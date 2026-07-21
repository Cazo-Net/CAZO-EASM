"""Live end-to-end test: Google OAuth silent linking fix.

Confirms that signing in with Google using an email that matches an existing
password-based account returns HTTP 409, not a silent account takeover.
"""
import pytest
from unittest.mock import patch


FAKE_GOOGLE_PAYLOAD = {
    "sub": "google-user-id-12345",
    "email": "oauth_collision@test.com",
    "name": "OAuth Attacker",
}


class TestGoogleOAuthSilentLinkingBlock:
    """Verify the fix for the Google OAuth account takeover vector."""

    def test_password_account_blocks_google_link(self, client, db_session):
        """Existing password account -> Google OAuth same email -> 409."""
        # Step 1: Create a password-based account
        resp = client.post("/api/v1/auth/register", json={
            "email": "oauth_collision@test.com",
            "password": "LegitUser1!",
            "full_name": "Legitimate User",
        })
        assert resp.status_code == 200, f"Register failed: {resp.text}"
        user_id = resp.json()["id"]

        # Step 2: Attempt Google OAuth sign-in with the same email
        with patch(
            "app.api.v1.auth_google.verify_google_credential",
            return_value=FAKE_GOOGLE_PAYLOAD,
        ):
            resp = client.post("/api/v1/auth/google", json={
                "credential": "fake-google-token",
            })

        # Step 3: Assert 409 CONFLICT — NOT a silent login
        assert resp.status_code == 409, (
            f"Expected 409 but got {resp.status_code}: {resp.text}"
        )
        detail = resp.json()["detail"]
        assert "already exists" in detail.lower(), f"Unexpected detail: {detail}"
        assert "Account Settings" in detail, f"Missing guidance in: {detail}"

        # Step 4: Confirm the original user was NOT modified
        from app.models.user import User
        user = db_session.query(User).filter(User.id == user_id).first()
        assert user.google_id is None, "google_id was set — account was silently linked!"
        assert user.email_verified is False or user.email_verified is True  # unchanged from registration state
        assert not user.hashed_password.startswith("GOOGLE_OAUTH:"), "Password hash was overwritten!"

    def test_google_only_account_allows_link(self, client, db_session):
        """Existing Google-only account -> Google OAuth same email -> 200 (link succeeds)."""
        from app.models.user import User
        from app.core.security import create_access_token

        # Step 1: Create a Google-only account (no password)
        user = User(
            email="google_only@test.com",
            full_name="Google User",
            google_id="original-google-id",
            email_verified=True,
            hashed_password="GOOGLE_OAUTH:sentinel",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Step 2: Google OAuth with the same email but different google_id
        fake_payload = {
            "sub": "new-google-id-67890",
            "email": "google_only@test.com",
            "name": "Google User",
        }
        with patch(
            "app.api.v1.auth_google.verify_google_credential",
            return_value=fake_payload,
        ):
            resp = client.post("/api/v1/auth/google", json={
                "credential": "fake-google-token",
            })

        # Step 3: Should succeed — Google-only accounts can be linked
        assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}: {resp.text}"
        assert "access_token" in resp.json()

        # Step 4: Confirm google_id was updated
        db_session.refresh(user)
        assert user.google_id == "new-google-id-67890", "google_id was not updated"

    def test_new_google_user_creates_account(self, client, db_session):
        """Unknown email -> Google OAuth -> 200 (new account created)."""
        with patch(
            "app.api.v1.auth_google.verify_google_credential",
            return_value=FAKE_GOOGLE_PAYLOAD,
        ):
            resp = client.post("/api/v1/auth/google", json={
                "credential": "fake-google-token",
            })

        assert resp.status_code == 200, f"Expected 200 but got {resp.text}"
        data = resp.json()
        assert "access_token" in data

        # Verify user was created
        from app.models.user import User
        user = db_session.query(User).filter(User.email == "oauth_collision@test.com").first()
        assert user is not None, "User was not created"
        assert user.google_id == "google-user-id-12345"
        assert user.hashed_password.startswith("GOOGLE_OAUTH:")
