from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import json
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AttackSec"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/easm"
    DATABASE_ECHO: bool = False
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    # SQLite for development. Kept under ./data to match the Docker volume layout
    # (see backend/Dockerfile and backend/.env.example).
    SQLITE_URL: str = "sqlite:///./data/easm.db"
    USE_SQLITE: bool = True

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # API Keys
    API_KEY_PREFIX: str = "easm_"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Redis (used for Celery broker/result and distributed rate limiting)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL: Optional[str] = os.getenv("CELERY_BROKER_URL", "")
    CELERY_RESULT_BACKEND: Optional[str] = os.getenv("CELERY_RESULT_BACKEND", "")
    USE_CELERY: bool = os.getenv("USE_CELERY", "false").lower() in ("1", "true", "yes")

    # Scanner settings
    SUBFINDER_PATH: str = "subfinder"
    NMAP_PATH: str = "nmap"
    NUCLEI_PATH: str = "nuclei"
    SCAN_TIMEOUT: int = 300
    MAX_CONCURRENT_SCANS: int = 5

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
    RATE_LIMIT_PER_MINUTE: int = 60

    # File storage
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports"

    # Email
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "log")  # log | smtp | resend
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@attacksec.io")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    # Frontend base URL (for links in emails, invitations, etc.)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # AI Settings
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.7"))
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "2048"))

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Allow CORS_ORIGINS to be provided as a JSON string or comma list via env
        raw = os.getenv("CORS_ORIGINS")
        if raw:
            self.CORS_ORIGINS = _parse_origins(raw)


def _parse_origins(raw: str) -> List[str]:
    raw = raw.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(o).strip() for o in parsed if str(o).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()


def is_production() -> bool:
    return settings.ENVIRONMENT.lower() in ("production", "prod")


# Secret handling:
# - In production: secrets are REQUIRED. Fail fast instead of generating ephemeral
#   keys that would differ across replicas and invalidate all JWTs on restart.
# - In development: auto-generate for convenience.
if is_production():
    missing = [
        name for name in ("SECRET_KEY", "JWT_SECRET_KEY")
        if not getattr(settings, name)
    ]
    if missing:
        raise RuntimeError(
            f"Missing required secret(s) in production: {', '.join(missing)}. "
            "Set them via environment variables or a secrets manager."
        )
    if settings.USE_SQLITE:
        raise RuntimeError(
            "SQLite is not supported in production. Set USE_SQLITE=false and "
            "configure DATABASE_URL to a PostgreSQL instance."
        )
else:
    if not settings.SECRET_KEY:
        settings.SECRET_KEY = secrets.token_hex(32)
    if not settings.JWT_SECRET_KEY:
        settings.JWT_SECRET_KEY = secrets.token_hex(32)


def get_database_url() -> str:
    """Get database URL based on configuration."""
    if settings.USE_SQLITE:
        return settings.SQLITE_URL
    return settings.DATABASE_URL


def get_celery_broker_url() -> str:
    return settings.CELERY_BROKER_URL or settings.REDIS_URL or "redis://localhost:6379/0"


def get_celery_result_backend() -> str:
    return settings.CELERY_RESULT_BACKEND or settings.REDIS_URL or "redis://localhost:6379/1"


def frontend_url(path: str = "") -> str:
    """Build an absolute frontend URL from the configured FRONTEND_URL.

    Used for links embedded in transactional emails (verification, password
    reset, invitations) so they point at the real deployment, not localhost.
    """
    base = (getattr(settings, "FRONTEND_URL", "") or "http://localhost:3000").rstrip("/")
    if not path:
        return base
    return f"{base}/{str(path).lstrip('/')}"
