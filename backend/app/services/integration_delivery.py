"""Send alerts to a customer's own tools: Slack, Microsoft Teams, Jira, Splunk.

Each organization configures its own destinations (``OrgIntegration`` rows).
``dispatch_integrations`` is called from the notification pipeline next to the
generic webhooks; it picks the organization's enabled integrations that
subscribe to the event and hands each to a small background pool, so a slow
or broken customer endpoint never delays a scan or an API request.

Safety rules, shared by every destination:

* Only the organization's own integrations are ever loaded (tenant filter in
  the query, re-checked in the worker).
* Destination URLs must be https and public. They are checked when saved and
  again on every request by ``GUARDED_HOOKS`` (DNS can change); redirects are
  not followed.
* Credentials are decrypted only inside the worker, are never logged, and
  never appear in stored error messages (errors are fixed strings, not the
  remote response or the exception text, which can contain the URL).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import frontend_url
from app.core import secret_box
from app.core.target_guard import GUARDED_HOOKS, check_public_target
from app.models.integration import IntegrationDelivery, OrgIntegration

logger = logging.getLogger(__name__)

MAX_PER_ORG = 20
AUTO_DISABLE_AFTER = 20  # consecutive failures
_ATTEMPTS = 2
_TIMEOUT = 10.0

# Events an integration can subscribe to (a subset of the webhook events:
# the ones the platform actually raises today).
EVENTS: Dict[str, str] = {
    "finding.critical": "New critical finding",
    "finding.high": "New high-severity finding",
    "finding.medium": "New medium-severity finding",
    "cve.new_match": "New CVE affecting your assets",
    "asset.shadow_asset": "Shadow asset discovered",
    "asset.new_subdomain": "New asset discovered",
    "asset.new_port": "New open port or service",
    "asset.disappeared": "Asset no longer found",
    "ssl.certificate_expiring": "Certificate expiring",
    "ssl.certificate_changed": "Certificate replaced",
    "scan.completed": "Scan completed",
    "scan.failed": "Scan failed",
}

_FINDING_EVENTS = ["finding.critical", "finding.high", "cve.new_match"]
_ALERT_EVENTS = _FINDING_EVENTS + [
    "asset.shadow_asset", "asset.new_subdomain", "asset.new_port",
    "ssl.certificate_expiring", "scan.failed",
]

KINDS: Dict[str, Dict[str, Any]] = {
    "slack": {
        "label": "Slack",
        "description": "Post alerts to a Slack channel.",
        "default_events": _ALERT_EVENTS,
        "fields": [
            {"key": "webhook_url", "label": "Incoming webhook URL", "secret": True, "required": True,
             "placeholder": "https://hooks.slack.com/services/…",
             "help": "In Slack: Apps > Incoming Webhooks > Add to a channel, then copy the URL."},
        ],
    },
    "teams": {
        "label": "Microsoft Teams",
        "description": "Post alerts to a Teams channel.",
        "default_events": _ALERT_EVENTS,
        "fields": [
            {"key": "webhook_url", "label": "Workflow webhook URL", "secret": True, "required": True,
             "placeholder": "https://…",
             "help": "In Teams: channel > Workflows > \"Post to a channel when a webhook request is received\"."},
        ],
    },
    "jira": {
        "label": "Jira",
        "description": "Open a Jira issue for each new finding.",
        "default_events": _FINDING_EVENTS,
        "fields": [
            {"key": "base_url", "label": "Jira site", "required": True,
             "placeholder": "https://yourcompany.atlassian.net"},
            {"key": "email", "label": "Account email", "required": True,
             "placeholder": "security-bot@yourcompany.com"},
            {"key": "api_token", "label": "API token", "secret": True, "required": True,
             "help": "Create one at id.atlassian.com > Security > API tokens. Use a service account "
                     "that can create issues in the project."},
            {"key": "project_key", "label": "Project key", "required": True, "placeholder": "SEC"},
            {"key": "issue_type", "label": "Issue type", "required": False, "placeholder": "Task"},
        ],
    },
    "splunk": {
        "label": "Splunk (SIEM)",
        "description": "Send every event to Splunk through the HTTP Event Collector.",
        "default_events": list(EVENTS.keys()),
        "fields": [
            {"key": "hec_url", "label": "HEC URL", "required": True,
             "placeholder": "https://http-inputs-yourstack.splunkcloud.com"},
            {"key": "token", "label": "HEC token", "secret": True, "required": True},
            {"key": "index", "label": "Index", "required": False, "placeholder": "main"},
            {"key": "sourcetype", "label": "Source type", "required": False, "placeholder": "cazo:easm"},
        ],
    },
}

_SLACK_HOSTS = {"hooks.slack.com", "hooks.slack-gov.com"}
_SEVERITY = {
    "finding.critical": "critical", "finding.high": "high", "finding.medium": "medium",
    "cve.new_match": "high", "scan.failed": "medium", "asset.shadow_asset": "medium",
}
_SEVERITY_COLOR = {"critical": "attention", "high": "attention", "medium": "warning", "low": "good", "info": "default"}
_SEVERITY_DOT = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "⚪"}


class IntegrationConfigError(ValueError):
    """The submitted settings are not acceptable; the message is shown to the user."""


# ── Validation ───────────────────────────────────────────────────────────


def _clean_url(raw: Any, label: str, *, keep_path: bool = True) -> str:
    url = str(raw or "").strip()
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise IntegrationConfigError(f"{label} is not a valid URL.")
    if parts.scheme != "https" or not host:
        raise IntegrationConfigError(f"{label} must start with https://.")
    if parts.username or parts.password:
        raise IntegrationConfigError(f"{label} must not contain a username or password.")
    if len(url) > 1000:
        raise IntegrationConfigError(f"{label} is too long.")
    if not keep_path:
        url = f"https://{host}" + (f":{port}" if port else "") + parts.path.rstrip("/")
    return url


def _require_public(url: str, label: str) -> None:
    host = urlsplit(url).hostname or ""
    if not check_public_target(host).allowed:
        raise IntegrationConfigError(
            f"{label} must be reachable from the internet. Private, local and reserved addresses are not allowed."
        )


def validate_settings(
    kind: str, values: Dict[str, Any], existing_secrets: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Split submitted values into (config, secrets), validated.

    A secret field left blank on an update keeps its stored value.
    """
    spec = KINDS.get(kind)
    if not spec:
        raise IntegrationConfigError("Unknown integration type.")
    existing_secrets = existing_secrets or {}
    known = {f["key"] for f in spec["fields"]}
    unknown = set(values or {}) - known
    if unknown:
        raise IntegrationConfigError(f"Unknown setting: {sorted(unknown)[0]}.")

    config: Dict[str, Any] = {}
    secrets: Dict[str, Any] = {}
    for f in spec["fields"]:
        raw = (values or {}).get(f["key"])
        value = str(raw).strip() if raw is not None else ""
        if f.get("secret") and not value:
            value = str(existing_secrets.get(f["key"]) or "")
        if f.get("required") and not value:
            raise IntegrationConfigError(f"{f['label']} is required.")
        if len(value) > 1000:
            raise IntegrationConfigError(f"{f['label']} is too long.")
        if any(ord(c) < 32 for c in value):
            raise IntegrationConfigError(f"{f['label']} contains invalid characters.")
        (secrets if f.get("secret") else config)[f["key"]] = value

    if kind == "slack":
        secrets["webhook_url"] = _clean_url(secrets["webhook_url"], "Incoming webhook URL")
        if (urlsplit(secrets["webhook_url"]).hostname or "").lower() not in _SLACK_HOSTS:
            raise IntegrationConfigError("That is not a Slack incoming webhook URL (it should start with https://hooks.slack.com/).")
    elif kind == "teams":
        secrets["webhook_url"] = _clean_url(secrets["webhook_url"], "Workflow webhook URL")
        _require_public(secrets["webhook_url"], "Workflow webhook URL")
    elif kind == "jira":
        config["base_url"] = _clean_url(config["base_url"], "Jira site", keep_path=False)
        _require_public(config["base_url"], "Jira site")
        if not re.fullmatch(r"[^@\s]{1,100}@[^@\s]{1,150}", config["email"]):
            raise IntegrationConfigError("Account email is not a valid email address.")
        config["project_key"] = config["project_key"].upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,19}", config["project_key"]):
            raise IntegrationConfigError("Project key should look like SEC or ITSEC (letters and digits only).")
        config["issue_type"] = config.get("issue_type") or "Task"
        if not re.fullmatch(r"[\w .\-]{1,40}", config["issue_type"]):
            raise IntegrationConfigError("Issue type contains invalid characters.")
    elif kind == "splunk":
        url = _clean_url(config["hec_url"], "HEC URL", keep_path=False)
        _require_public(url, "HEC URL")
        for suffix in ("/services/collector/event", "/services/collector"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
        config["hec_url"] = url
        config["sourcetype"] = config.get("sourcetype") or "cazo:easm"
        for key in ("index", "sourcetype"):
            if config.get(key) and not re.fullmatch(r"[\w:.\-]{1,80}", config[key]):
                raise IntegrationConfigError(f"{key.capitalize()} contains invalid characters.")
    return config, secrets


def validate_events(kind: str, event_types: Optional[List[str]]) -> List[str]:
    if not event_types:
        return list(KINDS[kind]["default_events"])
    bad = [e for e in event_types if e not in EVENTS]
    if bad:
        raise IntegrationConfigError(f"Unknown event: {bad[0]}.")
    return [e for e in EVENTS if e in set(event_types)]  # de-duplicated, stable order


def destination_hint(kind: str, config: Dict[str, Any], secrets: Dict[str, Any]) -> str:
    """A short, non-secret description of where this integration sends."""
    if kind in ("slack", "teams"):
        url = secrets.get("webhook_url") or ""
        host = urlsplit(url).hostname or ""
        return f"{host}/…{url[-4:]}" if url else ""
    if kind == "jira":
        return f"{urlsplit(config.get('base_url') or '').hostname or ''} · {config.get('project_key', '')}"
    if kind == "splunk":
        return urlsplit(config.get("hec_url") or "").hostname or ""
    return ""


# ── Message ──────────────────────────────────────────────────────────────


@dataclass
class OutboundMessage:
    event_type: str
    title: str
    message: str
    severity: str = "info"
    domain: str = ""
    lines: List[str] = field(default_factory=list)
    more: int = 0
    link: str = ""
    entity_type: str = ""
    entity_id: str = ""
    dedupe_key: str = ""
    occurred_at: str = ""
    test: bool = False


def _plain(value: Any, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", str(value if value is not None else "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_message(
    event_type: str,
    title: str,
    message: str,
    priority: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> OutboundMessage:
    data = data or {}
    severity = str(data.get("severity") or "").lower()
    if severity not in _SEVERITY_DOT:
        severity = _SEVERITY.get(event_type) or ("high" if priority in ("high", "urgent", "critical") else "info")
    items = data.get("items")
    lines = [_plain(i, 300) for i in items[:10]] if isinstance(items, list) else []
    more = data.get("more") if isinstance(data.get("more"), int) else 0
    if isinstance(items, list) and len(items) > 10:
        more += len(items) - 10
    path = data.get("url")
    link = frontend_url(path) if isinstance(path, str) and path.startswith("/") and not path.startswith("//") else frontend_url("/dashboard")
    dedupe = "|".join([event_type, entity_type or "", entity_id or "", str(data.get("alert_type") or ""), _plain(title, 200)])
    return OutboundMessage(
        event_type=event_type,
        title=_plain(title, 200),
        message=_plain(message, 1500),
        severity=severity,
        domain=_plain(data.get("domain") or "", 255),
        lines=lines,
        more=max(0, more),
        link=link,
        entity_type=entity_type or "",
        entity_id=entity_id or "",
        dedupe_key=hashlib.sha256(dedupe.encode()).hexdigest(),
        occurred_at=datetime.now(timezone.utc).isoformat(),
    )


def test_message() -> OutboundMessage:
    msg = build_message(
        "finding.high", "Test alert from CAZO EASM",
        "This is a test. If you can read it, the integration works.",
        data={"domain": "example.com", "items": ["example.com: sample finding (not real)"]},
    )
    msg.test = True
    return msg


def _slack_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _text_body(msg: OutboundMessage) -> str:
    parts = [msg.message]
    if msg.lines:
        parts.append("\n".join(f"- {line}" for line in msg.lines))
    if msg.more:
        parts.append(f"…and {msg.more} more.")
    return "\n\n".join(p for p in parts if p)


# ── Senders ──────────────────────────────────────────────────────────────


@dataclass
class SendResult:
    ok: bool
    error: str = ""
    external_ref: str = ""
    retry: bool = False


def _status_error(kind: str, status: int) -> SendResult:
    retry = status == 429 or status >= 500
    if status in (401, 403):
        text = {
            "jira": "Jira refused the email or API token, or the account cannot use this project.",
            "splunk": "Splunk refused the HEC token.",
        }.get(kind, "The destination refused the request. The webhook URL may have been revoked.")
    elif status == 404:
        text = {
            "jira": "Jira could not find that site or project.",
            "splunk": "No HTTP Event Collector was found at that URL.",
        }.get(kind, "The webhook URL no longer exists.")
    elif status == 400 and kind == "jira":
        text = "Jira rejected the issue. Check the issue type exists in the project and has no extra required fields."
    elif status == 429:
        text = "The destination is rate limiting us."
    else:
        text = f"The destination answered with HTTP {status}."
    return SendResult(False, text, retry=retry)


async def _send_slack(client, config, secrets, msg: OutboundMessage) -> SendResult:
    dot = _SEVERITY_DOT.get(msg.severity, "")
    body = _slack_escape(_text_body(msg))[:2900]
    context = " · ".join(x for x in [
        _slack_escape(msg.domain), EVENTS.get(msg.event_type, msg.event_type), f"<{msg.link}|Open in CAZO EASM>",
    ] if x)
    payload = {
        "text": f"{dot} {_slack_escape(msg.title)}".strip(),
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"{dot} {msg.title}".strip()[:150], "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": body or "-"}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": context}]},
        ],
    }
    resp = await client.post(secrets["webhook_url"], json=payload)
    return SendResult(True) if resp.status_code == 200 else _status_error("slack", resp.status_code)


async def _send_teams(client, config, secrets, msg: OutboundMessage) -> SendResult:
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": msg.title, "weight": "Bolder", "size": "Medium", "wrap": True,
             "color": _SEVERITY_COLOR.get(msg.severity, "default")},
            {"type": "TextBlock", "text": _text_body(msg)[:3000], "wrap": True},
            {"type": "FactSet", "facts": [f for f in [
                {"title": "Domain", "value": msg.domain} if msg.domain else None,
                {"title": "Event", "value": EVENTS.get(msg.event_type, msg.event_type)},
                {"title": "Severity", "value": msg.severity.capitalize()},
            ] if f]},
        ],
        "actions": [{"type": "Action.OpenUrl", "title": "Open in CAZO EASM", "url": msg.link}],
    }
    payload = {"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "content": card},
    ]}
    resp = await client.post(secrets["webhook_url"], json=payload)
    return SendResult(True) if 200 <= resp.status_code < 300 else _status_error("teams", resp.status_code)


