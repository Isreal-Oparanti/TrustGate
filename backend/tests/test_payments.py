import uuid
import hashlib
import hmac
import asyncio
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from app.database import SessionLocal
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.routers import payments
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
                    tier, status, squad_account_id, settlement_status, created_at, updated_at
                )
                VALUES (
                    :id, :business_name, :rc_number, :bvn, :nin, :email, :phone, :address,
                    :tier, :status, :squad_account_id, :settlement_status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
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
                "squad_account_id": f"mock_sub_{suffix}",
                "settlement_status": "active",
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


class _WebhookRequest:
    def __init__(self, payload: dict, signature: str | None = None):
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = {}
        if signature:
            self.headers["x-squad-encrypted-body"] = signature

    async def body(self):
        return self._body


def _initiate_payment(db, vendor_id: str, monkeypatch) -> dict:
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
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


def test_payment_initiation_sends_sub_merchant_id_to_squad(monkeypatch):
    vendor_id = _create_approved_vendor("VendorSubMerchantPay")
    captured_payload = {}

    def fake_initiate_payment(payload):
        captured_payload.update(payload)
        return {
            "status": 200,
            "success": True,
            "message": "success",
            "data": {"checkout_url": "https://checkout.example/test"},
        }

    monkeypatch.setattr(payments, "initiate_payment", fake_initiate_payment)
    monkeypatch.setattr(squad_api.settings, "PAYMENT_SECURITY_ANSWER_HASH", "")
    monkeypatch.setattr(squad_api.settings, "PAYMENT_SECURITY_ANSWER", "answer")

    db = SessionLocal()
    try:
        vendor = _get_vendor(db, vendor_id)
        _initiate_payment(db, vendor_id, monkeypatch)

        assert captured_payload["sub_merchant_id"] == vendor.squad_account_id
        assert captured_payload["metadata"]["platform_business_id"] == "SBHDTWL6SR"
        assert captured_payload["payment_channels"] == ["card", "bank_transfer"]
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


def test_payment_status_preserves_squad_validation_error(monkeypatch):
    vendor_id = _create_approved_vendor("VendorVerifyError")
    db = SessionLocal()
    try:
        payment = _initiate_payment(db, vendor_id, monkeypatch)

        def fake_verify_payment(_transaction_ref):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Squad API error: Invalid transaction reference",
                    "squad_status": 400,
                    "squad_response": {
                        "status": 400,
                        "success": False,
                        "message": "Invalid transaction reference",
                        "data": {},
                    },
                },
            )

        monkeypatch.setattr(payments, "verify_payment", fake_verify_payment)

        result = get_payment_status(
            transaction_ref=payment["transaction_ref"],
            db=db,
            current_vendor=_get_vendor(db, vendor_id),
        )

        assert result["payment"].transaction_ref == payment["transaction_ref"]
        assert result["squad_verification"]["verification_error"]["squad_response"]["message"] == "Invalid transaction reference"
    finally:
        db.close()


def test_local_squad_webhook_updates_payment_without_signature(monkeypatch):
    vendor_id = _create_approved_vendor("VendorWebhook")
    db = SessionLocal()
    try:
        payment = _initiate_payment(db, vendor_id, monkeypatch)
    finally:
        db.close()

    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", False)
    monkeypatch.setattr(squad_api.settings, "APP_ENV", "development")
    monkeypatch.setattr(squad_api.settings, "SQUAD_SECRET_KEY", "test-secret")

    webhook_db = SessionLocal()
    try:
        response = asyncio.run(
            payments.receive_squad_payment_webhook(
                _WebhookRequest(
                    {
                        "Event": "charge_successful",
                        "TransactionRef": payment["transaction_ref"],
                        "Body": {
                            "transaction_ref": payment["transaction_ref"],
                            "transaction_status": "success",
                            "gateway_ref": "SQUAD_REF_123",
                            "amount": 250000,
                            "currency": "NGN",
                        },
                    }
                ),
                db=webhook_db,
            )
        )
    finally:
        webhook_db.close()

    assert response["status"] == "success"

    db = SessionLocal()
    try:
        stored_payment = db.query(payments.Payment).filter_by(transaction_ref=payment["transaction_ref"]).first()
        assert stored_payment.status == "success"
        assert stored_payment.squad_gateway_ref == "SQUAD_REF_123"
        assert stored_payment.fraud_status == "clear"
    finally:
        db.close()


def test_production_squad_webhook_updates_from_verified_squad_response(monkeypatch):
    vendor_id = _create_approved_vendor("VendorWebhookVerify")
    db = SessionLocal()
    try:
        payment = _initiate_payment(db, vendor_id, monkeypatch)
    finally:
        db.close()

    def fake_verify_payment(_transaction_ref):
        return {
            "success": True,
            "data": {
                "transaction_ref": payment["transaction_ref"],
                "transaction_status": "Success",
                "gateway_ref": "VERIFIED_REF",
                "amount": 250000,
                "currency": "NGN",
            },
        }

    monkeypatch.setattr(payments, "verify_payment", fake_verify_payment)
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", False)
    monkeypatch.setattr(squad_api.settings, "APP_ENV", "production")
    monkeypatch.setattr(squad_api.settings, "SQUAD_SECRET_KEY", "test-secret")

    request = _WebhookRequest(
        {
            "Event": "charge_successful",
            "TransactionRef": payment["transaction_ref"],
            "Body": {
                "transaction_ref": payment["transaction_ref"],
                "transaction_status": "success",
                "gateway_ref": "UNTRUSTED_WEBHOOK_REF",
                "amount": 250000,
                "currency": "NGN",
            },
        }
    )
    request.headers["x-squad-encrypted-body"] = hmac.new(
        b"test-secret", request._body, hashlib.sha512
    ).hexdigest().upper()

    webhook_db = SessionLocal()
    try:
        response = asyncio.run(payments.receive_squad_payment_webhook(request, db=webhook_db))
    finally:
        webhook_db.close()

    assert response["verified"] is True

    db = SessionLocal()
    try:
        stored_payment = db.query(payments.Payment).filter_by(transaction_ref=payment["transaction_ref"]).first()
        assert stored_payment.status == "success"
        assert stored_payment.squad_gateway_ref == "VERIFIED_REF"
    finally:
        db.close()


def test_production_squad_webhook_requires_valid_signature(monkeypatch):
    raw_body = b'{"Event":"charge_successful"}'
    secret = "test-secret"
    signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest().upper()

    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", False)
    monkeypatch.setattr(squad_api.settings, "APP_ENV", "production")
    monkeypatch.setattr(squad_api.settings, "SQUAD_SECRET_KEY", secret)

    assert squad_api.validate_squad_webhook_signature(raw_body, None) is False
    assert squad_api.validate_squad_webhook_signature(raw_body, "bad-signature") is False
    assert squad_api.validate_squad_webhook_signature(raw_body, signature) is True


def test_payment_endpoints_require_current_vendor_header():
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            get_current_vendor(x_vendor_id=None, db=db)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "X-Vendor-Id header is required"
    finally:
        db.close()
