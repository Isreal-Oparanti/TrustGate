from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, verify_database_connection
from app.models import Document, Flag, Payment, Vendor, Verification
from app.routers import dashboard, documents, payments, squad, vendors, verification
from app.utils.logger import logger


# Keep model imports referenced so SQLAlchemy registers every table before create_all.
_registered_models = (Document, Flag, Payment, Vendor, Verification)

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

app.include_router(vendors.router, prefix=f"{settings.API_V1_PREFIX}/vendors", tags=["Vendors"])
app.include_router(verification.router, prefix=f"{settings.API_V1_PREFIX}/verify", tags=["Verification"])
app.include_router(documents.router, prefix=f"{settings.API_V1_PREFIX}/documents", tags=["Documents"])
app.include_router(squad.router, prefix=f"{settings.API_V1_PREFIX}/squad", tags=["Squad"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(payments.router, prefix=f"{settings.API_V1_PREFIX}/payments", tags=["Payments"])
app.include_router(payments.webhook_router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(payments.webhook_router, prefix=f"{settings.API_V1_PREFIX}/webhooks", tags=["Webhooks"])


@app.get("/health")
def health():
    return {"status": "ok", "database_connected": verify_database_connection()}
