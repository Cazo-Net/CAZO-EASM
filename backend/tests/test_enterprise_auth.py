from datetime import datetime, timezone, timedelta


class TestBruteForceProtection:
    def test_lockout_after_5_failed_attempts(self, client):
        client.post("/api/v1/auth/register", json={
            "email": "lock@test.com", "password": "LockPass1!", "full_name": "Lock User",
        })
        for i in range(5):
            client.post("/api/v1/auth/login", json={
                "email": "lock@test.com", "password": "WrongPass1!",
            })
        resp = client.post("/api/v1/auth/login", json={
            "email": "lock@test.com", "password": "LockPass1!",
        })
        assert resp.status_code == 423
        assert "locked" in resp.json()["detail"].lower()

    def test_successful_login_resets_failed_attempts(self, client):
        client.post("/api/v1/auth/register", json={
            "email": "reset@test.com", "password": "ResetPass1!", "full_name": "Reset User",
        })
        for _ in range(3):
            client.post("/api/v1/auth/login", json={
                "email": "reset@test.com", "password": "WrongPass1!",
            })
        resp = client.post("/api/v1/auth/login", json={
            "email": "reset@test.com", "password": "ResetPass1!",
        })
        assert resp.status_code == 200


class TestEmailVerification:
    def test_register_sends_verification_token(self, client, db_session):
        resp = client.post("/api/v1/auth/register", json={
            "email": "verify@test.com", "password": "VerifyPass1!", "full_name": "Verify User",
        })
        assert resp.status_code == 200
        assert resp.json()["email_verified"] is False
        # verification_token is no longer returned in the response (security fix)
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "verify@test.com").first()
        assert user is not None
        assert user.verification_token is not None

    def test_verify_email_success(self, client, db_session):
        client.post("/api/v1/auth/register", json={
            "email": "v2@test.com", "password": "V2Pass1!", "full_name": "V2 User",
        })
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "v2@test.com").first()
        token = user.verification_token
        resp = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert resp.status_code == 200

    def test_verify_email_invalid_token(self, client):
        resp = client.post("/api/v1/auth/verify-email", json={"token": "bad-token"})
        assert resp.status_code == 400


class TestPasswordResetFlow:
    def test_forgot_password_sends_email(self, client):
        client.post("/api/v1/auth/register", json={
            "email": "forgot@test.com", "password": "ForgotPass1!", "full_name": "Forgot User",
        })
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "forgot@test.com"})
        assert resp.status_code == 200

    def test_forgot_password_nonexistent_email(self, client):
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@test.com"})
        assert resp.status_code == 200

    def test_reset_password_success(self, client, db_session):
        from app.models.user import User
        from secrets import token_urlsafe

        client.post("/api/v1/auth/register", json={
            "email": "rst@test.com", "password": "RstPass1!", "full_name": "Rst User",
        })
        user = db_session.query(User).filter(User.email == "rst@test.com").first()
        user.reset_token = token_urlsafe(32)
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
        db_session.commit()

        resp = client.post("/api/v1/auth/reset-password", json={
            "token": user.reset_token, "new_password": "NewRstPass1!"
        })
        assert resp.status_code == 200

        resp = client.post("/api/v1/auth/login", json={
            "email": "rst@test.com", "password": "NewRstPass1!"
        })
        assert resp.status_code == 200

    def test_reset_password_expired_token(self, client, db_session):
        from app.models.user import User
        from secrets import token_urlsafe

        client.post("/api/v1/auth/register", json={
            "email": "exp@test.com", "password": "ExpPass1!", "full_name": "Exp User",
        })
        user = db_session.query(User).filter(User.email == "exp@test.com").first()
        user.reset_token = token_urlsafe(32)
        user.reset_token_expires = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        resp = client.post("/api/v1/auth/reset-password", json={
            "token": user.reset_token, "new_password": "NewExpPass1!"
        })
        assert resp.status_code == 400


class TestTwoFactorAuth:
    def test_setup_2fa(self, client, auth_headers):
        resp = client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "provisioning_uri" in data
        assert "secret" not in data  # secret must NOT be returned in response

    def test_enable_2fa_with_valid_code(self, client, auth_headers, db_session):
        import pyotp
        client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        # Secret is stored server-side, retrieve from DB
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "test@test.com").first()
        totp = pyotp.TOTP(user.totp_secret)
        resp = client.post("/api/v1/auth/2fa/enable", json={"code": totp.now()}, headers=auth_headers)
        assert resp.status_code == 200

    def test_enable_2fa_with_invalid_code(self, client, auth_headers):
        client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        resp = client.post("/api/v1/auth/2fa/enable", json={"code": "000000"}, headers=auth_headers)
        assert resp.status_code == 400

    def test_disable_2fa(self, client, auth_headers, db_session):
        import pyotp
        client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "test@test.com").first()
        totp = pyotp.TOTP(user.totp_secret)
        client.post("/api/v1/auth/2fa/enable", json={"code": totp.now()}, headers=auth_headers)
        resp = client.post("/api/v1/auth/2fa/disable", json={"code": totp.now()}, headers=auth_headers)
        assert resp.status_code == 200

    def test_disable_2fa_not_enabled(self, client, auth_headers, db_session):
        import pyotp
        client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "test@test.com").first()
        totp = pyotp.TOTP(user.totp_secret)
        resp = client.post("/api/v1/auth/2fa/disable", json={"code": totp.now()}, headers=auth_headers)
        assert resp.status_code == 400


