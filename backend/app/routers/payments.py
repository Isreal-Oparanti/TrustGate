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
    run_payment_fraud_monitoring,
    validate_squad_webhook_signature,
    verify_payment,
    verify_vendor_security_answer,
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
    payment.status = _status_from_squad(squad_data.get("transaction_status") or squad_data.get("status"))
    payment.squad_gateway_ref = squad_data.get("gateway_ref") or squad_data.get("gateway_transaction_ref")
    payment.squad_transaction_type = squad_data.get("transaction_type")
    payment.squad_response = squad_response
    fraud_status, fraud_notes = run_payment_fraud_monitoring(payment, squad_data)
    payment.fraud_status = fraud_status
    payment.fraud_notes = fraud_notes


def _verify_payment_best_effort(transaction_ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        return verify_payment(transaction_ref), None
    except HTTPException as exc:
        return None, {
            "status_code": exc.status_code,
            "detail": exc.detail,
        }
    except Exception as exc:
        return None, {
            "status_code": 502,
            "detail": {"message": f"Squad verify payment failed: {exc}"},
        }


@router.post("/initiate", response_model=PaymentInitiateResponse, status_code=status.HTTP_201_CREATED)
def initiate_customer_payment(
    payload: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    vendor = _get_vendor_or_404(db, current_vendor.id)
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before accepting payments")
    if not vendor.squad_account_id:
        raise HTTPException(status_code=409, detail="Vendor must be activated as a Squad sub-merchant first")
    if not verify_vendor_security_answer(vendor, payload.security_answer):
        raise HTTPException(status_code=403, detail="Security question answer is invalid")

    transaction_ref = f"TG{uuid.uuid4().hex[:20].upper()}"
    metadata = {
        **payload.metadata,
        "platform_business_id": settings.SQUAD_PARENT_BUSINESS_ID,
        "vendor_id": vendor.id,
        "vendor_business_name": vendor.business_name,
        "squad_sub_merchant_id": vendor.squad_account_id,
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
        "sub_merchant_id": vendor.squad_account_id,
    }

    try:
        squad_response = initiate_payment(squad_payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"message": f"Squad initiate payment failed: {exc}"}) from exc

    squad_data = _extract_squad_data(squad_response)
    squad_verification, squad_verification_error = _verify_payment_best_effort(transaction_ref)
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
        squad_response={
            "initiate": squad_response,
            "verification": squad_verification,
            "verification_error": squad_verification_error,
        },
    )
    if squad_verification:
        verification_data = _extract_squad_data(squad_verification)
        if verification_data:
            _update_payment_from_squad(payment, verification_data, payment.squad_response)
    db.add(payment)
    db.commit()

    return {
        "transaction_ref": payment.transaction_ref,
        "status": payment.status,
        "checkout_url": payment.checkout_url,
        "security_challenge_verified": payment.security_challenge_verified,
        "squad_response": squad_response,
        "squad_verification": squad_verification,
        "squad_verification_error": squad_verification_error,
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


@router.get("/security-question")
def get_payment_security_question(current_vendor: Vendor = Depends(get_current_vendor)):
    return {
        "question": current_vendor.payment_security_question or settings.PAYMENT_SECURITY_QUESTION,
        "required": True,
    }


@router.get("/{transaction_ref}", response_model=PaymentStatusResponse)
def get_payment_status(
    transaction_ref: str,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    payment = _get_vendor_payment_or_404(db, current_vendor, transaction_ref)

    try:
        squad_response = verify_payment(transaction_ref)
    except HTTPException as exc:
        if exc.status_code != 400:
            raise
        squad_response = {
            "success": False,
            "message": "Local payment exists, but Squad could not verify the reference yet.",
            "verification_error": exc.detail,
        }
        payment.squad_response = {
            "previous": payment.squad_response,
            "verification_error": exc.detail,
        }
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=502, detail={"message": f"Squad verify payment failed: {exc}"}) from exc

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
        squad_verification, squad_verification_error = _verify_payment_best_effort(transaction_ref)
        squad_data = _extract_squad_data(squad_verification or {})
        verified = bool(squad_data)
        squad_response = {
            "webhook": payload,
            "verification": squad_verification,
            "verification_error": squad_verification_error,
        }
        if squad_data:
            _update_payment_from_squad(payment, squad_data, squad_response)
        elif settings.APP_ENV != "production":
            squad_response["verification_fallback"] = "Used webhook body because Squad verification was unavailable outside production."
            _update_payment_from_squad(payment, body, squad_response)
        else:
            payment.squad_response = squad_response
            payment.fraud_status = "review"
            payment.fraud_notes = "Squad webhook received, but server-side verification failed. Payment status was not updated."
    else:
        payment.squad_response = payload
        payment.fraud_status = "not_run"
        payment.fraud_notes = f"Ignored unsupported Squad event: {event}."
        verified = False

    db.commit()
    return {
        "received": True,
        "event": event,
        "transaction_ref": transaction_ref,
        "status": payment.status,
        "verified": verified,
    }
