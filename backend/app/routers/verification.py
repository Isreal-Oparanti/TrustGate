import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal, get_db
from app.models.document import Document
from app.models.flag import Flag
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.verification import (
    FlagOut,
    VerificationNotStarted,
    VerificationQueued,
    VerificationResult,
    VerificationRunOut,
)
from app.services.scorer import recommendation_for, run_verification


router = APIRouter()


def _run_verification_background(vendor_id: str) -> None:
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor:
            asyncio.run(run_verification(db, vendor))
    finally:
        db.close()


def _get_vendor_or_404(db: Session, vendor_id: str) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.post("/{vendor_id}", response_model=VerificationRunOut | VerificationQueued)
async def verify_vendor(
    vendor_id: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    vendor = _get_vendor_or_404(db, vendor_id)

    # Check if vendor has at least one uploaded document (skip in dev mode)
    if settings.APP_ENV != "development":
        doc_count = db.query(Document).filter(
            Document.vendor_id == vendor_id
        ).count()

        if doc_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No documents uploaded. Please upload at least one document before verification."
            )

    if not wait:
        background_tasks.add_task(_run_verification_background, vendor_id)
        return {
            "vendor_id": vendor_id,
            "status": "queued",
            "trust_score": None,
            "verdict": "pending",
            "message": "Verification has started. Poll GET /api/v1/verify/{vendor_id} for the result.",
        }

    verification = await run_verification(db, vendor)
    return {
        "verification": verification,
        "recommendation": recommendation_for(verification.verdict),
    }


@router.get("/{vendor_id}", response_model=VerificationResult | VerificationNotStarted)
def get_latest_verification(vendor_id: str, db: Session = Depends(get_db)):
    _get_vendor_or_404(db, vendor_id)
    verification = (
        db.query(Verification)
        .filter(Verification.vendor_id == vendor_id)
        .order_by(Verification.created_at.desc())
        .first()
    )
    if not verification:
        return {
            "vendor_id": vendor_id,
            "status": "not_started",
            "trust_score": None,
            "verdict": "pending",
            "message": "Verification has not been run yet for this vendor.",
        }
    return verification


@router.get("/{vendor_id}/flags", response_model=list[FlagOut])
def get_vendor_flags(vendor_id: str, db: Session = Depends(get_db)):
    _get_vendor_or_404(db, vendor_id)
    return (
        db.query(Flag)
        .filter(Flag.vendor_id == vendor_id)
        .order_by(Flag.severity.desc(), Flag.created_at.desc())
        .all()
    )


@router.post("/{vendor_id}/rerun", response_model=VerificationRunOut)
async def rerun_verification(vendor_id: str, db: Session = Depends(get_db)):
    vendor = _get_vendor_or_404(db, vendor_id)
    verification = await run_verification(db, vendor)
    return {
        "verification": verification,
        "recommendation": recommendation_for(verification.verdict),
    }
