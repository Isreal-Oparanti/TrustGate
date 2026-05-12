from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.flag import Flag
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.verification import FlagOut, VerificationResult, VerificationRunOut
from app.services.scorer import recommendation_for, run_verification


router = APIRouter()


def _get_vendor_or_404(db: Session, vendor_id: str) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.post("/{vendor_id}", response_model=VerificationRunOut)
async def verify_vendor(vendor_id: str, db: Session = Depends(get_db)):
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

    verification = await run_verification(db, vendor)
    return {
        "verification": verification,
        "recommendation": recommendation_for(verification.verdict),
    }


@router.get("/{vendor_id}", response_model=VerificationResult)
def get_latest_verification(vendor_id: str, db: Session = Depends(get_db)):
    _get_vendor_or_404(db, vendor_id)
    verification = (
        db.query(Verification)
        .filter(Verification.vendor_id == vendor_id)
        .order_by(Verification.created_at.desc())
        .first()
    )
    if not verification:
        raise HTTPException(status_code=404, detail="No verification found for vendor")
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
