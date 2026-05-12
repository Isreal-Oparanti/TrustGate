import json
import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_vendor
from app.models.payment import Payment
from app.models.vendor import Vendor
from app.schemas.squad import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentOut,
    PaymentStatusResponse,
)
from app.services.squad_api import (
    initiate_payment,
    query_squad_transactions,
    run_payment_fraud_monitoring,
    validate_squad_webhook_signature,
    verify_payment,
    verify_security_answer,
)


router = APIRouter()
webhook_router = APIRouter()


def _get_vendor_or_404(db: Session, vendor_id: str) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return vendor


def _get_vendor_payment_or_404(db: Session, current_vendor: Vendor, transaction_ref: str) -> Payment:
    payment = (
        db.query(Payment)
        .filter(Payment.vendor_id == current_vendor.id, Payment.transaction_ref == transaction_ref)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


def _status_from_squad(value: str | None) -> str:
    normalized = (value or "pending").strip().lower()
    if normalized == "success":
        return "success"
    if normalized in {"failed", "abandoned", "pending"}:
        return normalized
    return "pending"


def _extract_squad_data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def _update_payment_from_squad(payment: Payment, squad_data: dict[str, Any], squad_response: dict[str, Any]):
    payment.status = _status_from_squad(squad_data.get("transaction_status"))
    payment.squad_gateway_ref = squad_data.get("gateway_ref") or squad_data.get("gateway_transaction_ref")
    payment.squad_transaction_type = squad_data.get("transaction_type")
    payment.squad_response = squad_response
    fraud_status, fraud_notes = run_payment_fraud_monitoring(payment, squad_data)
    payment.fraud_status = fraud_status
    payment.fraud_notes = fraud_notes


@router.post("/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_201_CREATED)
def initiate_customer_payment(
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    vendor = _get_vendor_or_404(db, current_vendor.id)
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before accepting payments")
    if not verify_security_answer(payload.security_answer):
        raise HTTPException(status_code=403, detail="Security question answer is invalid")

    transaction_ref = f"TG-{uuid.uuid4().hex[:20].upper()}"
    metadata = {
        **payload.metadata,
        "vendor_id": vendor.id,
        "vendor_business_name": vendor.business_name,
    }
    squad_payload = {
        "amount": payload.amount,
        "email": str(payload.customer_email),
        "currency": payload.currency.value,
        "initiate_type": "inline",
        "transaction_ref": transaction_ref,
        "customer_name": payload.customer_name,
        "callback_url": payload.callback_url or settings.PAYMENT_CALLBACK_URL,
        "payment_channels": [channel.value for channel in payload.payment_channels],
        "metadata": metadata,
        "pass_charge": payload.pass_charge,
    }

    try:
        squad_response = initiate_payment(squad_payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad initiate payment failed: {exc}") from exc

    squad_data = _extract_squad_data(squad_response)
    payment = Payment(
        id=str(uuid.uuid4()),
        vendor_id=vendor.id,
        transaction_ref=transaction_ref,
        customer_email=str(payload.customer_email),
        customer_name=payload.customer_name,
        amount=payload.amount,
        currency=payload.currency.value,
        status="pending",
        checkout_url=squad_data.get("checkout_url"),
        security_challenge_verified=True,
        fraud_status="not_run",
        metadata_json=metadata,
        squad_response=squad_response,
    )
    db.add(payment)
    db.commit()

    return {
        "transaction_ref": payment.transaction_ref,
        "status": payment.status,
        "checkout_url": payment.checkout_url,
        "security_challenge_verified": payment.security_challenge_verified,
        "squad_response": squad_response,
    }


@router.get("", response_model=list[PaymentOut])
@router.get("/", response_model=list[PaymentOut])
def list_payments(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    query = db.query(Payment).filter(Payment.vendor_id == current_vendor.id)
    if status_filter:
        query = query.filter(Payment.status == status_filter)
    return query.order_by(Payment.created_at.desc()).all()


@router.get("/squad-history")
def list_squad_payment_history(
    currency: str = Query(default="NGN"),
    start_date: str = Query(...),
    end_date: str = Query(...),
    page: int = Query(default=1, ge=1),
    perpage: int = Query(default=50, ge=1, le=100),
    reference: str = Query(...),
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    _get_vendor_payment_or_404(db, current_vendor, reference)
    params: dict[str, Any] = {
        "currency": currency,
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "perpage": perpage,
        "reference": reference,
    }
    try:
        return query_squad_transactions(params)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad transaction history failed: {exc}") from exc


@router.get("/security-question")
def get_payment_security_question(current_vendor: Vendor = Depends(get_current_vendor)):
    return {"question": settings.PAYMENT_SECURITY_QUESTION, "required": True}


@router.get("/{transaction_ref}", response_model=PaymentStatusResponse)
def get_payment_status(
    transaction_ref: str,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    payment = _get_vendor_payment_or_404(db, current_vendor, transaction_ref)

    try:
        squad_response = verify_payment(transaction_ref)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad verify payment failed: {exc}") from exc

    squad_data = _extract_squad_data(squad_response)
    if squad_data:
        _update_payment_from_squad(payment, squad_data, squad_response)
        db.commit()
        db.refresh(payment)

    return {"payment": payment, "squad_verification": squad_response}


@webhook_router.post("/squad")
async def receive_squad_payment_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-squad-encrypted-body")
    if not validate_squad_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=401, detail="Invalid Squad webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload") from exc

    event = payload.get("Event") or payload.get("event") or "unknown"
    body = payload.get("Body") or payload.get("body") or {}
    transaction_ref = payload.get("TransactionRef") or body.get("transaction_ref")
    if not transaction_ref:
        raise HTTPException(status_code=400, detail="Webhook missing transaction reference")

    payment = db.query(Payment).filter(Payment.transaction_ref == transaction_ref).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if event == "charge_successful":
        _update_payment_from_squad(payment, body, payload)
    else:
        payment.squad_response = payload
        payment.fraud_status = "not_run"
        payment.fraud_notes = f"Ignored unsupported Squad event: {event}."

    db.commit()
    return {"received": True, "event": event, "transaction_ref": transaction_ref, "status": payment.status}
