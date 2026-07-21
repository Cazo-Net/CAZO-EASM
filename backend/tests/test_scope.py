"""Unit tests for authorized-scope enforcement (pure logic, no DB)."""
import pytest

from app.core.scope import (
    check_target_authorized,
    is_valid_scope_value,
    _matches_domain,
    _ip_in_scope,
    ScopeMatch,
)
from app.models.scope import AuthorizedScope
from app.core.permissions import Permission


class TestScopeValidation:
    def test_valid_domain(self):
        assert is_valid_scope_value("domain", "example.com")
        assert is_valid_scope_value("domain", "app.example.com")
        assert not is_valid_scope_value("domain", "not a domain")

    def test_valid_wildcard(self):
        assert is_valid_scope_value("wildcard", "*.example.com")
        assert not is_valid_scope_value("wildcard", "example.com")

    def test_valid_ip_and_cidr(self):
        # Public IPs are allowed
        assert is_valid_scope_value("ip", "8.8.8.8")
        assert is_valid_scope_value("cidr", "8.8.8.0/24")
        # Private/reserved IPs are now blocked (SSRF protection)
        assert not is_valid_scope_value("ip", "10.0.0.1")
        assert not is_valid_scope_value("cidr", "10.0.0.0/24")
        assert not is_valid_scope_value("ip", "192.168.1.1")
        assert not is_valid_scope_value("ip", "127.0.0.1")
        # Invalid IPs still rejected
        assert not is_valid_scope_value("ip", "999.0.0.1")
        assert not is_valid_scope_value("cidr", "10.0.0.0/40")

    def test_private_ip_blocked(self):
        """Private/reserved IPs cannot be added as scopes (SSRF prevention)."""
        assert not is_valid_scope_value("ip", "10.0.0.1")
        assert not is_valid_scope_value("ip", "172.16.0.1")
        assert not is_valid_scope_value("ip", "192.168.1.1")
        assert not is_valid_scope_value("ip", "127.0.0.1")
        assert not is_valid_scope_value("ip", "169.254.1.1")
        assert not is_valid_scope_value("cidr", "10.0.0.0/8")
        assert not is_valid_scope_value("cidr", "192.168.0.0/16")


class TestDomainMatching:
    def test_exact(self):
        assert _matches_domain("example.com", "example.com")
        assert not _matches_domain("example.com", "other.com")

    def test_wildcard_apex_and_sub(self):
        assert _matches_domain("*.example.com", "example.com")
        assert _matches_domain("*.example.com", "api.example.com")
        assert _matches_domain("*.example.com", "a.b.example.com")
        assert not _matches_domain("*.example.com", "example.org")

    def test_case_insensitive(self):
        assert _matches_domain("Example.COM", "example.com")


class TestIpMatching:
    def test_exact_ip(self):
        assert _ip_in_scope("8.8.8.8", "8.8.8.8")
        assert not _ip_in_scope("8.8.8.8", "8.8.4.4")

    def test_cidr(self):
        assert _ip_in_scope("8.8.8.0/24", "8.8.8.42")
        assert not _ip_in_scope("8.8.8.0/24", "8.8.9.1")

    def test_ipv6(self):
        assert _ip_in_scope("2001:db8::1", "2001:db8::1")


class TestCheckAuthorized:
    """Uses a fake session returning configured scopes."""

    class _FakeQuery:
        def __init__(self, scopes):
            self._scopes = scopes

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._scopes

    class _FakeSession:
        def __init__(self, scopes):
            self._scopes = scopes

        def query(self, *args, **kwargs):
            return TestCheckAuthorized._FakeQuery(self._scopes)

    def _scope(self, scope_type, value, verified=True):
        return AuthorizedScope(
            id=f"scope-{scope_type}-{value}",
            organization_id="org1",
            scope_type=scope_type,
            value=value,
            verified=verified,
        )

    def test_no_scopes_implicit_deny_with_explicit_requirement(self, monkeypatch):
        # With REQUIRE_EXPLICIT_SCOPE on (production default), empty scopes => denied.
        from app.core import scope as scope_mod
        monkeypatch.setattr(scope_mod, "_require_explicit_scope", lambda: True)
        db = self._FakeSession([])
        m = check_target_authorized(db, "org1", "anything.com")
        assert m.authorized is False

    def test_matching_scope_allows(self):
        db = self._FakeSession([self._scope("domain", "example.com")])
        m = check_target_authorized(db, "org1", "example.com")
        assert m.authorized is True
        assert m.matched_scope_id is not None

    def test_non_matching_scope_denies(self):
        db = self._FakeSession([self._scope("domain", "example.com")])
        m = check_target_authorized(db, "org1", "other.com")
        assert m.authorized is False

    def test_wildcard_scope_allows_subdomain(self):
        db = self._FakeSession([self._scope("wildcard", "*.example.com")])
        m = check_target_authorized(db, "org1", "api.example.com")
        assert m.authorized is True

    def test_cidr_scope_allows_host(self):
        db = self._FakeSession([self._scope("cidr", "8.8.8.0/24")])
        m = check_target_authorized(db, "org1", "8.8.8.42")
        assert m.authorized is True

    def test_private_ip_target_denied(self):
        """Private IP targets are blocked even with a matching scope."""
        db = self._FakeSession([self._scope("cidr", "10.0.0.0/8")])
        m = check_target_authorized(db, "org1", "10.0.0.1")
        assert m.authorized is False

    def test_private_scope_denied(self):
        """Private IP scopes are blocked."""
        db = self._FakeSession([self._scope("cidr", "192.168.0.0/16")])
        m = check_target_authorized(db, "org1", "192.168.5.5")
        assert m.authorized is False
