from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
import secrets
import time
import logging

from app.config import settings, is_production
from app.database import init_db, write_engine
from app.core.rate_limit import get_rate_limiter
from app.core.logging import configure_logging
from app.services.platform_log import (
    log_unexpected, log_api_request, log_security_event,
    SEV_WARNING, SEV_ERROR,
)

logger = logging.getLogger("app.main")


# ---------------------------------------------------------------------------
# Sentry — init before FastAPI for proper auto-instrumentation
# ---------------------------------------------------------------------------
def _init_sentry() -> None:
    """Initialize Sentry SDK if a DSN is configured."""
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=f"easm@{settings.APP_VERSION}",
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            integrations=[
                FastApiIntegration(
                    enable_style_propagation=False,
                    request_hook=_sentry_request_hook,
                ),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            send_default_pii=False,
            attach_stacktrace=True,
            _experiments={"record_sql_params": True},
        )
        logger.info("Sentry initialized (dsn=%s…)", settings.SENTRY_DSN[:12])
    except Exception as exc:
        logger.warning("Sentry init failed: %s", exc)


def _sentry_request_hook(scope, hint):
    """Redact sensitive headers before sending to Sentry."""
    if "request" in scope:
        headers = scope["request"].get("headers", {})
        for sensitive in ("authorization", "cookie", "x-api-key"):
            if sensitive in headers:
                headers[sensitive] = "[redacted]"
    return scope


_init_sentry()

# Paths that must never be throttled (orchestrator liveness/readiness probes).
_PROBE_PATHS = {"/health", "/ready"}


