import datetime as dt
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.vendor import TierEnum, VendorCreate, VendorOut, VendorStatusUpdate
from app.utils.logger import db_log, logger


router = APIRouter()


def validate_vendor_fields(payload: VendorCreate) -> list[str]:
    errors: list[str] = []
    tier = payload.tier.value
    bvn_status = "\u2713"
    nin_status = "\u2713"
    phone_status = "\u2713"
    email_status = "\u2713"
    rc_status = "\u2713"

    if payload.bvn and not re.match(r"^\d{11}$", payload.bvn):
        errors.append("BVN must be exactly 11 digits")
        bvn_status = "\u2717"
    elif payload.bvn and (len(set(payload.bvn)) == 1 or payload.bvn == "12345678901"):
        errors.append("BVN appears to be a placeholder value")
        bvn_status = "\u26a0 placeholder"

    if payload.nin and not re.match(r"^\d{11}$", payload.nin):
        errors.append("NIN must be exactly 11 digits")
        nin_status = "\u2717"
    elif payload.nin and (len(set(payload.nin)) == 1 or payload.nin == "12345678901"):
        errors.append("NIN appears to be a placeholder value")
        nin_status = "\u26a0 placeholder"

    if payload.phone and not re.match(r"^(\+?234|0)[789][01]\d{8}$", payload.phone):
        errors.append("Invalid Nigerian phone number format")
        phone_status = "\u2717"

    if tier in ["tier2", "tier3"] and payload.email:
        free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        domain = str(payload.email).split("@")[-1].lower()
        if domain in free_domains:
            errors.append("Business accounts should use a corporate email address")
            email_status = "\u26a0 free_domain"

    if tier == "tier3" and not (payload.rc_number or "").strip():
        errors.append("RC number is required for Tier 3 vendors")
        rc_status = "\u2717"
    elif tier in ["tier2", "tier3"] and payload.rc_number:
        if not re.match(r"^RC\s*\d{5,7}$", payload.rc_number, re.IGNORECASE):
            errors.append("RC number format invalid - expected RC followed by 5-7 digits")
            rc_status = "\u2717"

    logger.info(
        "\u2192 Validating vendor fields: BVN=%s NIN=%s Phone=%s Email=%s RC=%s",
        bvn_status,
        nin_status,
        phone_status,
        email_status,
        rc_status,
    )
    return errors


@router.post("/", response_model=VendorOut, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
):
    validation_errors = validate_vendor_fields(payload)
    if validation_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation failed",
                "errors": validation_errors,
            },
        )

    vendor = Vendor(
        id=str(uuid.uuid4()),
        business_name=payload.business_name,
        rc_number=payload.rc_number or None,
        website_url=payload.website_url or None,
        social_media_url=payload.social_media_url or None,
        business_category=payload.business_category or None,
        bank_name=payload.bank_name or None,
        bank_code=payload.bank_code or None,
        account_number=payload.account_number or None,
        account_name=payload.account_name or None,
        bvn=payload.bvn,
        nin=payload.nin,
        email=str(payload.email),
        phone=payload.phone,
        address=payload.address,
        director_name=payload.director_name or None,
        expected_monthly_volume=payload.expected_monthly_volume,
        tier=payload.tier.value,
        status="pending",
        created_at=dt.datetime.now(dt.UTC),
    )
    db_log(f"\u2192 Saving vendor: {vendor.business_name} | tier: {vendor.tier} | id: {vendor.id}")
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    db_log(f"\u2713 Vendor saved - id: {vendor.id}")
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
