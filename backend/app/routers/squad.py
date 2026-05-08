from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vendor import Vendor
from app.schemas.squad import SquadCreateMerchantRequest
from app.services.squad_api import create_merchant, parse_webhook_event


router = APIRouter()


def _create_squad_merchant_for_vendor(vendor_id: str, db: Session):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before Squad merchant creation")

    result = create_merchant(vendor)
    vendor.squad_merchant_id = result.get("merchant_id") or result.get("data", {}).get("merchant_id")
    db.commit()
    db.refresh(vendor)
    return {"vendor_id": vendor.id, "squad_merchant_id": vendor.squad_merchant_id, "result": result}


@router.post("/webhook")
def receive_squad_webhook(payload: dict, db: Session = Depends(get_db)):
    event = parse_webhook_event(payload)
    data = event["data"]
    vendor_id = data.get("vendor_id")
    if vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor and event["event"] in {"merchant.signup", "merchant.created"}:
            vendor.status = "pending"
            db.commit()
    return {"received": True, "event": event["event"]}


@router.post("/create-merchant")
def create_squad_merchant(payload: SquadCreateMerchantRequest, db: Session = Depends(get_db)):
    return _create_squad_merchant_for_vendor(payload.vendor_id, db)


@router.post("/create-merchant/{vendor_id}")
def create_squad_merchant_by_path(vendor_id: str, db: Session = Depends(get_db)):
    return _create_squad_merchant_for_vendor(vendor_id, db)


@router.get("/merchant/{vendor_id}")
def get_squad_merchant_status(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {
        "vendor_id": vendor.id,
        "has_squad_merchant": bool(vendor.squad_merchant_id),
        "squad_merchant_id": vendor.squad_merchant_id,
    }
