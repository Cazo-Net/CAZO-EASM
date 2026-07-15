from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import secrets
import time
import logging

from app.config import settings, is_production
from app.database import init_db, engine
from app.core.rate_limit import get_rate_limiter
from app.core.logging import configure_logging

logger = logging.getLogger("app.main")

# Paths that must never be throttled (orchestrator liveness/readiness probes).
_PROBE_PATHS = {"/health", "/ready"}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    configure_logging(getattr(settings, "LOG_LEVEL", "INFO"))
    init_db()
    get_rate_limiter()
    logger.info("Application started", extra={"environment": settings.ENVIRONMENT})
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), "
        "usb=(), interest-cohort=()"
    )
    if is_production():
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
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
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)

    # Never throttle liveness/readiness probes.
    if request.url.path in _PROBE_PATHS:
        return await call_next(request)

    client_ip = _client_ip(request)

    # Stricter limit for login/register endpoints
    path = request.url.path
    is_auth_endpoint = path in ("/api/v1/auth/login", "/api/v1/auth/register")
    max_requests = LOGIN_RATE_LIMIT if is_auth_endpoint else GLOBAL_RATE_LIMIT
    bucket = "auth" if is_auth_endpoint else "global"

    if not get_rate_limiter().is_allowed(f"{bucket}:{client_ip}", max_requests):
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


@app.get("/ready")
async def readiness_check():
