class TestRegister:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@test.com",
                "password": "StrongPass1!",
                "full_name": "New User",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "new@test.com"
        assert data["full_name"] == "New User"
        assert data["role"] == "member"
        assert "id" in data

    def test_register_duplicate_email(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "StrongPass1!",
                "full_name": "User",
            },
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "StrongPass1!",
                "full_name": "User 2",
            },
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_register_weak_password(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weak@test.com",
                "password": "weak",
                "full_name": "Weak",
            },
        )
        assert resp.status_code == 422

    def test_register_no_uppercase(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "no@test.com",
                "password": "nouppercase1!",
                "full_name": "No Upper",
            },
        )
        assert resp.status_code == 422

    def test_register_no_special_char(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "nospecial@test.com",
                "password": "NoSpecial1",
                "full_name": "No Special",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@test.com",
                "password": "LoginPass1!",
                "full_name": "Login User",
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "LoginPass1!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrong@test.com",
                "password": "CorrectPass1!",
                "full_name": "Wrong User",
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@test.com", "password": "WrongPass1!"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@test.com", "password": "GhostPass1!"},
        )
        assert resp.status_code == 401


class TestRefreshToken:
    def test_refresh_success(self, client):
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh@test.com",
                "password": "RefreshPass1!",
                "full_name": "Refresh User",
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"email": "refresh@test.com", "password": "RefreshPass1!"},
        )
        refresh_token = login_resp.json()["refresh_token"]
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401


class TestGetMe:
    def test_get_me_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == auth_headers["email"]

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
