"""Detect credentials that a public web response gives away.

Used on content any visitor can already fetch: home pages, same-origin
JavaScript bundles and files such as an exposed ``.env``. Matches are
*never* stored in full. A finding keeps the secret's type, where it was
seen, a redacted preview (first and last few characters) and a SHA-256
fingerprint so the same secret can be tracked across scans and confirmed
rotated, without the platform becoming a store of customers' keys.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Pattern


@dataclass(frozen=True)
class SecretRule:
    rule_id: str
    name: str
    pattern: Pattern[str]
    severity: str
    group: int = 0          # regex group holding the secret value
    min_entropy: float = 0.0


def _r(p: str, flags: int = 0) -> Pattern[str]:
    return re.compile(p, flags)


SECRET_RULES: List[SecretRule] = [
    SecretRule("aws-access-key-id", "AWS access key ID", _r(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), "high", 1),
    SecretRule(
        "aws-secret-access-key", "AWS secret access key",
        _r(r"(?i)aws.{0,20}?(?:secret|private).{0,20}?['\"=:\s]{1,4}([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"),
        "critical", 1, 3.5,
    ),
    SecretRule("gcp-api-key", "Google API key", _r(r"\b(AIza[0-9A-Za-z_\-]{35})\b"), "medium", 1),
    SecretRule("gcp-service-account", "Google service account key", _r(r"\"type\"\s*:\s*\"(service_account)\""), "critical", 1),
    SecretRule("stripe-secret-key", "Stripe secret key", _r(r"\b((?:sk|rk)_live_[0-9A-Za-z]{20,})\b"), "critical", 1),
    SecretRule("github-token", "GitHub token", _r(r"\b((?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36,})\b"), "critical", 1),
    SecretRule("github-fine-grained", "GitHub fine-grained token", _r(r"\b(github_pat_[0-9A-Za-z_]{60,})\b"), "critical", 1),
    SecretRule("gitlab-token", "GitLab personal access token", _r(r"\b(glpat-[0-9A-Za-z_\-]{20})\b"), "critical", 1),
    SecretRule("slack-token", "Slack token", _r(r"\b(xox[abprs]-[0-9A-Za-z-]{10,})\b"), "high", 1),
    SecretRule("slack-webhook", "Slack incoming webhook", _r(r"(https://hooks\.slack\.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[0-9A-Za-z]+)"), "medium", 1),
    SecretRule("discord-webhook", "Discord webhook", _r(r"(https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+)"), "medium", 1),
    SecretRule("twilio-api-key", "Twilio API key", _r(r"\b(SK[0-9a-fA-F]{32})\b"), "high", 1),
    SecretRule("sendgrid-api-key", "SendGrid API key", _r(r"\b(SG\.[0-9A-Za-z_\-]{22}\.[0-9A-Za-z_\-]{43})\b"), "high", 1),
    SecretRule("mailgun-api-key", "Mailgun API key", _r(r"\b(key-[0-9a-zA-Z]{32})\b"), "high", 1),
    SecretRule("openai-api-key", "OpenAI API key", _r(r"\b(sk-(?:proj-)?[A-Za-z0-9_\-]{20,}T3BlbkFJ[A-Za-z0-9_\-]{20,})\b"), "critical", 1),
    SecretRule("anthropic-api-key", "Anthropic API key", _r(r"\b(sk-ant-[A-Za-z0-9_\-]{30,})\b"), "critical", 1),
    SecretRule("private-key", "Private key", _r(r"(-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----)"), "critical", 1),
    SecretRule(
        "db-connection-string", "Database connection string with password",
        _r(r"\b((?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)://[^\s:'\"/@]+:[^\s@'\"/]{3,}@[^\s'\"<>]+)"),
        "critical", 1,
    ),
    SecretRule(
        "jwt", "JSON Web Token",
        _r(r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})\b"),
        "medium", 1,
    ),
    SecretRule(
        "generic-password-assignment", "Hard-coded password",
        _r(r"(?im)^\s*[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|API_KEY|TOKEN|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*['\"]?([^\s'\"#]{8,})"),
        "high", 1, 3.0,
    ),
]

# Placeholder values that are not real secrets.
_PLACEHOLDERS = re.compile(
    r"(?i)^(?:x+|\*+|changeme|change_me|your[_-]?.*|example.*|dummy.*|test.*|sample.*|"
    r"placeholder.*|null|none|undefined|true|false|<.*>|\$\{.*\}|%.*%|\{\{.*\}\})$"
)


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: Dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def redact(value: str) -> str:
    """Keep enough to recognise the secret, never enough to use it."""
    if len(value) <= 8:
        return value[:1] + "…" + f" ({len(value)} chars)"
    if len(value) <= 16:
        return value[:3] + "…" + value[-2:] + f" ({len(value)} chars)"
    return value[:6] + "…" + value[-4:] + f" ({len(value)} chars)"


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]


def find_secrets(text: str, limit: int = 20) -> List[Dict[str, str]]:
    """Return redacted matches in ``text``. The raw values are discarded."""
    if not text:
        return []
    out: List[Dict[str, str]] = []
    seen: set = set()
    for rule in SECRET_RULES:
        for m in rule.pattern.finditer(text):
            value = m.group(rule.group) if rule.group else m.group(0)
            if not value or _PLACEHOLDERS.match(value):
                continue
            if rule.min_entropy and shannon_entropy(value) < rule.min_entropy:
                continue
            fp = fingerprint(value)
            if fp in seen:
                continue
            seen.add(fp)
            out.append({
                "rule_id": rule.rule_id,
                "name": rule.name,
                "severity": rule.severity,
                "redacted": redact(value) if rule.rule_id not in ("private-key", "gcp-service-account") else rule.name,
                "fingerprint": fp,
            })
            if len(out) >= limit:
                return out
    return out
