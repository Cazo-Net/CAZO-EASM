from pydantic_settings import BaseSettings
from typing import Optional, List
import os
import json
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CAZO EASM"
    APP_VERSION: str = "1.0.5"
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
    NMAP_PATH: str = "nmap"
    SCAN_TIMEOUT: int = 30
    MAX_CONCURRENT_SCANS: int = 5

    # Scan profiles/settings
    SCAN_SMALL_MAX_SUBDOMAINS: int = 20
    SCAN_LARGE_MAX_SUBDOMAINS: int = 1000
    SCAN_DEFAULT_PORTS: List[int] = [80, 443, 8080, 8443]
    SCAN_QUICK_PORTS: List[int] = [80, 443]
    SCAN_TOP_PORTS: int = 1000

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
    RATE_LIMIT_PER_MINUTE: int = 60

    # Authorized-scope enforcement.
    # When True, an organization must have at least one matching AuthorizedScope
    # row before any discovery target is scanned. When False (dev default), orgs
    # with no scopes configured are implicitly authorized (legacy behavior).
    REQUIRE_EXPLICIT_SCOPE: bool = os.getenv("REQUIRE_EXPLICIT_SCOPE", "true").lower() in ("1", "true", "yes")
    # When True, matched scopes must also be `verified` (ownership proven) to
    # authorize a target. Defaults to False. Pair with a ScopeVerifier to prove it.
    REQUIRE_VERIFIED_SCOPE: bool = os.getenv("REQUIRE_VERIFIED_SCOPE", "false").lower() in ("1", "true", "yes")

    # Caching
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")

    # File storage
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports"

    # Email
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "log")  # log | smtp | resend
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@cazo.io")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    # Frontend base URL (for links in emails, invitations, etc.)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # AI Settings (supports multiple keys for rotation)
    AI_API_KEYS: str = os.getenv("AI_API_KEYS", "")  # Comma-separated keys
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")  # Single key fallback
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.7"))
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "2048"))
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "openai")  # openai | anthropic | ollama | stub

    # Anthropic provider settings
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

    # Ollama (local) provider settings
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    # Stripe / Billing
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_STARTER: str = os.getenv("STRIPE_PRICE_STARTER", "")
    STRIPE_PRICE_PROFESSIONAL: str = os.getenv("STRIPE_PRICE_PROFESSIONAL", "")
    STRIPE_PRICE_ENTERPRISE: str = os.getenv("STRIPE_PRICE_ENTERPRISE", "")

    # Subscription / Billing
    TRIAL_DURATION_DAYS: int = int(os.getenv("TRIAL_DURATION_DAYS", "14"))
    GRACE_PERIOD_DAYS: int = int(os.getenv("GRACE_PERIOD_DAYS", "7"))
    PASSWORD_EXPIRY_DAYS: int = int(os.getenv("PASSWORD_EXPIRY_DAYS", "90"))

    def get_ai_api_keys(self) -> list[str]:
        """Get list of AI API keys (supports rotation)."""
        keys = []
        if self.AI_API_KEYS:
            keys = [k.strip() for k in self.AI_API_KEYS.split(",") if k.strip()]
        if not keys and self.AI_API_KEY:
            keys = [self.AI_API_KEY]
        return keys

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
    # Development convenience: auto-generate any missing secrets, but PERSIST them
    # so they stay stable across restarts and separate processes. Ephemeral keys
    # would silently invalidate every JWT session on each reload.
    _generated: dict[str, str] = {}
    if not settings.SECRET_KEY:
        settings.SECRET_KEY = secrets.token_hex(32)
        _generated["SECRET_KEY"] = settings.SECRET_KEY
    if not settings.JWT_SECRET_KEY:
        settings.JWT_SECRET_KEY = secrets.token_hex(32)
        _generated["JWT_SECRET_KEY"] = settings.JWT_SECRET_KEY

    if _generated:
        _env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        try:
            if os.path.exists(_env_path):
                with open(_env_path, "r", encoding="utf-8") as _fh:
                    _lines = _fh.readlines()
            else:
                _lines = []

            _remaining = dict(_generated)
            for _i, _line in enumerate(_lines):
                for _key in list(_remaining):
                    # Replace an empty `KEY=` (or `KEY= `) assignment in place.
                    if _line.strip() == f"{_key}=" or _line.rstrip("\n").strip() == f"{_key}=":
                        _lines[_i] = f"{_key}={_remaining.pop(_key)}\n"
            # Append any keys that weren't present at all.
            for _key, _val in _remaining.items():
                if _lines and not _lines[-1].endswith("\n"):
                    _lines[-1] += "\n"
                _lines.append(f"{_key}={_val}\n")

            with open(_env_path, "w", encoding="utf-8") as _fh:
                _fh.writelines(_lines)
        except OSError:
            # If we can't persist (read-only FS, etc.), fall back to the in-memory
            # keys for this process — sessions just won't survive a restart.
            pass


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
