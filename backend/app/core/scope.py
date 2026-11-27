"""Authorized-scope enforcement.

Centralizes the "only authorized data collection" policy. Discovery targets are
checked against an organization's ``AuthorizedScope`` rows before any scanner is
invoked, and the result is recorded for auditability.

Design notes:
- Matching supports exact domains, ``*.example.com`` wildcards, single IP
  addresses, and CIDR blocks.
- Verification is pluggable via :class:`ScopeVerifier`. The default verifier
  performs no out-of-band checks (scope is trusted once recorded); an optional
  ``DnsTxtScopeVerifier`` stub shows where ownership proof would hook in. This
  keeps the system strict-by-policy without tight coupling to any external
  verification provider.
- When ``REQUIRE_EXPLICIT_SCOPE`` is disabled (dev default) and an organization
  has *no* scopes configured, the org is treated as implicitly authorized so the
  existing behavior (and the test suite) is preserved. In production this flag
  should be enabled.
"""
import ipaddress
import logging
import re
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.scope import AuthorizedScope

logger = logging.getLogger(__name__)

# Domain label regex (RFC 1123-ish, pragmatic).
_DOMAIN_RE = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


@dataclass
class ScopeMatch:
    authorized: bool
    matched_scope_id: Optional[str] = None
    scope_type: Optional[str] = None
    reason: str = ""


class ScopeVerifier(ABC):
    """Pluggable verification of a scope's ownership/authorization.

    Implementations may perform out-of-band checks (DNS TXT, email, etc.).
    The default :class:`NoopVerifier` trusts scopes as recorded.
    """

    @abstractmethod
    def verify(self, scope: AuthorizedScope) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class NoopVerifier(ScopeVerifier):
    """Trusts scopes as recorded in the database (no out-of-band check)."""

    @property
    def name(self) -> str:
        return "noop"

    def verify(self, scope: AuthorizedScope) -> bool:
        return True


class DnsTxtScopeVerifier(ScopeVerifier):
    """Ownership verification via a DNS TXT record.

    The customer publishes ``cazo-verify=<token>`` at
    ``_cazo-verify.<domain>``, where ``<token>`` is the scope's own random
    ``verification_token``. Lookup failures count as "not verified"; they never
    fall back to trusting the stored flag.
    """

    @property
    def name(self) -> str:
        return "dns_txt"

    def verify(self, scope: AuthorizedScope) -> bool:
        import dns.resolver  # type: ignore[import-untyped]

        if scope.scope_type not in ("domain", "wildcard"):
            return False
        token = getattr(scope, "verification_token", None)
        if not token:
            return False

        name = verification_record_name(scope)
        expected = f"cazo-verify={token}"
        try:
            answers = dns.resolver.resolve(name, "TXT", lifetime=5)
        except Exception as exc:  # noqa: BLE001 — NXDOMAIN, NoAnswer, timeout
            logger.info("DNS TXT lookup for %s failed: %s", name, exc)
            return False
        for rdata in answers:
            txt = b"".join(rdata.strings).decode("utf-8", errors="replace").strip()
            if secrets.compare_digest(txt, expected):
                return True
        logger.info("DNS TXT verification failed for %s: no matching record", name)
        return False


def verification_base_domain(scope: AuthorizedScope) -> str:
    value = _normalize_hostname(scope.value)
    return value[2:] if value.startswith("*.") else value


def verification_record_name(scope: AuthorizedScope) -> str:
    return f"_cazo-verify.{verification_base_domain(scope)}"


def ensure_verification_token(scope: AuthorizedScope) -> str:
    if not getattr(scope, "verification_token", None):
        scope.verification_token = secrets.token_urlsafe(24)
    return scope.verification_token


def verification_instructions(scope: AuthorizedScope) -> dict:
    """What the customer must publish to prove ownership of a scope."""
    if scope.scope_type not in ("domain", "wildcard"):
        return {
            "method": "manual",
            "instructions": "IP and CIDR scopes are verified by a platform administrator.",
        }
    token = ensure_verification_token(scope)
    return {
        "method": "dns_txt",
        "record_type": "TXT",
        "record_name": verification_record_name(scope),
        "record_value": f"cazo-verify={token}",
        "instructions": (
            f"Add a DNS TXT record named {verification_record_name(scope)} with the value "
            f"cazo-verify={token}, then press Verify. DNS changes can take a few minutes to appear."
        ),
    }


def _require_explicit_scope() -> bool:
    return getattr(settings, "REQUIRE_EXPLICIT_SCOPE", False)


def _normalize_hostname(target: str) -> str:
    return target.strip().rstrip(".").lower()


