from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings, get_database_url


if settings.USE_SQLITE:
    engine = create_engine(
        get_database_url(),
        connect_args={"check_same_thread": False},
        echo=settings.DATABASE_ECHO,
    )
else:
    engine = create_engine(
        get_database_url(),
        echo=settings.DATABASE_ECHO,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables.

    Creates all tables defined on the declarative Base. ``create_all`` is
    idempotent: it only creates tables that do not already exist, so it is
    safe to run in every environment (dev, prod, and alongside Alembic).

    Importing the models package ensures every mapped table is registered on
    ``Base.metadata`` before ``create_all`` runs, so this works both as a
    standalone bootstrap and when called from application startup.
    """
    from app import models  # noqa: F401  (registers all tables on Base.metadata)
    Base.metadata.create_all(bind=engine)