class TestSessions:
    def test_list_sessions(self, client, auth_headers):
        resp = client.get("/api/v1/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_revoke_session(self, client, auth_headers):
        sessions = client.get("/api/v1/sessions", headers=auth_headers).json()
        assert len(sessions) >= 1
        session_id = sessions[0]["id"]
        resp = client.delete(f"/api/v1/sessions/{session_id}", headers=auth_headers)
        assert resp.status_code == 200

    def test_revoke_all_sessions(self, client, auth_headers):
        resp = client.delete("/api/v1/sessions", headers=auth_headers)
        assert resp.status_code == 200


class TestInvitations:
    def _create_org(self, client, auth_headers):
        client.post("/api/v1/organizations", json={"name": "Test Org"}, headers=auth_headers)

    def _admin_headers(self, client, db_session):
        """Create an admin user with INVITE_USERS permission."""
        from app.models.user import User
        from app.core.security import get_password_hash, create_access_token
        admin = User(email="invadmin@test.com", hashed_password=get_password_hash("Admin1!"), role="admin")
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        token = create_access_token(data={"sub": admin.id, "role": admin.role})
        return {"Authorization": f"Bearer {token}"}

    def test_create_invitation(self, client, db_session):
        headers = self._admin_headers(client, db_session)
        client.post("/api/v1/organizations", json={"name": "Test Org"}, headers=headers)
        resp = client.post("/api/v1/invitations", json={
            "email": "invite@test.com", "role": "member"
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "invite@test.com"

    def test_list_invitations(self, client, db_session):
        headers = self._admin_headers(client, db_session)
        client.post("/api/v1/organizations", json={"name": "Test Org"}, headers=headers)
        client.post("/api/v1/invitations", json={
            "email": "list@test.com", "role": "member"
        }, headers=headers)
        resp = client.get("/api/v1/invitations", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_create_invitation_no_org(self, client, db_session):
        from app.models.user import User
        from app.core.security import get_password_hash, create_access_token

        # Use admin role so RBAC passes; the 400 tests the org-check, not permission
        user = User(email="noorg@test.com", hashed_password=get_password_hash("NoOrg1!"), role="admin")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = create_access_token(data={"sub": user.id, "role": user.role})
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/v1/invitations", json={
            "email": "test@test.com", "role": "member"
        }, headers=headers)
        assert resp.status_code == 400


class TestAdminEndpoints:
    def _make_admin(self, client, db_session):
        from app.models.user import User
        from app.core.security import get_password_hash, create_access_token

        # Use superuser role to bypass org-scoping (test users have no org)
        admin = User(email="admin@test.com", hashed_password=get_password_hash("Admin1!"), role="superuser")
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        token = create_access_token(data={"sub": admin.id, "role": admin.role})
        return {"Authorization": f"Bearer {token}"}

    def test_admin_list_users(self, client, db_session):
        admin_headers = self._make_admin(client, db_session)
        client.post("/api/v1/auth/register", json={
            "email": "u1@test.com", "password": "User1Pass!", "full_name": "U1",
        })
        resp = client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_non_admin_cannot_list_users(self, client, auth_headers):
        resp = client.get("/api/v1/admin/users", headers=auth_headers)
        assert resp.status_code == 403

    def test_admin_disable_user(self, client, db_session):
        admin_headers = self._make_admin(client, db_session)
        reg = client.post("/api/v1/auth/register", json={
            "email": "dis@test.com", "password": "DisPass1!", "full_name": "Dis User",
        })
        user_id = reg.json()["id"]
        resp = client.put(f"/api/v1/admin/users/{user_id}/disable", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_enable_user(self, client, db_session):
        admin_headers = self._make_admin(client, db_session)
        reg = client.post("/api/v1/auth/register", json={
            "email": "ena@test.com", "password": "EnaPass1!", "full_name": "Ena User",
        })
        user_id = reg.json()["id"]
        client.put(f"/api/v1/admin/users/{user_id}/disable", headers=admin_headers)
        resp = client.put(f"/api/v1/admin/users/{user_id}/enable", headers=admin_headers)
        assert resp.status_code == 200

    def test_admin_unlock_user(self, client, db_session):
        admin_headers = self._make_admin(client, db_session)
        client.post("/api/v1/auth/register", json={
            "email": "unlock@test.com", "password": "Unlock1!", "full_name": "Unlock User",
        })
        for _ in range(5):
            client.post("/api/v1/auth/login", json={
                "email": "unlock@test.com", "password": "Wrong1!",
            })
        users = client.get("/api/v1/admin/users", headers=admin_headers).json()
        user_id = next(u["id"] for u in users if u["email"] == "unlock@test.com")
        resp = client.put(f"/api/v1/admin/users/{user_id}/unlock", headers=admin_headers)
        assert resp.status_code == 200

        resp = client.post("/api/v1/auth/login", json={
            "email": "unlock@test.com", "password": "Unlock1!",
        })
        assert resp.status_code == 200


class TestSecurityEndpoints:
    def test_generate_recovery_codes(self, client, auth_headers):
        resp = client.post("/api/v1/security/recovery-codes", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["codes"]) == 10

    def test_list_recovery_codes(self, client, auth_headers):
        client.post("/api/v1/security/recovery-codes", headers=auth_headers)
        resp = client.get("/api/v1/security/recovery-codes", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_list_trusted_devices(self, client, auth_headers):
        resp = client.get("/api/v1/security/trusted-devices", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_request_email_change(self, client, auth_headers):
        resp = client.post("/api/v1/security/change-email", json={
            "new_email": "newemail@test.com", "password": "TestPass123!"
        }, headers=auth_headers)
        assert resp.status_code == 200

    def test_request_email_change_wrong_password(self, client, auth_headers):
        resp = client.post("/api/v1/security/change-email", json={
            "new_email": "newemail2@test.com", "password": "WrongPass1!"
        }, headers=auth_headers)
        assert resp.status_code == 401
