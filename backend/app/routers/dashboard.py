import datetime as dt
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.dashboard import DashboardStats, QueueOut


router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    today = dt.datetime.utcnow().date()
    total = db.query(func.count(Vendor.id)).scalar() or 0
    total_today = db.query(func.count(Vendor.id)).filter(func.date(Vendor.created_at) == str(today)).scalar() or 0
    approved = db.query(func.count(Vendor.id)).filter(Vendor.status == "approved").scalar() or 0
    pending_review = (
        db.query(func.count(Vendor.id))
        .filter(Vendor.status.in_(["pending", "review"]))
        .scalar()
        or 0
    )
    blocked = db.query(func.count(Vendor.id)).filter(Vendor.status == "blocked").scalar() or 0
    average_score = db.query(func.avg(Verification.trust_score)).scalar() or 0
    return {
        "total_vendors": total,
        "total_today": total_today,
        "approved": approved,
        "pending_review": pending_review,
        "blocked": blocked,
        "average_score": round(float(average_score), 2),
    }


@router.get("/queue", response_model=QueueOut)
def get_queue(db: Session = Depends(get_db)):
    vendors = (
        db.query(Vendor)
        .filter(Vendor.status.in_(["pending", "review"]))
        .order_by(Vendor.created_at.desc())
        .limit(50)
        .all()
    )
    items = []
    for vendor in vendors:
        latest = (
            db.query(Verification)
            .filter(Verification.vendor_id == vendor.id)
            .order_by(Verification.created_at.desc())
            .first()
        )
        items.append({"vendor": vendor, "latest_verification": latest})
    return {"items": items}


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