def _jira_auth(config, secrets) -> httpx.BasicAuth:
    return httpx.BasicAuth(config["email"], secrets["api_token"])


async def _send_jira(client, config, secrets, msg: OutboundMessage) -> SendResult:
    description = "\n\n".join(x for x in [
        _text_body(msg),
        f"Domain: {msg.domain}" if msg.domain else "",
        f"Severity: {msg.severity}",
        f"Details: {msg.link}",
        "Created automatically by CAZO EASM.",
    ] if x)
    payload = {"fields": {
        "project": {"key": config["project_key"]},
        "summary": f"[{msg.severity.upper()}] {msg.title}"[:250],
        "description": description[:30000],
        "issuetype": {"name": config.get("issue_type") or "Task"},
        "labels": ["cazo-easm", f"severity-{msg.severity}"],
    }}
    resp = await client.post(f"{config['base_url']}/rest/api/2/issue", json=payload, auth=_jira_auth(config, secrets))
    if resp.status_code in (200, 201):
        key = ""
        try:
            key = str(resp.json().get("key") or "")[:100]
        except Exception:  # noqa: BLE001
            pass
        return SendResult(True, external_ref=key)
    return _status_error("jira", resp.status_code)


async def _test_jira(client, config, secrets) -> SendResult:
    """Check the credentials and project without opening an issue."""
    resp = await client.get(
        f"{config['base_url']}/rest/api/2/project/{config['project_key']}", auth=_jira_auth(config, secrets),
    )
    return SendResult(True) if resp.status_code == 200 else _status_error("jira", resp.status_code)


