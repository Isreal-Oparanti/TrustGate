import datetime as dt
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.schemas.vendor import (
    VendorCreate,
    VendorCreateResponse,
    VendorOut,
)
from app.services.squad_api import create_sub_merchant, hash_security_answer


router = APIRouter()


@router.post("/", response_model=VendorCreateResponse, status_code=201)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
):
    existing_vendor = db.query(Vendor).filter(Vendor.business_name == payload.business_name).first()
    if existing_vendor:
        raise HTTPException(status_code=409, detail="Business name already exists")

    vendor = Vendor(
        id=str(uuid.uuid4()),
        business_name=payload.business_name,
        rc_number=payload.rc_number,
        bvn=payload.bvn,
        nin=payload.nin,
        email=str(payload.email),
        phone=payload.phone,
        address=payload.address,
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
    db.add(vendor)
    db.flush()

    squad_response = _sync_vendor_to_squad_sub_merchant(vendor, db)
    return {"vendor": vendor, "squad_response": squad_response}


def _extract_squad_account_id(squad_response: dict[str, Any]) -> str | None:
    data = squad_response.get("data")
    if isinstance(data, dict):
        return data.get("account_id")
    return squad_response.get("account_id")


def _sync_vendor_to_squad_sub_merchant(vendor: Vendor, db: Session) -> dict[str, Any]:
    try:
        squad_response = create_sub_merchant(vendor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Squad sub-merchant creation failed: {exc}") from exc

    vendor.squad_account_id = _extract_squad_account_id(squad_response)
    vendor.settlement_status = "active" if vendor.squad_account_id else "pending"
    if vendor.squad_account_id:
        vendor.status = "approved"
    db.commit()
    db.refresh(vendor)
    return squad_response


@router.get("/me", response_model=VendorOut)
def get_logged_in_vendor(current_vendor: Vendor = Depends(get_current_vendor)):
    return current_vendor
