"""CAZO Admin Panel - Standalone backend on port 9000.

Connects to the EASM platform database (read-only by default).
Separate JWT secret for admin authentication.
"""

from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    APP_NAME: str = "CAZO Admin Panel"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # EASM platform database (read by default, write only for admin actions)
    EASM_DATABASE_URL: str = os.getenv(
        "EASM_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/easm"
    )
    EASM_SQLITE_PATH: str = os.getenv(
        "EASM_SQLITE_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "backend", "data", "easm.db")
    )
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "true").lower() in ("1", "true", "yes")

    # Admin panel own auth (separate from EASM)
    # No usable default: an unset secret is replaced by a random one at startup
    # (admin sessions then end on restart). The old hard-coded default let
    # anyone forge admin tokens.
    ADMIN_JWT_SECRET: str = os.getenv("ADMIN_JWT_SECRET", "")
    ADMIN_JWT_ALGORITHM: str = "HS256"
    ADMIN_JWT_EXPIRE_MINUTES: int = 60

    # Admin credentials (override via env in production)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@cazo.io")
    # Optional fallback login. Normally the admin signs in with a database
    # superuser (backend: python -m app.utils.create_admin). The fallback is
    # ignored while this is empty, a known default, or shorter than 12 chars.
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3001", "http://localhost:9000"]

    # Pool settings (lightweight - admin panel has few concurrent users)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

_WEAK_JWT_SECRETS = {"", "admin-panel-secret-change-in-production", "change-me", "secret"}
if settings.ADMIN_JWT_SECRET in _WEAK_JWT_SECRETS:
    import secrets as _secrets
    settings.ADMIN_JWT_SECRET = _secrets.token_hex(32)

WEAK_ADMIN_PASSWORDS = {"", "admin123", "admin", "password", "changeme", "change-me"}
