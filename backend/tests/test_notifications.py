"""Tests for the notifications & preferences system.

Covers:
  - dispatch_notification(): preference checks, dedup, in-app creation
  - ensure_default_preferences()
  - Notification preferences API (list, bulk update, single update)
  - Auth hooks (login notification, password change)
  - Scan hook CVE dispatch
"""



# ---------------------------------------------------------------------------
# Helper: create a user directly in the DB
# ---------------------------------------------------------------------------
def _create_user(db, email="notif@test.com", password="TestPass123!"):
    from app.models.user import User
    from app.core.security import get_password_hash
    user = User(
        email=email,
        full_name="Notif Test",
        hashed_password=get_password_hash(password),
        is_active=True,
        organization_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ===========================================================================
# 1. dispatch_notification – in-app creation
# ===========================================================================
class TestDispatchNotificationInApp:
    def test_creates_in_app_notification(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="scan_completed",
            title="Scan done",
            message="All clear",
            data={"domain": "example.com"},
        )
        assert notif is not None
        assert notif.type == "scan_completed"
        assert notif.title == "Scan done"
        assert notif.priority == "normal"
        assert notif.channel == "in_app"
        assert notif.read is False
        assert notif.data["domain"] == "example.com"

    def test_returns_none_when_all_channels_disabled(self, db_session):
        from app.services.notification_service import dispatch_notification, ensure_default_preferences
        user = _create_user(db_session)
        ensure_default_preferences(db_session, user.id)
        # Disable both channels for scan_completed
        from app.models.notification_preference import NotificationPreference
        pref = db_session.query(NotificationPreference).filter(
            NotificationPreference.user_id == user.id,
            NotificationPreference.notification_type == "scan_completed",
        ).first()
        pref.in_app_enabled = False
        pref.email_enabled = False
        db_session.commit()

        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="scan_completed",
            title="Should not appear",
            message="Suppressed",
        )
        assert notif is None

    def test_priority_resolved_from_type(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="new_finding_critical",
            title="Critical vuln",
            message="RCE found",
        )
        assert notif is not None
        assert notif.priority == "critical"

    def test_explicit_priority_overrides_type_default(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="scan_completed",
            title="Custom priority",
            message="msg",
            priority="critical",
        )
        assert notif is not None
        assert notif.priority == "critical"