async def _send_splunk(client, config, secrets, msg: OutboundMessage) -> SendResult:
    event = {k: v for k, v in asdict(msg).items() if k not in ("dedupe_key",)}
    event["vendor"] = "CAZO"
    event["product"] = "EASM"
    payload: Dict[str, Any] = {"time": time.time(), "sourcetype": config.get("sourcetype") or "cazo:easm", "event": event}
    if config.get("index"):
        payload["index"] = config["index"]
    resp = await client.post(
        f"{config['hec_url']}/services/collector/event", json=payload,
        headers={"Authorization": f"Splunk {secrets['token']}"},
    )
    return SendResult(True) if resp.status_code == 200 else _status_error("splunk", resp.status_code)


_SENDERS = {"slack": _send_slack, "teams": _send_teams, "jira": _send_jira, "splunk": _send_splunk}


def _make_client() -> httpx.AsyncClient:
    # GUARDED_HOOKS refuses non-public hosts at request time; no redirects.
    return httpx.AsyncClient(
        timeout=_TIMEOUT, event_hooks=GUARDED_HOOKS, follow_redirects=False,
        headers={"User-Agent": "CAZO-EASM-Integrations/1.0"},
    )


async def send_once(kind: str, config: Dict[str, Any], secrets: Dict[str, Any], msg: OutboundMessage) -> SendResult:
    """One attempt. Never raises; never puts the URL or a token in the error."""
    try:
        async with _make_client() as client:
            if msg.test and kind == "jira":
                return await _test_jira(client, config, secrets)
            return await _SENDERS[kind](client, config, secrets, msg)
    except httpx.TimeoutException:
        return SendResult(False, "The destination did not answer in time.", retry=True)
    except httpx.RequestError as exc:
        if "non-public host" in str(exc):
            return SendResult(False, "The destination address is not a public internet address.")
        return SendResult(False, "Could not connect to the destination.", retry=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Integration send failed (%s): %s", kind, type(exc).__name__)
        return SendResult(False, "The message could not be sent.")


async def send_with_retry(kind, config, secrets, msg) -> SendResult:
    result = SendResult(False, "Not sent.")
    for attempt in range(_ATTEMPTS):
        result = await send_once(kind, config, secrets, msg)
        if result.ok or not result.retry:
            break
        if attempt < _ATTEMPTS - 1:
            await asyncio.sleep(1.5)
    return result


# ── Dispatch ─────────────────────────────────────────────────────────────

_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="integrations")
_recent: Dict[Tuple[str, str], float] = {}
_recent_lock = threading.Lock()
_REPEAT_WINDOW = 120.0  # seconds