def _matches_domain(value: str, target: str) -> bool:
    """Return True if ``target`` is authorized by the domain/wildcard ``value``."""
    val = _normalize_hostname(value)
    tgt = _normalize_hostname(target)
    if val.startswith("*."):
        base = val[2:]
        # Authorize base domain and any single-level+ subdomain.
        if tgt == base:
            return True
        return tgt.endswith("." + base)
    return val == tgt


def _ip_in_scope(value: str, target: str) -> bool:
    try:
        if "/" in value:
            net = ipaddress.ip_network(value, strict=False)
            return ipaddress.ip_address(target) in net
        return ipaddress.ip_address(value) == ipaddress.ip_address(target)
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# SECURITY: Private/loopback IP ranges that must never be scanned.
# These are blocked at scope creation AND at scan-time enforcement.
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback (IPv4)
    ipaddress.ip_network("10.0.0.0/8"),        # private (RFC1918)
    ipaddress.ip_network("172.16.0.0/12"),     # private (RFC1918)
    ipaddress.ip_network("192.168.0.0/16"),    # private (RFC1918)
    ipaddress.ip_network("169.254.0.0/16"),    # link-local
    ipaddress.ip_network("100.64.0.0/10"),     # shared address space (RFC6598)
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),      # documentation (TEST-NET-1)
    ipaddress.ip_network("198.51.100.0/24"),   # documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),    # documentation (TEST-NET-3)
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("::1/128"),            # loopback (IPv6)
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]


def _is_private_or_reserved_ip(ip_str: str) -> bool:
    """Return True if the IP address is private, loopback, link-local, or reserved.

    Used to block scanning of internal infrastructure via SSRF.
    Checks against both Python's ipaddress flags AND our explicit blocked list
    (which covers RFC6598 shared address space that Python doesn't flag).
    """
    try:
        addr = ipaddress.ip_address(ip_str)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return True
        # Check against explicit blocked networks (covers RFC6598 etc.)
        return any(addr in blocked for blocked in _BLOCKED_NETWORKS)
    except ValueError:
        return False


def _scope_value_is_private(scope_value: str) -> bool:
    """Return True if a scope value (IP or CIDR) overlaps private ranges."""
    try:
        if "/" in scope_value:
            net = ipaddress.ip_network(scope_value, strict=False)
            return any(net.overlaps(blocked) for blocked in _BLOCKED_NETWORKS)
        return _is_private_or_reserved_ip(scope_value)
    except ValueError:
        return False


def _target_matches_scope(scope: AuthorizedScope, target: str) -> bool:
    t = _normalize_hostname(target)

    # SECURITY: Block scanning of private/loopback/reserved IP ranges
    # regardless of whether an org has configured a matching scope.
    if scope.scope_type in ("ip", "cidr"):
        # If the TARGET is a private IP, block it.
        if _is_private_or_reserved_ip(t):
            logger.warning(f"Blocked scan of private/reserved target: {t}")
            return False
        # If the SCOPE itself is a private range, block it.
        if _scope_value_is_private(scope.value):
            logger.warning(f"Blocked private/reserved scope: {scope.value}")
            return False

    if scope.scope_type in ("domain", "wildcard"):
        return _matches_domain(scope.value, t)
    if scope.scope_type in ("ip", "cidr"):
        return _ip_in_scope(scope.value, t)
    # Unknown type: be conservative and deny.
    return False


def get_scopes_for_org(db: Session, organization_id: str) -> List[AuthorizedScope]:
    return (
        db.query(AuthorizedScope)
        .filter(AuthorizedScope.organization_id == organization_id)
        .all()
    )


def check_target_authorized(
    db: Session,
    organization_id: str,
    target: str,
    verifier: Optional[ScopeVerifier] = None,
) -> ScopeMatch:
    """Check whether ``target`` is authorized for ``organization_id``.

    Returns a :class:`ScopeMatch`. When the org has no scopes configured and
    ``REQUIRE_EXPLICIT_SCOPE`` is disabled, the target is authorized implicitly
    (preserves legacy behavior) with ``matched_scope_id=None``.
    """
    verifier = verifier or NoopVerifier()
    target = _normalize_hostname(target)

    scopes = get_scopes_for_org(db, organization_id)
    if not scopes:
        if _require_explicit_scope():
            return ScopeMatch(
                authorized=False,
                reason="No authorized scopes configured for organization.",
            )
        return ScopeMatch(
            authorized=True,
            reason="Implicit authorization (no explicit scopes configured).",
        )

    for scope in scopes:
        if not _target_matches_scope(scope, target):
            continue
        if getattr(settings, "REQUIRE_VERIFIED_SCOPE", False) and not scope.verified:
            # Scope matches but is unverified and verification is required.
            continue
        if not verifier.verify(scope):
            continue
        return ScopeMatch(
            authorized=True,
            matched_scope_id=scope.id,
            scope_type=scope.scope_type,
            reason=f"Matched {scope.scope_type} scope '{scope.value}'.",
        )

    return ScopeMatch(
        authorized=False,
        reason="Target does not match any authorized scope for the organization.",
    )


