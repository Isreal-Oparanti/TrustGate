import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.main import app as _app
from app.database import SessionLocal
from app.models.vendor import Vendor
from app.routers.wallets import create_wallet, get_my_wallet
from app.services import squad_api


def _create_vendor_for_wallet() -> str:
    suffix = uuid.uuid4().hex[:8]
    vendor_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.execute(
            text(
                """
                INSERT INTO vendors (
                    id, business_name, rc_number, bvn, nin, email, phone, address,
                    tier, status, squad_account_id, settlement_account_number, settlement_status,
                    created_at, updated_at
                )
                VALUES (
                    :id, :business_name, :rc_number, :bvn, :nin, :email, :phone, :address,
                    :tier, :status, :squad_account_id, :settlement_account_number, :settlement_status,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": vendor_id,
                "business_name": f"Wallet Vendor {suffix}",
                "rc_number": f"RC{suffix}",
                "bvn": "12345678901",
                "nin": "10987654321",
                "email": f"wallet-{suffix}@example.com",
                "phone": "08012345678",
                "address": "12 Marina Road, Lagos",
                "tier": "tier2",
                "status": "approved",
                "squad_account_id": f"mock_sub_{suffix}",
                "settlement_account_number": "0123456789",
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


def test_vendor_can_create_and_fetch_wallet(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    vendor_id = _create_vendor_for_wallet()
    db = SessionLocal()
    try:
        vendor = _get_vendor(db, vendor_id)
        created = create_wallet(
            db=db,
            current_vendor=vendor,
        )

        wallet = get_my_wallet(db=db, current_vendor=vendor)

        assert created["wallet"].vendor_id == vendor_id
        assert wallet.virtual_account_number
        assert wallet.customer_identifier == f"TG{vendor_id.replace('-', '').upper()}"
    finally:
        db.close()


def test_static_wallet_requires_gtbank_settlement_in_live_mode(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", False)
    monkeypatch.setattr(squad_api.settings, "SQUAD_SECRET_KEY", "test-secret")
    vendor_id = _create_vendor_for_wallet()
    db = SessionLocal()
    try:
        vendor = _get_vendor(db, vendor_id)
        vendor.settlement_bank = "Demo Bank"
        vendor.settlement_bank_code = "999999"
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            create_wallet(db=db, current_vendor=vendor)

        assert exc_info.value.status_code == 409
        assert "GTBank" in exc_info.value.detail
    finally:
        db.close()
