"""Database connection to EASM platform database."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings


def _get_database_url() -> str:
    if settings.USE_SQLITE:
        return f"sqlite:///{settings.EASM_SQLITE_PATH}"
    return settings.EASM_DATABASE_URL


engine = create_engine(
    _get_database_url(),
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=15,
    pool_recycle=900,
    connect_args={"check_same_thread": False} if settings.USE_SQLITE else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "pool_size": engine.pool.size(), "checked_out": engine.pool.checkedout()}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}
