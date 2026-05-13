from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, verify_database_connection
from app.models import Document, Flag, Payment, Vendor, Verification, Wallet
from app.routers import payments, transfers, vendors, wallets
from app.utils.logger import logger


# Keep model imports referenced so SQLAlchemy registers every table before create_all.
_registered_models = (Document, Flag, Payment, Vendor, Verification, Wallet)

# 🧱 Create all DB tables on startup for the hackathon/demo flow.
Base.metadata.create_all(bind=engine)


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

app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(wallets.router, prefix="/api/wallets", tags=["Wallets"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(transfers.router, prefix="/api/transfers", tags=["Transfers"])
app.include_router(payments.webhook_router, prefix="/api/webhooks", tags=["Webhooks"])


@app.get("/health")
def health():
    return {"status": "ok", "database_connected": verify_database_connection()}