def _client_ip(request: Request) -> str:
    from app.core.client_ip import get_client_ip
    return get_client_ip(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
    init_db()
    get_rate_limiter()
    _reap_stuck_scans()
    _configure_dns()

    # Scans run from the durable job queue. Scheduled scans and periodic
    # maintenance are run by scan workers, not by every API process.
    from app.services.scan_dispatch import execution_mode
    from app.core.scope import scope_mode
    from app.workers.scan_worker import start_embedded_worker, stop_embedded_worker
    _exec_mode = execution_mode()
    # The worker also runs schedules and maintenance, so it starts in every
    # execution mode; scheduled scans always go through the queue.
    _embedded = bool(settings.RUN_EMBEDDED_WORKER)
    if _embedded:
        await start_embedded_worker()
    logger.info(
        "Scan execution: mode=%s, embedded_worker=%s, scope_enforcement=%s",
        _exec_mode, _embedded, scope_mode(),
    )
    if _exec_mode == "queue" and not _embedded:
        logger.info("Scans are queued for external scan workers (python -m app.workers.scan_worker)")
    if scope_mode() == "open":
        logger.warning("SCOPE_ENFORCEMENT=open: any organization can scan any public target")

    # Initialize Neo4j graph database
    from app.blockchain.infrastructure.graph.neo4j_driver import driver as neo4j_driver
    from app.blockchain.infrastructure.graph.schema import initialize_schema
    from app.blockchain.application.connector_registry import register_defaults
    await neo4j_driver.initialize()
    await initialize_schema()
    register_defaults()

    # Initialize OpenSearch indices
    from app.blockchain.infrastructure.search.opensearch_client import client as os_client
    from app.blockchain.infrastructure.search.index_definitions import ensure_indices
    await os_client.initialize()
    ensure_indices()

    # Register default VASPs for Travel Rule compliance
    from app.blockchain.application.compliance import register_default_vasps
    register_default_vasps()

    # Start watchdog service
    from app.blockchain.application.watchdog import watchdog
    await watchdog.start()

    logger.info("Application started", extra={"environment": settings.ENVIRONMENT})
    yield

    # Stop watchdog + Neo4j + OpenSearch
    await watchdog.stop()
    await neo4j_driver.close()
    await os_client.close()

    # Stop the embedded scan worker (running jobs go back to the queue)
    await stop_embedded_worker()
    logger.info("Application shutting down")


def _configure_dns() -> None:
    """Configure dnspython to always use Google DNS first (system DNS has gaps)."""
    import dns.resolver
    default = dns.resolver.get_default_resolver()
    system_ns = list(default.nameservers)
    # Google DNS first, then system as fallback
    default.nameservers = ["8.8.8.8", "8.8.4.4"] + system_ns
    default.lifetime = 5
    logger.info("DNS configured: Google DNS primary, system fallback (%s)", system_ns)


def _reap_stuck_scans() -> None:
    """Mark scans left in running/pending after a process crash as failed.

    Background scans run in-process; if the server dies mid-scan the row is
    left dangling in ``running`` with a frozen progress. On startup we flip
    any such scan older than the timeout to ``failed`` so the UI stops showing
    it perpetually "in progress".
    """
    from app.database import SessionLocal
    from app.models.scan import Scan
    from app.services.scan_dispatch import execution_mode

    if execution_mode() == "queue":
        # Queued scans are owned by scan workers, which recover their own
        # dead jobs from heartbeats. Failing "old" running scans here would
        # kill healthy long scans whenever the API restarts.
        return

    timeout = timedelta(minutes=30)
    cutoff = datetime.now(timezone.utc) - timeout
    db = SessionLocal()
    try:
        stuck = (
            db.query(Scan)
            .filter(Scan.status.in_(["running", "pending"]))
            .filter(Scan.started_at < cutoff)
            .all()
        )
        for scan in stuck:
            scan.status = "failed"
            scan.error_message = "Scan interrupted (server restarted). Please re-run."
            scan.completed_at = datetime.now(timezone.utc)
        if stuck:
            db.commit()
            logger.warning(
                "Reaped %d stuck scan(s) left running before cutoff %s",
                len(stuck), cutoff.isoformat(),
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to reap stuck scans: %s", exc)
        db.rollback()
    finally:
        db.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# ---------------------------------------------------------------------------
# SECURITY: Global exception handler — strip stack traces and internal details
# from 500 responses in production to prevent information leakage.
# Also writes the full exception to platform_logs for admin analysis.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Capture in Sentry before returning generic error
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass
    try:
        log_unexpected(
            f"Unhandled exception: {exc}",
            exception=exc,
            request_id=request.headers.get("x-request-id"),
            client_ip=_client_ip(request),
            path=request.url.path,
            method=request.method,
            status_code=500,
        )
    except Exception:  # noqa: BLE001
        pass
    # Always return generic error — never leak exception details
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — distributed via Redis when available, uses X-Forwarded-For behind proxy
LOGIN_RATE_LIMIT = 10
GLOBAL_RATE_LIMIT = settings.RATE_LIMIT_PER_MINUTE if hasattr(settings, 'RATE_LIMIT_PER_MINUTE') else 60


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    # Defense-in-depth security headers. The API serves JSON, so a strict
    # CSP (no rendering surface) is safe and blocks clickjacking/embedding.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    response.headers["X-Download-Options"] = "noopen"
    if is_production():
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com; "
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com https://www.googleapis.com; "
            "frame-src 'self' https://accounts.google.com; "
            "frame-ancestors 'none'; base-uri 'none'"
        )
    return response


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    # Don't log routine orchestrator probes — keep logs signalful.
    if request.url.path in _PROBE_PATHS:
        return await call_next(request)

    request_id = request.headers.get("x-request-id") or secrets.token_hex(8)
    client_ip = _client_ip(request)
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )

    # Write non-2xx responses to platform_logs for admin analysis
    if response.status_code >= 400:
        try:
            severity = SEV_ERROR if response.status_code >= 500 else SEV_WARNING
            log_api_request(
                f"{request.method} {request.url.path} → {response.status_code}",
                severity=severity,
                request_id=request_id,
                client_ip=client_ip,
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        except Exception:  # noqa: BLE001
            pass

    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    # Never throttle liveness/readiness probes.
    if request.url.path in _PROBE_PATHS:
        return await call_next(request)

    # Never throttle read-only polling endpoints (GET only).
    path = request.url.path
    is_polling = request.method == "GET" and (
        path.startswith("/api/v1/assets")
        or path.startswith("/api/v1/scans")
        or path.startswith("/api/v1/notifications")
    )
    if is_polling:
        return await call_next(request)

    # Shadow-asset endpoints (list, review, review-log) are interactive,
    # authenticated user actions — exempt from the global throttle so a user
    # can confirm/reject candidates without tripping the 429 limit.
    if path.startswith("/api/v1/shadow-assets"):
        return await call_next(request)

    client_ip = _client_ip(request)

    # Stricter limit for login/register endpoints
    path = request.url.path
    # Every unauthenticated credential / token endpoint gets the strict bucket.
    # (Login also has a per-email limit inside the handler, which a spoofed IP
    # cannot get around.)
    is_auth_endpoint = path in (
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/2fa/verify-login",
        "/api/v1/auth/google",
    ) or path.startswith("/api/v1/passkeys/authenticate")
    max_requests = LOGIN_RATE_LIMIT if is_auth_endpoint else GLOBAL_RATE_LIMIT
    bucket = "auth" if is_auth_endpoint else "global"

    if not get_rate_limiter().is_allowed(f"{bucket}:{client_ip}", max_requests):
        try:
            log_security_event(
                f"Rate limit exceeded ({bucket})",
                detail={"bucket": bucket, "max_requests": max_requests},
                client_ip=client_ip,
                path=request.url.path,
                method=request.method,
                status_code=429,
            )
        except Exception:  # noqa: BLE001
            pass
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."}
        )

    response = await call_next(request)
    return response


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health_check():
    """Liveness probe — process is up and accepting connections."""
    return {"status": "healthy"}