def is_valid_scope_value(scope_type: str, value: str) -> bool:
    """Validate a scope value's syntax for its type (used on create/update).

    SECURITY: Also rejects private/loopback/reserved IP ranges to prevent
    SSRF against internal infrastructure.
    """
    value = value.strip()
    if scope_type == "wildcard":
        if not value.startswith("*."):
            return False
        body = value[2:]
        return bool(_DOMAIN_RE.match(body))
    if scope_type == "domain":
        return bool(_DOMAIN_RE.match(value))
    if scope_type in ("ip", "cidr"):
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
            # Block private/loopback/reserved ranges
            if _scope_value_is_private(value):
                return False
            return True
        except ValueError:
            return False
    return False


# ---------------------------------------------------------------------------
# Scan-time enforcement
# ---------------------------------------------------------------------------

SCOPE_MODES = ("verified", "registered", "open")


def scope_mode() -> str:
    """How strictly scans are gated by authorized scopes.

    * ``verified``   — target must match a scope whose ownership is proven
                       (DNS TXT, or set by a platform admin). Production default.
    * ``registered`` — target must match any scope the organization added.
    * ``open``       — no scope check (development default).

    Internal and private addresses are blocked in every mode.
    """
    from app.config import is_production

    mode = (getattr(settings, "SCOPE_ENFORCEMENT", "") or "").strip().lower()
    if mode in SCOPE_MODES:
        return mode
    if getattr(settings, "REQUIRE_VERIFIED_SCOPE", False):
        return "verified"
    return "verified" if is_production() else "open"


@dataclass
class ScanAuthorization:
    authorized: bool
    target: str
    reason: str = ""
    scope_id: Optional[str] = None
    verification: Optional[dict] = None

    def as_error_detail(self) -> dict:
        detail = {"msg": self.reason, "target": self.target}
        if self.scope_id:
            detail["scope_id"] = self.scope_id
        if self.verification:
            detail["verification"] = self.verification
        return detail


def _matching_scopes(db: Session, organization_id: str, target: str) -> List[AuthorizedScope]:
    return [s for s in get_scopes_for_org(db, organization_id) if _target_matches_scope(s, target)]


def authorize_scan_target(
    db: Session,
    organization_id: Optional[str],
    raw_target: str,
    *,
    actor_id: Optional[str] = None,
    auto_register: bool = True,
    resolve: bool = True,
    mode: Optional[str] = None,
) -> ScanAuthorization:
    """Decide whether ``organization_id`` may actively scan ``raw_target``.

    Called when a scan or schedule is created, and again by the worker right
    before a scan runs (scopes can be revoked and DNS can change).

    When the target is not covered and ``auto_register`` is on, an unverified
    ``*.domain`` scope is created for the organization and the response
    carries the DNS TXT record to publish, so the user can verify and retry
    instead of hunting for the scopes page.
    """
    from app.core.target_guard import check_public_target

    guard = check_public_target(raw_target, resolve=resolve)
    if not guard.allowed:
        return ScanAuthorization(False, guard.target, guard.reason)
    target = guard.target

    if not organization_id:
        return ScanAuthorization(False, target, "You must belong to an organization to scan.")

    mode = mode if mode in SCOPE_MODES else scope_mode()
    if mode == "open":
        return ScanAuthorization(True, target, "Scope enforcement is disabled (SCOPE_ENFORCEMENT=open).")

    matches = _matching_scopes(db, organization_id, target)
    if mode == "registered" and matches:
        return ScanAuthorization(True, target, "Matched registered scope.", scope_id=matches[0].id)

    verified = [s for s in matches if s.verified]
    if verified:
        return ScanAuthorization(True, target, "Matched verified scope.", scope_id=verified[0].id)

    if matches:
        scope = matches[0]
    elif auto_register and mode == "verified" and is_valid_scope_value("wildcard", f"*.{target}"):
        scope = AuthorizedScope(
            organization_id=organization_id,
            scope_type="wildcard",
            value=f"*.{target}",
            verified=False,
            added_by=actor_id,
            note="Added automatically when a scan was requested; verify ownership to enable scanning.",
        )
        ensure_verification_token(scope)
        db.add(scope)
        db.commit()
        db.refresh(scope)
    else:
        return ScanAuthorization(
            False, target,
            f"'{target}' is not in your organization's authorized scope. Add it on the Scopes page first.",
        )

    instructions = verification_instructions(scope)
    if instructions.get("method") == "dns_txt":
        db.commit()  # persist a freshly generated token
    return ScanAuthorization(
        False,
        target,
        f"Ownership of {verification_base_domain(scope)} is not verified yet. "
        + instructions["instructions"],
        scope_id=scope.id,
        verification=instructions,
    )