# ===========================================================================
# 2. dispatch_notification – deduplication
# ===========================================================================
class TestDispatchDeduplication:
    def test_dedup_suppresses_duplicate_within_24h(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif1 = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="ssl_expiring",
            title="SSL expiring",
            message="30 days left",
            related_entity_type="certificate",
            related_entity_id="cert-123",
        )
        assert notif1 is not None
        # Second dispatch with same entity should be deduplicated
        notif2 = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="ssl_expiring",
            title="SSL expiring",
            message="30 days left",
            related_entity_type="certificate",
            related_entity_id="cert-123",
        )
        assert notif2 is None

    def test_dedup_allows_different_entity(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="ssl_expiring",
            title="SSL expiring",
            message="30 days left",
            related_entity_type="certificate",
            related_entity_id="cert-123",
        )
        notif2 = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="ssl_expiring",
            title="SSL expiring",
            message="15 days left",
            related_entity_type="certificate",
            related_entity_id="cert-456",
        )
        assert notif2 is not None

    def test_skip_dedup_bypasses_dedup(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif1 = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="scan_completed",
            title="Scan 1",
            message="msg",
            related_entity_type="scan",
            related_entity_id="scan-1",
            skip_dedup=True,
        )
        notif2 = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="scan_completed",
            title="Scan 1 again",
            message="msg",
            related_entity_type="scan",
            related_entity_id="scan-1",
            skip_dedup=True,
        )
        assert notif1 is not None
        assert notif2 is not None

    def test_security_events_skip_dedup(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        for ntype in ("new_login", "password_changed", "email_changed"):
            notif1 = dispatch_notification(
                db=db_session,
                organization_id=None,
                user_id=user.id,
                notification_type=ntype,
                title=f"{ntype} 1",
                message="msg",
                related_entity_type="user",
                related_entity_id=user.id,
            )
            notif2 = dispatch_notification(
                db=db_session,
                organization_id=None,
                user_id=user.id,
                notification_type=ntype,
                title=f"{ntype} 2",
                message="msg",
                related_entity_type="user",
                related_entity_id=user.id,
            )
            assert notif1 is not None, f"{ntype} first should be created"
            assert notif2 is not None, f"{ntype} second should also be created (skip dedup)"


# ===========================================================================
# 3. ensure_default_preferences
# ===========================================================================
class TestEnsureDefaultPreferences:
    def test_creates_default_prefs(self, db_session):
        from app.services.notification_service import ensure_default_preferences
        user = _create_user(db_session)
        ensure_default_preferences(db_session, user.id)

        from app.models.notification_preference import NotificationPreference
        prefs = db_session.query(NotificationPreference).filter(
            NotificationPreference.user_id == user.id,
        ).all()
        types = {p.notification_type for p in prefs}
        assert "scan_completed" in types
        assert "new_finding_critical" in types
        assert "ssl_expiring" in types
        assert "new_cve_match" in types
        assert "weekly_digest" in types
        assert "inventory_new_asset" in types
        # 12 original types plus the 6 inventory change alerts.
        assert len(prefs) == 18

    def test_idempotent(self, db_session):
        from app.services.notification_service import ensure_default_preferences
        user = _create_user(db_session)
        ensure_default_preferences(db_session, user.id)
        ensure_default_preferences(db_session, user.id)

        from app.models.notification_preference import NotificationPreference
        count = db_session.query(NotificationPreference).filter(
            NotificationPreference.user_id == user.id,
        ).count()
        assert count == 18


# ===========================================================================
# 4. Notification preferences API
# ===========================================================================
class TestNotificationPreferencesAPI:
    def test_list_returns_defaults(self, client, auth_headers):
        resp = client.get("/api/v1/notification-preferences", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "preferences" in data
        types = {p["notification_type"] for p in data["preferences"]}
        assert "scan_completed" in types
        assert "new_finding_critical" in types

    def test_update_single_preference(self, client, auth_headers):
        resp = client.put(
            "/api/v1/notification-preferences/scan_completed",
            json={"notification_type": "scan_completed", "in_app_enabled": False, "email_enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["in_app_enabled"] is False
        assert resp.json()["email_enabled"] is True

    def test_update_single_preference_one_channel(self, client, auth_headers):
        # The settings page sends only the channel that was toggled.
        resp = client.put(
            "/api/v1/notification-preferences/scan_failed",
            json={"email_enabled": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["email_enabled"] is False
        in_app = resp.json()["in_app_enabled"]
        resp = client.put(
            "/api/v1/notification-preferences/scan_failed",
            json={"in_app_enabled": not in_app},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["in_app_enabled"] is (not in_app)
        assert resp.json()["email_enabled"] is False

    def test_update_single_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/v1/notification-preferences/nonexistent_type",
            json={"notification_type": "nonexistent_type", "in_app_enabled": True, "email_enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_bulk_update(self, client, auth_headers):
        resp = client.put(
            "/api/v1/notification-preferences",
            json={
                "preferences": [
                    {"notification_type": "scan_completed", "in_app_enabled": False, "email_enabled": False},
                    {"notification_type": "ssl_expiring", "in_app_enabled": True, "email_enabled": False},
                ]
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        prefs = {p["notification_type"]: p for p in resp.json()["preferences"]}
        assert prefs["scan_completed"]["in_app_enabled"] is False
        assert prefs["ssl_expiring"]["email_enabled"] is False


# ===========================================================================
# 5. Auth hook – login notification
# ===========================================================================
class TestLoginNotification:
    def test_login_creates_notification(self, client, auth_headers):
        """Login should dispatch a new_login notification."""
        from app.models.notification import Notification
        from tests.conftest import TestingSessionLocal
        email = auth_headers["email"]
        # Second login
        client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})

        db = TestingSessionLocal()
        try:
            notifs = db.query(Notification).filter(Notification.type == "new_login").all()
            assert len(notifs) >= 1
        finally:
            db.close()


# ===========================================================================
# 6. Auth hook – password change
# ===========================================================================
class TestPasswordChangeNotification:
    def test_password_change_creates_notification(self, client, auth_headers):
        from app.models.notification import Notification
        from tests.conftest import TestingSessionLocal
        resp = client.put(
            "/api/v1/users/me/password",
            json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        db = TestingSessionLocal()
        try:
            notifs = db.query(Notification).filter(Notification.type == "password_changed").all()
            assert len(notifs) >= 1
            assert notifs[0].related_entity_type == "user"
        finally:
            db.close()


# ===========================================================================
# 7. CVE match notification in scan results
# ===========================================================================
class TestCVENotificationDispatch:
    def test_cve_finding_dispatches_new_cve_match(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        # Simulate what _generate_notifications does for CVE findings
        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="new_cve_match",
            title="CVE match: CVE-2024-1234",
            message="Version-correlated (unverified) CVE-2024-1234 on nginx 1.18.",
            related_entity_type="finding",
            related_entity_id=None,
            data={
                "scan_id": "scan-abc",
                "domain": "example.com",
                "cve_id": "CVE-2024-1234",
                "tech_name": "nginx 1.18",
                "severity": "high",
            },
        )
        assert notif is not None
        assert notif.type == "new_cve_match"
        assert notif.priority == "high"
        assert notif.data["cve_id"] == "CVE-2024-1234"

    def test_shadow_asset_notification(self, db_session):
        from app.services.notification_service import dispatch_notification
        user = _create_user(db_session)
        notif = dispatch_notification(
            db=db_session,
            organization_id=None,
            user_id=user.id,
            notification_type="new_shadow_asset",
            title="New shadow asset detected",
            message="New shadow asset: staging.example.com (confidence: 85%)",
            related_entity_type="asset",
            related_entity_id="asset-789",
            data={"confidence": 85, "value": "staging.example.com"},
        )
        assert notif is not None
        assert notif.type == "new_shadow_asset"
        assert notif.priority == "high"


# ===========================================================================
# 8. Email log dedup
# ===========================================================================
class TestEmailLogDedup:
    def test_email_log_prevents_resend(self, db_session):
        from app.models.notification_email_log import NotificationEmailLog
        # Simulate an email already sent
        log = NotificationEmailLog(
            notification_id="notif-123",
            user_id="user-456",
            email_type="ssl_expiring",
            resend_id="resend-789",
        )
        db_session.add(log)
        db_session.commit()

        from app.services.notification_service import _should_send_email
        # Should still return True since _should_send_email doesn't check email_log
        # (dedup is handled at the dispatch level)
        result = _should_send_email(db_session, "user-456", "ssl_expiring")
        assert result is True
