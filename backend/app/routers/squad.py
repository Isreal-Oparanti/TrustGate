from __future__ import annotations

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.transaction import Transaction
from app.models.vendor import Vendor
from app.schemas.squad import SquadCreateMerchantRequest
from app.services.squad_api import (
    create_sub_merchant,
    parse_webhook_event,
    verify_transaction,
    verify_webhook_signature,
)
from app.services.transaction_monitor import monitor_transaction
from app.utils.logger import squad_log


router = APIRouter()


def _extract_account_id(result: dict) -> str | None:
    data = result.get("data", result)
    return data.get("account_id") or data.get("merchant_id") or data.get("id") or result.get("account_id")


async def _create_squad_merchant_for_vendor(vendor_id: str, db: Session):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before Squad merchant creation")

    result = await create_sub_merchant(vendor)
    vendor.squad_merchant_id = _extract_account_id(result)
    db.commit()
    db.refresh(vendor)
    return {"vendor_id": vendor.id, "squad_merchant_id": vendor.squad_merchant_id, "result": result}


def _run_monitor_background(merchant_id: str, transaction_payload: dict) -> None:
    db = SessionLocal()
    try:
        asyncio.run(monitor_transaction(merchant_id, transaction_payload, db))
    finally:
        db.close()


@router.post("/webhook")
async def receive_squad_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_squad_signature: str | None = Header(default=None, alias="x-squad-signature"),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if not await verify_webhook_signature(body, x_squad_signature or ""):
        raise HTTPException(status_code=403, detail="Invalid Squad webhook signature")

    payload = await request.json()
    event = parse_webhook_event(payload)
    data = event["data"]
    squad_log(f"▶ Webhook received — event: {event['event']}")

    transaction_ref = data.get("transaction_ref") or data.get("reference") or data.get("transaction_id")
    amount = int(data.get("amount") or 0)
    status = data.get("transaction_status") or data.get("status") or "unknown"
    squad_log(f"   transaction_ref: {transaction_ref} | amount: ₦{amount / 100:,.0f} | status: {status}")

    if event["event"] not in {"payment_complete", "charge.success", "transaction.success"}:
        return {"received": True, "event": event["event"], "processed": False}

    if not transaction_ref:
        raise HTTPException(status_code=400, detail="Webhook missing transaction reference")

    verified = await verify_transaction(transaction_ref)
    verified_data = verified.get("data", verified)
    verified_status = verified_data.get("transaction_status") or verified_data.get("status") or status
    if str(verified_status).lower() != "success":
        return {"received": True, "event": event["event"], "verified_status": verified_status}

    vendor_id = data.get("vendor_id") or verified_data.get("vendor_id")
    squad_account_id = (
        data.get("squad_account_id")
        or data.get("submerchant_id")
        or verified_data.get("squad_account_id")
        or verified_data.get("submerchant_id")
    )
    vendor = None
    if vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor and squad_account_id:
        vendor = db.query(Vendor).filter(Vendor.squad_merchant_id == squad_account_id).first()

    if not vendor:
        squad_log("   No TrustGate vendor matched this Squad transaction; stored monitor skipped", "warning")
        return {"received": True, "event": event["event"], "verified_status": verified_status, "matched_vendor": False}

    transaction = db.query(Transaction).filter(Transaction.transaction_ref == transaction_ref).first()
    if not transaction:
        transaction = Transaction(
            merchant_id=vendor.id,
            squad_account_id=vendor.squad_merchant_id or squad_account_id,
            transaction_ref=transaction_ref,
            amount=int(verified_data.get("amount") or amount),
            customer_email=data.get("customer_email") or verified_data.get("customer_email") or verified_data.get("email"),
            transaction_status=verified_status,
        )
        db.add(transaction)
    else:
        transaction.transaction_status = verified_status
        transaction.amount = int(verified_data.get("amount") or amount or transaction.amount)
    db.commit()

    monitor_payload = {
        "amount": transaction.amount,
        "customer_email": transaction.customer_email or "",
        "transaction_ref": transaction.transaction_ref,
        "created_at": transaction.created_at,
    }
    background_tasks.add_task(_run_monitor_background, vendor.squad_merchant_id or vendor.id, monitor_payload)
    return {"received": True, "event": event["event"], "verified_status": verified_status, "matched_vendor": True}


@router.post("/create-merchant")
async def create_squad_merchant(payload: SquadCreateMerchantRequest, db: Session = Depends(get_db)):
    return await _create_squad_merchant_for_vendor(payload.vendor_id, db)


@router.post("/create-merchant/{vendor_id}")
async def create_squad_merchant_by_path(vendor_id: str, db: Session = Depends(get_db)):
    return await _create_squad_merchant_for_vendor(vendor_id, db)


@router.get("/merchant/{vendor_id}")
def get_squad_merchant_status(vendor_id: str, db: Session = Depends(get_db)):
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {
        "vendor_id": vendor.id,
        "has_squad_merchant": bool(vendor.squad_merchant_id),
        "squad_merchant_id": vendor.squad_merchant_id,
        "status": vendor.status,
    }
