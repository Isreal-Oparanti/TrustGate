import asyncio
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, engine, verify_database_connection
from app.models import Document, Flag, Payment, Transaction, Vendor, Verification, Wallet, WalletActivity
from app.routers import admin, dashboard, documents, payments, squad, transactions, transfers, vendors, verification, wallets
from app.utils.logger import agent_log, db_log, logger


UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"

for _noisy in ("asyncio", "httpx", "httpcore", "watchfiles", "urllib3", "openai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# Keep model imports referenced so SQLAlchemy registers every table before create_all.
_registered_models = (Document, Flag, Payment, Transaction, Vendor, Verification, Wallet, WalletActivity)

Base.metadata.create_all(bind=engine)
db_log("✓ Tables verified - vendors, verifications, flags, payments, wallets, transactions")


def _ensure_columns(table_name: str, columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    missing = [(name, ddl) for name, ddl in columns.items() if name not in existing]
    if not missing:
        return

    with engine.begin() as conn:
        for name, ddl in missing:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))
            db_log(f"✓ Migration applied - added {table_name}.{name}")


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
            "expected_monthly_volume": "BIGINT",
            "squad_account_id": "VARCHAR",
            "squad_merchant_id": "VARCHAR",
            "settlement_account_name": "VARCHAR",
            "settlement_account_number": "VARCHAR",
            "settlement_bank_code": "VARCHAR",
            "settlement_bank": "VARCHAR",
            "settlement_status": "VARCHAR DEFAULT 'not_started' NOT NULL",
            "payment_security_question": "VARCHAR",
            "payment_security_answer_hash": "VARCHAR",
        },
    )
    _ensure_columns("documents", {"doc_type": "VARCHAR", "file_size_kb": "INTEGER"})
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
    db_log("✓ Vendor model updated with extended fields")
except Exception as exc:
    db_log(f"Model auto-migration skipped: {exc}", "warning")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        agent_log("LLM provider: openai | model: gpt-4o-mini")
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

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(wallets.router, prefix="/api/wallets", tags=["Wallets"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(transfers.router, prefix="/api/transfers", tags=["Transfers"])
app.include_router(payments.webhook_router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(vendors.router, prefix=f"{settings.API_V1_PREFIX}/vendors", tags=["Vendors"])
app.include_router(verification.router, prefix=f"{settings.API_V1_PREFIX}/verify", tags=["Verification"])
app.include_router(documents.router, prefix=f"{settings.API_V1_PREFIX}/documents", tags=["Documents"])
app.include_router(squad.router, prefix=f"{settings.API_V1_PREFIX}/squad", tags=["Squad"])
app.include_router(transactions.router, prefix=f"{settings.API_V1_PREFIX}/transactions", tags=["Transactions"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(admin.router, prefix=f"{settings.API_V1_PREFIX}/admin", tags=["Admin"])


@app.get("/health")
def health():
    squad_enabled = bool(settings.SQUAD_SECRET_KEY) and not settings.SQUAD_MOCK_MODE
    return {
        "status": "ok",
        "database_connected": verify_database_connection(),
        "squad": {
            "enabled": squad_enabled,
            "mock_mode": settings.SQUAD_MOCK_MODE,
            "base_url": settings.SQUAD_API_BASE_URL,
            "has_secret_key": bool(settings.SQUAD_SECRET_KEY),
        },
    }