@app.get("/health/scans")
async def scan_queue_health():
    """Scan queue status: execution mode, job counts and oldest waiting job.

    A growing ``oldest_pending_seconds`` means no scan worker is running or
    workers are saturated.
    """
    import asyncio
    from app.database import SessionLocal
    from app.services.job_queue import queue_stats
    from app.services.scan_dispatch import execution_mode
    from app.core.scope import scope_mode
    from app.workers.scan_worker import embedded_worker

    def _stats():
        db = SessionLocal()
        try:
            return queue_stats(db)
        finally:
            db.close()

    try:
        stats = await asyncio.to_thread(_stats)
    except Exception:  # noqa: BLE001
        stats = {"error": "queue unavailable"}
    w = embedded_worker()
    return {
        "execution_mode": execution_mode(),
        "scope_enforcement": scope_mode(),
        "embedded_worker": {"running": True, "active_jobs": w.active_jobs} if w else {"running": False},
        "queue": stats,
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe — dependencies (database) are reachable."""
    try:
        with write_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
        neo4j_ok = False
        try:
            from app.blockchain.infrastructure.graph.neo4j_driver import driver
            if driver.is_connected:
                result = await driver.run("RETURN 1 AS ok")
                neo4j_ok = bool(result)
        except Exception:
            neo4j_ok = False
        return {"status": "ready", "database": "ok", "neo4j": neo4j_ok}
    except Exception as exc:  # noqa: BLE001
        logger.error("Readiness check failed", extra={"error": str(exc)})
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unreachable"},
        )



# Import and include routers
from fastapi import Depends  # noqa: E402
from app.api.deps import get_current_user  # noqa: E402
# blockchain and darkweb have no per-route auth, so the whole router requires a login.
from app.api.v1 import scan, auth, assets, reports, organizations, projects, users, api_keys, compare, notifications, notification_preferences, tags, canvas, sessions, invitations, admin, security, scopes, api_keys_v2, security_center, passkeys, replay, asset_360, change_feed, collaboration, reports_v2, auth_google, evidence, shadow, search, osint, scanner_v2, logs, blockchain, darkweb, webhooks, integrations, support  # noqa: E402

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(auth_google.router, prefix="/api/v1/auth", tags=["Google OAuth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(scan.router, prefix="/api/v1/scans", tags=["Scans"])
app.include_router(assets.router, prefix="/api/v1/assets", tags=["Assets"])
# Registered before the generic reports router: its `/{report_id}` route would
# otherwise capture `/reports/executive` and answer 404.
app.include_router(reports_v2.router, prefix="/api/v1/reports/executive", tags=["Executive Reports"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(organizations.router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(api_keys.router, prefix="/api/v1/api-keys", tags=["API Keys"])
app.include_router(compare.router, prefix="/api/v1/compare", tags=["Compare"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(notification_preferences.router, prefix="/api/v1/notification-preferences", tags=["Notification Preferences"])
app.include_router(tags.router, prefix="/api/v1/tags", tags=["Tags, Audit Logs, Favorites"])
app.include_router(canvas.router, prefix="/api/v1/canvases", tags=["Intelligence Canvas"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(invitations.router, prefix="/api/v1/invitations", tags=["Invitations"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(security.router, prefix="/api/v1/security", tags=["Security"])
app.include_router(scopes.router, prefix="/api/v1/scopes", tags=["Authorized Scopes"])
app.include_router(api_keys_v2.router, prefix="/api/v1/api-keys/v2", tags=["API Keys v2"])
app.include_router(security_center.router, prefix="/api/v1/security-center", tags=["Security Center"])
app.include_router(passkeys.router, prefix="/api/v1/passkeys", tags=["Passkeys"])
app.include_router(replay.router, prefix="/api/v1/replay", tags=["Exposure Replay"])
app.include_router(asset_360.router, prefix="/api/v1/asset360", tags=["Asset 360"])
app.include_router(change_feed.router, prefix="/api/v1/changefeed", tags=["Change Feed"])
app.include_router(collaboration.router, prefix="/api/v1/collaboration", tags=["Collaboration"])
app.include_router(evidence.router, prefix="/api/v1/findings", tags=["Evidence Center"])
app.include_router(shadow.router, prefix="/api/v1/shadow-assets", tags=["Shadow Assets"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(osint.router, prefix="/api/v1/osint", tags=["OSINT Intelligence"])
app.include_router(scanner_v2.router, prefix="/api/v1/scanner-v2", tags=["Scanner v2"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Platform Logs"])
app.include_router(blockchain.router, prefix="/api/v1/blockchain", tags=["Blockchain Intelligence"], dependencies=[Depends(get_current_user)])
app.include_router(darkweb.router, prefix="/api/v1/darkweb", tags=["Dark Web Intelligence"], dependencies=[Depends(get_current_user)])
app.include_router(support.router, prefix="/api/v1/support", tags=["Support Chat"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])


# Billing: plans, checkout, Stripe webhooks; plan limits answer HTTP 402.
from app.api.v1 import billing  # noqa: E402
from app.billing.entitlements import PlanLimitExceeded  # noqa: E402

app.include_router(billing.router, prefix="/api/v1/billing", tags=["Billing"])


@app.exception_handler(PlanLimitExceeded)
async def plan_limit_handler(request: Request, exc: PlanLimitExceeded):
    """Plan limits are a payment matter, not a permission one: HTTP 402."""
    return JSONResponse(status_code=402, content={"detail": exc.as_detail()})


# API docs (only in debug mode)
if settings.DEBUG:
    from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

    @app.get("/api/docs", include_in_schema=False)
    async def swagger_ui():
        return get_swagger_ui_html(openapi_url="/api/openapi.json", title="CAZO API")

    @app.get("/api/redoc", include_in_schema=False)
    async def redoc_ui():
        return get_redoc_html(openapi_url="/api/openapi.json", title="CAZO API")

    @app.get("/api/openapi.json", include_in_schema=False)
    async def openapi_json():
        return app.openapi()
