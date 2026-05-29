from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings
from app.utils.logger import db_log, logger


connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _redact_database_url(url: str) -> str:
    """Redact sensitive credentials from database URL for logging."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://...@{rest.split('@', 1)[1]}"
    return url


def verify_database_connection() -> bool:
    """
    Verify database connectivity with a simple SELECT 1 query.
    This is synchronous and safe to run in a thread pool.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        db_log(f"✓ Database connected — {_redact_database_url(settings.DATABASE_URL)}")
        return True
    except Exception as exc:
        db_log(f"✗ Database connection failed: {exc}", "error")
        return False


def get_db():
    """Dependency injection for database sessions in FastAPI routes."""
    db = SessionLocal()
    logger.debug("Database session opened")
    try:
        yield db
    finally:
        db.close()
        logger.debug("Database session closed")