from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, verify_database_connection
from app.models import Document, Flag, Transaction, Vendor, Verification
from app.routers import dashboard, documents, squad, vendors, verification
from app.utils.logger import db_log, logger

# ── Silence noisy third-party loggers so terminal stays clean ────────────────
for _noisy in ("asyncio", "httpx", "httpcore", "watchfiles", "urllib3", "openai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


# Keep model imports referenced so SQLAlchemy registers every table before create_all.
_registered_models = (Document, Flag, Transaction, Vendor, Verification)

# 🧱 Create all DB tables on startup for the hackathon/demo flow.
Base.metadata.create_all(bind=engine)
db_log("✓ Tables verified — vendors, verifications, flags, transactions")

# ── Auto-migrate: add director_name column if missing (existing SQLite DBs) ──
try:
    from sqlalchemy import text as _text
    with engine.connect() as _conn:
        _conn.execute(_text("ALTER TABLE vendors ADD COLUMN director_name VARCHAR"))
        _conn.commit()
        db_log("✓ Migration applied — added director_name column")
except Exception:
    pass  # Column already exists or table doesn't exist yet


@asynccontextmanager
async def lifespan(app: FastAPI):
    if verify_database_connection():
        logger.info("🚀 TrustGate API started with database connected")
    else:
        logger.error("🛑 TrustGate API started, but database connection failed")
    yield


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


@app.get("/health")
def health():
    return {"status": "ok", "database_connected": verify_database_connection()}