def _submit(integration_id: str, organization_id: str, msg: OutboundMessage) -> None:
    """Queue one delivery. Replaced in tests to run inline."""
    _pool.submit(deliver, integration_id, organization_id, msg)


def record_result(row: OrgIntegration, result: SendResult) -> None:
    now = datetime.now(timezone.utc)
    if result.ok:
        row.failure_count = 0
        row.last_success_at = now
        row.last_error = None
    else:
        row.failure_count = (row.failure_count or 0) + 1
        row.last_failure_at = now
        row.last_error = (result.error or "Failed")[:300]
        if row.failure_count >= AUTO_DISABLE_AFTER:
            row.enabled = False
            row.last_error = (f"Turned off after {AUTO_DISABLE_AFTER} failed deliveries in a row. " + row.last_error)[:300]


def deliver(integration_id: str, organization_id: str, msg: OutboundMessage) -> Optional[SendResult]:
    """Send one message through one integration (runs in the background pool)."""
    import app.database as _database

    db = _database.SessionLocal()
    try:
        row = (
            db.query(OrgIntegration)
            .filter(OrgIntegration.id == integration_id, OrgIntegration.organization_id == organization_id)
            .first()
        )
        if not row or not row.enabled:
            return None
        kind, config = row.kind, dict(row.config or {})
        try:
            secrets = secret_box.decrypt(row.secret_encrypted)
        except secret_box.SecretUnreadable:
            record_result(row, SendResult(False, "Stored credentials can no longer be read. Please enter them again."))
            db.commit()
            return None

        claim = None
        if kind == "jira":
            # Claim the alert first so two workers cannot open two tickets.
            claim = IntegrationDelivery(
                integration_id=row.id, organization_id=organization_id, dedupe_key=msg.dedupe_key,
            )
            db.add(claim)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return None  # already ticketed

        result = asyncio.run(send_with_retry(kind, config, secrets, msg))

        row = db.query(OrgIntegration).filter(OrgIntegration.id == integration_id).first()
        if row:
            record_result(row, result)
        if claim is not None:
            if result.ok:
                claim.external_ref = result.external_ref or None
            else:
                db.delete(claim)  # let a later alert try again
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001
        logger.error("Integration delivery crashed for %s: %s", integration_id, type(exc).__name__)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    finally:
        db.close()


def dispatch_integrations(
    db: Session,
    organization_id: Optional[str],
    event_type: str,
    title: str,
    message: str,
    priority: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
) -> int:
    """Queue the event for the organization's matching integrations. Never raises."""
    if not organization_id:
        return 0
    try:
        rows = (
            db.query(OrgIntegration.id, OrgIntegration.event_types)
            .filter(OrgIntegration.organization_id == organization_id, OrgIntegration.enabled.is_(True))
            .all()
        )
        matching = [r.id for r in rows if event_type in (r.event_types or [])]
        if not matching:
            return 0
        msg = build_message(event_type, title, message, priority, data, related_entity_type, related_entity_id)
        # The same alert is raised once per recipient; send it out only once.
        now = time.monotonic()
        key = (organization_id, msg.dedupe_key)
        with _recent_lock:
            if now - _recent.get(key, -1e9) < _REPEAT_WINDOW:
                return 0
            if len(_recent) > 5000:
                _recent.clear()
            _recent[key] = now
        for integration_id in matching:
            _submit(integration_id, organization_id, msg)
        return len(matching)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to dispatch integrations for org %s: %s", organization_id, exc)
        return 0
