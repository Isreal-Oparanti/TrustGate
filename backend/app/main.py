import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine, verify_database_connection
from app.models import Document, Flag, Transaction, Vendor, Verification
from app.routers import admin, dashboard, documents, squad, vendors, verification
from app.utils.logger import db_log, logger


for _noisy in ("asyncio", "httpx", "httpcore", "watchfiles", "urllib3", "openai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


_registered_models = (Document, Flag, Transaction, Vendor, Verification)

Base.metadata.create_all(bind=engine)
db_log("\u2713 Tables verified - vendors, verifications, flags, transactions")


def _ensure_columns(table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    missing = [(name, ddl) for name, ddl in columns.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))
            db_log(f"\u2713 Migration applied - added {table_name}.{name}")


try:
    _ensure_columns(
        "vendors",
        {
            "rc_number": "VARCHAR",
            "website_url": "VARCHAR",
            "social_media_url": "VARCHAR",
            "business_category": "VARCHAR",
            "bank_name": "VARCHAR",
            "bank_code": "VARCHAR",
            "account_number": "VARCHAR",
            "account_name": "VARCHAR",
            "director_name": "VARCHAR",
            "expected_monthly_volume": "INTEGER",
        },
    )
    _ensure_columns("documents", {"doc_type": "VARCHAR"})
    _ensure_columns(
        "verifications",
        {
            "identity_score": "INTEGER DEFAULT 0 NOT NULL",
            "document_score": "INTEGER DEFAULT 0 NOT NULL",
            "business_score": "INTEGER DEFAULT 0 NOT NULL",
            "behaviour_score": "INTEGER DEFAULT 0 NOT NULL",
            "external_checks": "JSON",
            "processing_time_ms": "INTEGER DEFAULT 0 NOT NULL",
        },
    )
    db_log("\u2713 Vendor model updated with extended fields")
except Exception as exc:
    db_log(f"Model auto-migration skipped: {exc}", "warning")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            db_ok = await loop.run_in_executor(executor, verify_database_connection)

        if db_ok:
            logger.info("TrustGate API started with database connected")
        else:
            logger.warning("TrustGate API started, but database connection failed")
    except Exception as exc:
        logger.error("Startup error during DB verification: %s", exc)

    yield

    logger.info("TrustGate API shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI vendor trust scoring and KYB intelligence for Squad-style merchant onboarding.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendors.router, prefix=f"{settings.API_V1_PREFIX}/vendors", tags=["Vendors"])
app.include_router(verification.router, prefix=f"{settings.API_V1_PREFIX}/verify", tags=["Verification"])
app.include_router(documents.router, prefix=f"{settings.API_V1_PREFIX}/documents", tags=["Documents"])
app.include_router(squad.router, prefix=f"{settings.API_V1_PREFIX}/squad", tags=["Squad"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(admin.router, prefix=f"{settings.API_V1_PREFIX}/admin", tags=["Admin"])


@app.get("/health")
def health():
    return {"status": "ok", "database_connected": verify_database_connection()}
