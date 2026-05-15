import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.database import SessionLocal
from app.models.vendor import Vendor
from app.routers import transfers
from app.routers.transfers import lookup_account, send_money
from app.schemas.transfer import TransferAccountLookupRequest, TransferInitiateRequest
from app.services import squad_api


def _create_transfer_vendor() -> str:
    suffix = uuid.uuid4().hex[:8]
    vendor_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO vendors (
                    id, business_name, rc_number, bvn, nin, email, phone, address,
                    tier, status, squad_account_id, settlement_status, payment_security_answer_hash,
                    created_at, updated_at
                )
                VALUES (
                    :id, :business_name, :rc_number, :bvn, :nin, :email, :phone, :address,
                    :tier, :status, :squad_account_id, :settlement_status, :payment_security_answer_hash,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": vendor_id,
                "business_name": f"Transfer Vendor {suffix}",
                "rc_number": f"RC{suffix}",
                "bvn": "12345678901",
                "nin": "10987654321",
                "email": f"transfer-{suffix}@example.com",
                "phone": "08012345678",
                "address": "12 Marina Road, Lagos",
                "tier": "tier2",
                "status": "approved",
                "squad_account_id": f"mock_sub_{suffix}",
                "settlement_status": "active",
                "payment_security_answer_hash": squad_api.hash_security_answer("answer"),
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


def test_vendor_can_lookup_transfer_account(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    vendor_id = _create_transfer_vendor()
    db = SessionLocal()
    try:
        response = lookup_account(
            payload=TransferAccountLookupRequest(bank_code="000013", account_number="0123456789"),
            current_vendor=_get_vendor(db, vendor_id),
        )

        assert response["squad_response"]["success"] is True
        assert response["squad_response"]["data"]["account_number"] == "0123456789"
    finally:
        db.close()


def test_vendor_can_send_money_with_platform_reference(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    vendor_id = _create_transfer_vendor()
    db = SessionLocal()
    try:
        response = send_money(
            payload=TransferInitiateRequest(
                amount=10000,
                bank_code="000013",
                account_number="0123456789",
                account_name="Demo Recipient",
                remark="Vendor payout",
                security_answer="answer",
            ),
            db=db,
            current_vendor=_get_vendor(db, vendor_id),
        )

        transfer_ref = response["squad_response"]["data"]["transaction_reference"]
        assert transfer_ref.startswith("SBHDTWL6SR_")
    finally:
        db.close()


def test_send_money_uses_verified_lookup_account_name(monkeypatch):
    vendor_id = _create_transfer_vendor()
    captured_payload = {}

    def fake_lookup_transfer_account(_payload):
        return {
            "success": True,
            "data": {"account_name": "Verified Recipient", "account_number": "0123456789"},
        }

    def fake_initiate_transfer(payload):
        captured_payload.update(payload)
        return {"success": True, "data": payload}

    monkeypatch.setattr(transfers, "lookup_transfer_account", fake_lookup_transfer_account)
    monkeypatch.setattr(transfers, "initiate_transfer", fake_initiate_transfer)

    db = SessionLocal()
    try:
        send_money(
            payload=TransferInitiateRequest(
                amount=10000,
                bank_code="000013",
                account_number="0123456789",
                account_name="Client Supplied Name",
                remark="Vendor payout",
                security_answer="answer",
            ),
            db=db,
            current_vendor=_get_vendor(db, vendor_id),
        )

        assert captured_payload["account_name"] == "Verified Recipient"
    finally:
        db.close()


def test_transfer_timeout_status_is_preserved_for_requery(monkeypatch):
    vendor_id = _create_transfer_vendor()

    monkeypatch.setattr(
        transfers,
        "lookup_transfer_account",
        lambda _payload: {"success": True, "data": {"account_name": "Verified Recipient"}},
    )

    def fake_initiate_transfer(_payload):
        raise HTTPException(status_code=424, detail={"message": "Timeout; requery transaction before retry"})

    monkeypatch.setattr(transfers, "initiate_transfer", fake_initiate_transfer)

    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            send_money(
                payload=TransferInitiateRequest(
                    amount=10000,
                    bank_code="000013",
                    account_number="0123456789",
                    account_name="Client Supplied Name",
                    remark="Vendor payout",
                    security_answer="answer",
                ),
                db=db,
                current_vendor=_get_vendor(db, vendor_id),
            )

        assert exc_info.value.status_code == 424
    finally:
        db.close()
