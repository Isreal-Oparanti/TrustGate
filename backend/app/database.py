from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
from app.utils.logger import logger


connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# 🔌 Database connection lives here. SQLite works locally; Postgres works by changing DATABASE_URL.
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def verify_database_connection() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Database connection is healthy")
        return True
    except Exception as exc:
        logger.error("🔴 Database connection failed: %s", exc)
        return False


def get_db():
    db = SessionLocal()
    logger.debug("🔌 Database session opened")
    try:
        yield db
    finally:
        db.close()
        logger.debug("🔒 Database session closed")
