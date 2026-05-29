import datetime as dt
from fastapi import APIRouter, Depends
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.dashboard import DashboardStats
from app.schemas.vendor import VendorOut


router = APIRouter()


def _attach_latest_verification(vendor: Vendor, db: Session) -> Vendor:
    latest = (
        db.query(Verification)
        .filter(Verification.vendor_id == vendor.id)
        .order_by(Verification.created_at.desc())
        .first()
    )
    score = latest.trust_score if latest else None
    setattr(vendor, "trust_score", score)
    setattr(vendor, "verification_score", score)
    if latest and vendor.status in {"pending", "review", "flagged", "blocked"}:
        vendor.status = latest.verdict
    return vendor


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    today = dt.datetime.utcnow().date()
    total = db.query(func.count(Vendor.id)).scalar() or 0
    total_today = db.query(func.count(Vendor.id)).filter(cast(Vendor.created_at, Date) == today).scalar() or 0
    approved = db.query(func.count(Vendor.id)).filter(Vendor.status == "approved").scalar() or 0
    pending_review = (
        db.query(func.count(Vendor.id))
        .filter(Vendor.status.in_(["pending", "review"]))
        .scalar()
        or 0
    )
    blocked = db.query(func.count(Vendor.id)).filter(Vendor.status.in_(["flagged", "blocked"])).scalar() or 0
    average_score = db.query(func.avg(Verification.trust_score)).scalar() or 0
    return {
        "total_today": total_today,
        "approved": approved,
        "pending_review": pending_review,
        "blocked": blocked,
        "avg_score": round(float(average_score), 2),
    }


@router.get("/queue", response_model=list[VendorOut])
def get_queue(db: Session = Depends(get_db)):
    vendors = (
        db.query(Vendor)
        .filter(Vendor.status.in_(["pending", "review", "flagged"]))
        .order_by(Vendor.created_at.desc())
        .limit(50)
        .all()
    )
    return [_attach_latest_verification(vendor, db) for vendor in vendors]


@router.get("/recent", response_model=list[dict])
def get_recent(db: Session = Depends(get_db)):
    recent = (
        db.query(Verification, Vendor)
        .join(Vendor, Verification.vendor_id == Vendor.id)
        .order_by(Verification.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "verification_id": verification.id,
            "vendor_id": vendor.id,
            "business_name": vendor.business_name,
            "trust_score": verification.trust_score,
            "risk_level": verification.risk_level,
            "verdict": verification.verdict,
            "created_at": verification.created_at.isoformat(),
        }
        for verification, vendor in recent
    ]
