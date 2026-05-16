import datetime as dt
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.vendor import (
    TierEnum,
    VendorCreate,
    VendorCreateResponse,
    VendorLogin,
    VendorOut,
    VendorStatusUpdate,
)
from app.services.squad_api import create_merchant, hash_security_answer
from app.utils.logger import db_log, logger


router = APIRouter()


def _attach_latest_verification_score(vendor: Vendor, db: Session) -> Vendor:
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


def validate_vendor_fields(payload: VendorCreate) -> list[str]:
    errors: list[str] = []
    tier = payload.tier.value
    bvn_status = "✓"
    nin_status = "✓"
    phone_status = "✓"
    email_status = "✓"
    rc_status = "✓"

    if payload.bvn and not re.match(r"^\d{11}$", payload.bvn):
        errors.append("BVN must be exactly 11 digits")
        bvn_status = "✗"
    elif payload.bvn and (len(set(payload.bvn)) == 1 or payload.bvn == "12345678901"):
        errors.append("BVN appears to be a placeholder value")
        bvn_status = "⚠ placeholder"

    if payload.nin and not re.match(r"^\d{11}$", payload.nin):
        errors.append("NIN must be exactly 11 digits")
        nin_status = "✗"
    elif payload.nin and (len(set(payload.nin)) == 1 or payload.nin == "12345678901"):
        errors.append("NIN appears to be a placeholder value")
        nin_status = "⚠ placeholder"

    if payload.phone and not re.match(r"^(234|0)[789][01]\d{8}$", payload.phone):
        errors.append("Invalid Nigerian phone number format. Use 08012345678 or 2348012345678.")
        phone_status = "✗"

    if payload.settlement_account_number and not re.match(r"^\d{10}$", payload.settlement_account_number):
        errors.append("Settlement account number must be exactly 10 digits")

    settlement_bank_code = (payload.settlement_bank_code or "").strip()
    settlement_bank = (payload.settlement_bank or "").strip().lower()
    if settlement_bank_code not in {"058", "000013"} and "gtbank" not in settlement_bank and "guaranty trust" not in settlement_bank:
        errors.append("Wallet-compatible settlement bank must be GTBank")

    if tier in ["tier2", "tier3"] and payload.email:
        free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        domain = str(payload.email).split("@")[-1].lower()
        if domain in free_domains:
            errors.append("Business accounts should use a corporate email address")
            email_status = "⚠ free_domain"

    if tier == "tier3" and not (payload.rc_number or "").strip():
        errors.append("RC number is required for Tier 3 vendors")
        rc_status = "✗"
    elif tier in ["tier2", "tier3"] and payload.rc_number:
        if not re.match(r"^RC\s*\d{5,7}$", payload.rc_number, re.IGNORECASE):
            errors.append("RC number format invalid - expected RC followed by 5-7 digits")
            rc_status = "✗"

    logger.info(
        "→ Validating vendor fields: BVN=%s NIN=%s Phone=%s Email=%s RC=%s",
        bvn_status,
        nin_status,
        phone_status,
        email_status,
        rc_status,
    )
    return errors


def _extract_squad_account_id(squad_response: dict[str, Any]) -> str | None:
    data = squad_response.get("data")
    if isinstance(data, dict):
        return data.get("account_id") or data.get("merchant_id") or data.get("id")
    return squad_response.get("account_id") or squad_response.get("merchant_id") or squad_response.get("id")


def _needs_squad_sync(vendor: Vendor) -> bool:
    squad_id = vendor.squad_account_id or vendor.squad_merchant_id
    return not squad_id or squad_id.startswith("mock_sub_")


def _sync_vendor_to_squad_sub_merchant(vendor: Vendor, db: Session) -> dict[str, Any]:
    try:
        squad_response = create_merchant(vendor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Squad sub-merchant creation failed: {exc}") from exc

    vendor.squad_account_id = _extract_squad_account_id(squad_response)
    vendor.squad_merchant_id = vendor.squad_account_id
    vendor.settlement_status = "active" if vendor.squad_account_id else "pending"
    db.commit()
    db.refresh(vendor)
    return squad_response


@router.post("/", response_model=VendorCreateResponse, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
):
    business_name = " ".join(payload.business_name.split())
    existing_vendor = db.query(Vendor).filter(func.lower(Vendor.business_name) == business_name.lower()).first()
    if existing_vendor:
        raise HTTPException(status_code=409, detail="Business name already exists")

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
        business_name=business_name,
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
        settlement_account_name=payload.settlement_account_name,
        settlement_account_number=payload.settlement_account_number,
        settlement_bank_code=payload.settlement_bank_code,
        settlement_bank=payload.settlement_bank,
        settlement_status="pending",
        payment_security_question=payload.payment_security_question,
        payment_security_answer_hash=hash_security_answer(payload.payment_security_answer),
        created_at=dt.datetime.now(dt.UTC),
    )
    db_log(f"→ Saving vendor: {vendor.business_name} | tier: {vendor.tier} | id: {vendor.id}")
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    db_log(f"✓ Vendor saved - id: {vendor.id}")
    return {
        "vendor": vendor,
        "squad_response": {"message": "Vendor saved pending approval. Squad sync will run after approval."},
    }


@router.post("/login", response_model=VendorOut)
def login_vendor(payload: VendorLogin, db: Session = Depends(get_db)):
    business_name = " ".join(payload.business_name.split())
    rc_number = (payload.rc_number or "").strip()
    vendor = (
        db.query(Vendor)
        .filter(
            func.lower(Vendor.business_name) == business_name.lower(),
            func.lower(func.coalesce(Vendor.rc_number, "")) == rc_number.lower(),
        )
        .first()
    )
    if not vendor:
        raise HTTPException(status_code=401, detail="Business name or RC number is incorrect")
    if vendor.status != "approved":
        raise HTTPException(status_code=403, detail="Vendor must be approved before accessing the vendor portal")
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
    vendors = query.order_by(Vendor.created_at.desc()).all()
    return [_attach_latest_verification_score(vendor, db) for vendor in vendors]


@router.get("/me", response_model=VendorOut)
def get_logged_in_vendor(current_vendor: Vendor = Depends(get_current_vendor)):
    return current_vendor


@router.get("/{vendor_id}", response_model=VendorOut)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return _attach_latest_verification_score(vendor, db)


@router.patch("/{vendor_id}/status", response_model=VendorOut)
def update_vendor_status(vendor_id: str, payload: VendorStatusUpdate, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.status = payload.status.value

    if payload.status.value == "approved" and _needs_squad_sync(vendor):
        db.flush()
        _sync_vendor_to_squad_sub_merchant(vendor, db)
        return vendor

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
