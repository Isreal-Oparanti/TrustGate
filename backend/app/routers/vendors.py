import datetime as dt
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models.vendor import Vendor
from app.schemas.vendor import TierEnum, VendorCreate, VendorOut, VendorStatusUpdate
from app.services.scorer import run_verification
from app.utils.logger import db_log, logger


router = APIRouter()


def run_verification_for_vendor_id(vendor_id: str):
    db = SessionLocal()
    try:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor:
            run_verification(db, vendor)
            logger.info("🤖 Verification pipeline completed for vendor %s", vendor_id)
    finally:
        db.close()


@router.post("/", response_model=VendorOut, status_code=201)
def create_vendor(
    payload: VendorCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    vendor = Vendor(
        id=str(uuid.uuid4()),
        business_name=payload.business_name,
        rc_number=payload.rc_number,
        bvn=payload.bvn,
        nin=payload.nin,
        email=str(payload.email),
        phone=payload.phone,
        address=payload.address,
        director_name=payload.director_name or "",
        tier=payload.tier.value,
        status="pending",
        created_at=dt.datetime.now(dt.UTC),
    )
    db_log(f"→ Saving vendor: {vendor.business_name} | tier: {vendor.tier} | id: {vendor.id}")
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    db_log(f"✓ Vendor saved — id: {vendor.id}")
    background_tasks.add_task(run_verification_for_vendor_id, vendor.id)
    return vendor


@router.get("/", response_model=list[VendorOut])
def list_vendors(
    status: str | None = Query(default=None),
    tier: TierEnum | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Vendor)
    if status:
        query = query.filter(Vendor.status == status)
    if tier:
        query = query.filter(Vendor.tier == tier.value)
    return query.order_by(Vendor.created_at.desc()).all()


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


@router.patch("/{vendor_id}/status", response_model=VendorOut)
def update_vendor_status(vendor_id: str, payload: VendorStatusUpdate, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.status = payload.status.value
    db.commit()
    db.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=204)
def delete_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    db.delete(vendor)
    db.commit()
