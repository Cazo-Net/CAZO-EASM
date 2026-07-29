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
    ADMIN_JWT_SECRET: str = os.getenv("ADMIN_JWT_SECRET", "admin-panel-secret-change-in-production")
    ADMIN_JWT_ALGORITHM: str = "HS256"
    ADMIN_JWT_EXPIRE_MINUTES: int = 60

    # Admin credentials (override via env in production)
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@cazo.io")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3001", "http://localhost:9000"]

    # Pool settings (lightweight - admin panel has few concurrent users)
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
