import uuid
from fastapi import HTTPException
import pytest
from app.database import SessionLocal
from app.models.vendor import Vendor
from app.routers.payments import initiate_customer_payment
from app.routers.vendors import create_vendor, update_vendor_status
from app.schemas.squad import PaymentInitiateRequest
from app.schemas.vendor import VendorCreate, VendorStatusUpdate
from app.services import squad_api


def test_sub_merchant_vendor_can_initiate_payment_with_own_security_answer(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    suffix = f"{uuid.uuid4().int % 1_000_000:06d}"
    db = SessionLocal()
    try:
        result = create_vendor(
            payload=VendorCreate(
                business_name=f"Sub Merchant Demo {suffix} Ltd",
                rc_number=f"RC{suffix}",
                bvn="22345678901",
                nin="10987654321",
                email=f"submerchant-{suffix}@example.com",
                phone="08012345678",
                address="12 Marina Road, Lagos",
                tier="tier2",
                settlement_account_name=f"Sub Merchant Demo {suffix} Ltd",
                settlement_account_number="0123456789",
                settlement_bank_code="058",
                settlement_bank="GTBank",
                payment_security_question="What is the test answer?",
                payment_security_answer="sub-demo-answer",
            ),
            db=db,
        )
        vendor = update_vendor_status(result["vendor"].id, VendorStatusUpdate(status="approved"), db=db)

        assert vendor.squad_account_id
        assert vendor.settlement_status == "active"
        assert vendor.payment_security_question == "What is the test answer?"

        payment = initiate_customer_payment(
            payload=PaymentInitiateRequest(
                amount=250000,
                customer_email="customer@example.com",
                customer_name="Ada Lovelace",
                security_answer="sub-demo-answer",
                currency="NGN",
            ),
            db=db,
            current_vendor=vendor,
        )

        assert payment["transaction_ref"].startswith("TG")
        assert "-" not in payment["transaction_ref"]
    finally:
        db.close()


def test_sub_merchant_vendor_rejects_wrong_security_answer(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    suffix = f"{uuid.uuid4().int % 1_000_000:06d}"
    db = SessionLocal()
    try:
        result = create_vendor(
            payload=VendorCreate(
                business_name=f"Sub Merchant Reject {suffix} Ltd",
                rc_number=f"RC{suffix}",
                bvn="22345678901",
                nin="10987654321",
                email=f"submerchant-reject-{suffix}@example.com",
                phone="08012345678",
                address="12 Marina Road, Lagos",
                tier="tier2",
                settlement_account_name=f"Sub Merchant Reject {suffix} Ltd",
                settlement_account_number="0123456789",
                settlement_bank_code="058",
                settlement_bank="GTBank",
                payment_security_question="What is the test answer?",
                payment_security_answer="right-answer",
            ),
            db=db,
        )
        vendor: Vendor = update_vendor_status(result["vendor"].id, VendorStatusUpdate(status="approved"), db=db)

        with pytest.raises(HTTPException) as exc_info:
            initiate_customer_payment(
                payload=PaymentInitiateRequest(
                    amount=250000,
                    customer_email="customer@example.com",
                    customer_name="Ada Lovelace",
                    security_answer="wrong-answer",
                    currency="NGN",
                ),
                db=db,
                current_vendor=vendor,
            )

        assert exc_info.value.status_code == 403
    finally:
        db.close()
