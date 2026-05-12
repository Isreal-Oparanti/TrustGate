import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.database import SessionLocal
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.routers.payments import get_payment_status, initiate_customer_payment, list_payments
from app.schemas.squad import PaymentInitiateRequest
from app.services import squad_api


def _create_approved_vendor(name: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    vendor_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO vendors (
                    id, business_name, rc_number, bvn, nin, email, phone, address,
                    tier, status, settlement_status, created_at, updated_at
                )
                VALUES (
                    :id, :business_name, :rc_number, :bvn, :nin, :email, :phone, :address,
                    :tier, :status, :settlement_status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": vendor_id,
                "business_name": f"{name} {suffix}",
                "rc_number": f"RC{suffix}",
                "bvn": "12345678901",
                "nin": "10987654321",
                "email": f"{name.lower()}-{suffix}@example.com",
                "phone": "08012345678",
                "address": "12 Marina Road, Lagos",
                "tier": "tier2",
                "status": "approved",
                "settlement_status": "not_started",
            },
        )
        db.commit()
    finally:
        db.close()
    return vendor_id


def _get_vendor(db, vendor_id: str) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    assert vendor is not None
    return vendor


def _initiate_payment(db, vendor_id: str, monkeypatch) -> dict:
    monkeypatch.setattr(squad_api.settings, "PAYMENT_SECURITY_ANSWER_HASH", "")
    monkeypatch.setattr(squad_api.settings, "PAYMENT_SECURITY_ANSWER", "answer")

    return initiate_customer_payment(
        payload=PaymentInitiateRequest(
            amount=250000,
            customer_email="customer@example.com",
            customer_name="Ada Lovelace",
            security_answer="answer",
            currency="NGN",
            payment_channels=["card", "bank"],
            metadata={"order_id": "ORD-1001"},
            pass_charge=False,
        ),
        db=db,
        current_vendor=_get_vendor(db, vendor_id),
    )


def test_payment_initiation_uses_current_vendor(monkeypatch):
    vendor_id = _create_approved_vendor("VendorPay")
    db = SessionLocal()
    try:
        response_body = _initiate_payment(db, vendor_id, monkeypatch)

        payments = list_payments(status_filter=None, db=db, current_vendor=_get_vendor(db, vendor_id))
        assert any(payment.transaction_ref == response_body["transaction_ref"] for payment in payments)
        assert all(payment.vendor_id == vendor_id for payment in payments)
    finally:
        db.close()


def test_vendor_cannot_access_another_vendors_payment(monkeypatch):
    vendor_a = _create_approved_vendor("VendorA")
    vendor_b = _create_approved_vendor("VendorB")
    db = SessionLocal()
    try:
        payment = _initiate_payment(db, vendor_a, monkeypatch)

        vendor_b_payments = list_payments(status_filter=None, db=db, current_vendor=_get_vendor(db, vendor_b))
        assert all(item.transaction_ref != payment["transaction_ref"] for item in vendor_b_payments)

        with pytest.raises(HTTPException) as exc_info:
            get_payment_status(
                transaction_ref=payment["transaction_ref"],
                db=db,
                current_vendor=_get_vendor(db, vendor_b),
            )
        assert exc_info.value.status_code == 404
    finally:
        db.close()


def test_payment_endpoints_require_current_vendor_header():
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_current_vendor(x_vendor_id=None, db=db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "X-Vendor-Id header is required"
    finally:
        db.close()
