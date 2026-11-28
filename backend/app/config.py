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

    # Database — production-grade for 1M+ users
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/easm"
    DATABASE_ECHO: bool = False
    # Read replica (optional — routes all reads here when set)
    DATABASE_READ_URL: Optional[str] = None
    # Connection pool — tuned for ~320 concurrent requests (4 workers × 80 each)
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "32"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "48"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "15"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "900"))
    DB_POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() in ("1", "true", "yes")
    DB_STATEMENT_CACHE_SIZE: int = int(os.getenv("DB_STATEMENT_CACHE_SIZE", "1000"))
    DB_PREPARED_STATEMENT_CACHE_SIZE: int = int(os.getenv("DB_PREPARED_STATEMENT_CACHE_SIZE", "100"))
    # Table partitioning (for scans, vulnerabilities, assets on large deployments)
    DB_PARTITION_ENABLED: bool = os.getenv("DB_PARTITION_ENABLED", "false").lower() in ("1", "true", "yes")

    # SQLite for development. Kept under ./data to match the Docker volume layout
    # (see backend/Dockerfile and backend/.env.example).
    SQLITE_URL: str = "sqlite:///./data/easm.db"
    USE_SQLITE: bool = True

    # JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    # Key that signs the audit log chain. Empty = derived from SECRET_KEY.
    # Changing either one makes older audit entries fail verification, so set
    # it once and keep it.
    AUDIT_LOG_KEY: str = os.getenv("AUDIT_LOG_KEY", "")
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
    NMAP_PATH: str = os.getenv("NMAP_PATH", "nmap")
    # When true, "full" port scans use the bundled nmap binary (real -sV
    # service/version fingerprinting + optional -O OS detection). When false
    # or nmap is unavailable, the pure-Python connect scanner is used.
    USE_NMAP: bool = os.getenv("USE_NMAP", "true").lower() in ("1", "true", "yes")
    NMAP_TIMEOUT: int = int(os.getenv("NMAP_TIMEOUT", "30"))
    NMAP_MAX_CONCURRENCY: int = int(os.getenv("NMAP_MAX_CONCURRENCY", "20"))
    NMAP_OS_DETECTION: bool = os.getenv("NMAP_OS_DETECTION", "false").lower() in ("1", "true", "yes")
    NMAP_TOP_PORTS: int = int(os.getenv("NMAP_TOP_PORTS", "100"))
    # Fast port scanner settings (replaces nmap for port discovery)
    FAST_SCAN_CONCURRENCY: int = int(os.getenv("FAST_SCAN_CONCURRENCY", "2000"))
    FAST_SCAN_CONNECT_TIMEOUT: float = float(os.getenv("FAST_SCAN_CONNECT_TIMEOUT", "0.5"))
    FAST_SCAN_BANNER_TIMEOUT: float = float(os.getenv("FAST_SCAN_BANNER_TIMEOUT", "1.0"))
    # RDAP (modern WHOIS replacement)
    RDAP_BASE_URL: str = os.getenv("RDAP_BASE_URL", "https://rdap.org")
    SCAN_TIMEOUT: int = 15
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
    # Proxies in front of the backend that append to X-Forwarded-For (see
    # app/core/client_ip.py). 0 = legacy: trust the left-most (spoofable) entry.
    TRUSTED_PROXY_HOPS: int = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))

    # Authorized-scope enforcement.
    # When True, an organization must have at least one matching AuthorizedScope
    # row before any discovery target is scanned. When False (dev default), orgs
    # with no scopes configured are implicitly authorized (legacy behavior).
    REQUIRE_EXPLICIT_SCOPE: bool = os.getenv("REQUIRE_EXPLICIT_SCOPE", "true").lower() in ("1", "true", "yes")
    # When True, matched scopes must also be `verified` (ownership proven) to
    # authorize a target. Defaults to False. Pair with a ScopeVerifier to prove it.
    REQUIRE_VERIFIED_SCOPE: bool = os.getenv("REQUIRE_VERIFIED_SCOPE", "false").lower() in ("1", "true", "yes")

    # Scan-time scope gate: "verified" | "registered" | "open". Empty means
    # "registered" in production and "open" elsewhere. See app/core/scope.py.
    SCOPE_ENFORCEMENT: str = os.getenv("SCOPE_ENFORCEMENT", "")

    # ── Scan execution ──────────────────────────────────────────────
    # "queue"  — durable scan_jobs table, run by scan workers (production default)
    # "inline" — run inside the API process (development default)
    # "celery" — legacy Celery task queue
    SCAN_EXECUTION_MODE: str = os.getenv("SCAN_EXECUTION_MODE", "")
    # Also run a scan worker inside the API process. On by default so a
    # single-service deploy keeps working; set to false once a dedicated
    # scan-worker service is running (docker-compose and the Railway worker
    # config already do).
    RUN_EMBEDDED_WORKER: bool = os.getenv("RUN_EMBEDDED_WORKER", "true").lower() in ("1", "true", "yes")
    SCAN_WORKER_CONCURRENCY: int = int(os.getenv("SCAN_WORKER_CONCURRENCY", "3"))
    SCAN_MAX_RUNNING_PER_ORG: int = int(os.getenv("SCAN_MAX_RUNNING_PER_ORG", "2"))
    SCAN_MAX_ATTEMPTS: int = int(os.getenv("SCAN_MAX_ATTEMPTS", "2"))
    SCAN_RETRY_BASE_SECONDS: int = int(os.getenv("SCAN_RETRY_BASE_SECONDS", "60"))
    SCAN_JOB_STALE_SECONDS: int = int(os.getenv("SCAN_JOB_STALE_SECONDS", "300"))
    SCAN_HEARTBEAT_SECONDS: int = int(os.getenv("SCAN_HEARTBEAT_SECONDS", "30"))
    SCAN_TIMEOUT_QUICK_MINUTES: int = int(os.getenv("SCAN_TIMEOUT_QUICK_MINUTES", "10"))
    SCAN_TIMEOUT_FULL_MINUTES: int = int(os.getenv("SCAN_TIMEOUT_FULL_MINUTES", "45"))
    # Scan depth (app/scanners/v2/profiles.py). Full scans use "standard";
    # a scan can ask for "deep" through scan_options.depth.
    # Optional open-source tools, used only when the binary is installed.
    # nuclei stays off until the person running the platform turns it on;
    # it runs non-intrusive templates only (see external_tools.py).
    SCAN_ENABLE_NUCLEI: bool = os.getenv("SCAN_ENABLE_NUCLEI", "false").lower() in ("1", "true", "yes")
    NUCLEI_RATE_LIMIT: int = int(os.getenv("NUCLEI_RATE_LIMIT", "10"))
    SCAN_ENABLE_SUBFINDER: bool = os.getenv("SCAN_ENABLE_SUBFINDER", "true").lower() in ("1", "true", "yes")
    # Periodic jobs (scheduled scans, SSL expiry, weekly digest, CVE sync)
    # run inside scan workers; turn off if you run Celery beat instead.
    RUN_PERIODIC_TASKS: bool = os.getenv("RUN_PERIODIC_TASKS", "true").lower() in ("1", "true", "yes")

    # Caching
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() in ("1", "true", "yes")

    # File storage
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reports"

    # Email
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "log")  # log | smtp | resend
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@cazo.io")
    # Support chat: where the team is told about new customer messages
    # (comma-separated addresses). Empty = no email, messages still reach the
    # admin panel inbox.
    SUPPORT_NOTIFY_EMAIL: str = os.getenv("SUPPORT_NOTIFY_EMAIL", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    # Blockchain Intelligence
    ETHERSCAN_API_KEY: str = os.getenv("ETHERSCAN_API_KEY", "")

    # Dark web & threat intelligence sources. Each one is optional: a source
    # without its key shows as "not configured" instead of returning results.
    # Have I Been Pwned (https://haveibeenpwned.com/API/Key) — breached
    # accounts and domain search. Domain search also needs the domain verified
    # in the HIBP dashboard.
    HIBP_API_KEY: str = os.getenv("HIBP_API_KEY", "")
    # abuse.ch Auth-Key (https://auth.abuse.ch/) — URLhaus and ThreatFox.
    ABUSECH_AUTH_KEY: str = os.getenv("ABUSECH_AUTH_KEY", "")
    # How often saved monitors are re-checked by the worker.
    THREAT_INTEL_CHECK_HOURS: int = int(os.getenv("THREAT_INTEL_CHECK_HOURS", "24"))

    # Neo4j (Phase 2: graph analytics)
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # OpenSearch (Phase 5: blockchain search)
    OPENSEARCH_HOSTS: str = os.getenv("OPENSEARCH_HOSTS", "https://localhost:9200")
    OPENSEARCH_USER: str = os.getenv("OPENSEARCH_USER", "admin")
    OPENSEARCH_PASSWORD: str = os.getenv("OPENSEARCH_PASSWORD", "EasmAdmin123!")
    OPENSEARCH_VERIFY_CERTS: bool = os.getenv("OPENSEARCH_VERIFY_CERTS", "false").lower() in ("1", "true", "yes")

    # Billing (Stripe). Leave STRIPE_SECRET_KEY empty to disable checkout;
    # plans and limits still apply. Live keys (sk_live_/rk_live_) are refused
    # unless BILLING_ALLOW_LIVE_KEYS=true, so a test deploy can never charge.
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    BILLING_ALLOW_LIVE_KEYS: bool = os.getenv("BILLING_ALLOW_LIVE_KEYS", "false").lower() in ("1", "true", "yes")
    # Currency for prices and checkout (lowercase ISO code). Prices for any
    # currency other than "usd" must be supplied via BILLING_PLANS_JSON.
    BILLING_CURRENCY: str = os.getenv("BILLING_CURRENCY", "usd").lower()
    # Optional JSON overrides for the plan catalog (prices, limits); see app/billing/plans.py.
    BILLING_PLANS_JSON: str = os.getenv("BILLING_PLANS_JSON", "")
    # Enforce plan limits (root domains, hosts, scans, users) in the API.
    BILLING_ENFORCE_LIMITS: bool = os.getenv("BILLING_ENFORCE_LIMITS", "true").lower() in ("1", "true", "yes")
    # Days a past-due or just-expired plan keeps working before limits fall back.
    BILLING_GRACE_DAYS: int = int(os.getenv("BILLING_GRACE_DAYS", "7"))
    # Let Stripe Tax calculate tax (e.g. Malaysian SST) at checkout. Needs Stripe
    # Tax set up with your tax registrations in the Stripe Dashboard first.
    BILLING_AUTOMATIC_TAX: bool = os.getenv("BILLING_AUTOMATIC_TAX", "false").lower() in ("1", "true", "yes")

    # Frontend base URL (for links in emails, invitations, etc.)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # Google OAuth
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    PASSWORD_EXPIRY_DAYS: int = int(os.getenv("PASSWORD_EXPIRY_DAYS", "90"))

    # Sentry
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_TRACES_SAMPLE_RATE: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    SENTRY_PROFILES_SAMPLE_RATE: float = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))

    # Upstash Redis
    UPSTASH_REDIS_URL: str = os.getenv("UPSTASH_REDIS_URL", "")
    UPSTASH_REDIS_TOKEN: str = os.getenv("UPSTASH_REDIS_TOKEN", "")

    # Upstash QStash
    QSTASH_CURRENT_SIGNING_KEY: str = os.getenv("QSTASH_CURRENT_SIGNING_KEY", "")
    QSTASH_NEXT_SIGNING_KEY: str = os.getenv("QSTASH_NEXT_SIGNING_KEY", "")
    QSTASH_TOKEN: str = os.getenv("QSTASH_TOKEN", "")

    # Upstash Kafka
    UPSTASH_KAFKA_URL: str = os.getenv("UPSTASH_KAFKA_URL", "")
    UPSTASH_KAFKA_USERNAME: str = os.getenv("UPSTASH_KAFKA_USERNAME", "")
    UPSTASH_KAFKA_PASSWORD: str = os.getenv("UPSTASH_KAFKA_PASSWORD", "")

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


def normalize_postgres_url(url: str) -> str:
    """Pin plain Postgres URLs to the psycopg2 driver.

    SQLAlchemy 2.1 maps ``postgresql://`` to psycopg 3, which is not installed
    (requirements ship psycopg2-binary). Hosting providers such as Railway and
    Heroku also hand out ``postgres://`` URLs, which SQLAlchemy rejects.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def get_database_url() -> str:
    """Get database URL based on configuration."""
    if settings.USE_SQLITE:
        return settings.SQLITE_URL
    return normalize_postgres_url(settings.DATABASE_URL)


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
