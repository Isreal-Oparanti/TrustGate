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
        assert wallet.bank == "GTBank"
        assert wallet.account_name == vendor.business_name
    finally:
        db.close()


def test_wallet_create_normalizes_squad_business_response(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", False)
    monkeypatch.setattr(squad_api.settings, "SQUAD_SECRET_KEY", "test-secret")
    vendor_id = _create_vendor_for_wallet()

    def fake_create_business_virtual_account(_vendor, customer_identifier: str, beneficiary_account: str | None):
        return {
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "first_name": "Techzilla-Will",
                "last_name": "Okoye",
                "bank_code": "058",
                "virtual_account_number": "2474681469",
                "beneficiary_account": beneficiary_account,
                "customer_identifier": customer_identifier,
            },
        }

    monkeypatch.setattr("app.routers.wallets.create_business_virtual_account", fake_create_business_virtual_account)

    db = SessionLocal()
    try:
        vendor = _get_vendor(db, vendor_id)
        vendor.settlement_bank = "GTBank"
        vendor.settlement_bank_code = "058"
        db.commit()

        created = create_wallet(db=db, current_vendor=vendor)

        assert created["wallet"].virtual_account_number == "2474681469"
        assert created["wallet"].bank == "GTBank"
        assert created["wallet"].bank_code == "058"
        assert created["wallet"].account_name == vendor.business_name
    finally:
        db.close()


def test_existing_wallet_display_fields_are_backfilled(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    vendor_id = _create_vendor_for_wallet()
    db = SessionLocal()
    try:
        vendor = _get_vendor(db, vendor_id)
        created = create_wallet(db=db, current_vendor=vendor)
        wallet = created["wallet"]
        wallet.bank = None
        wallet.bank_code = None
        wallet.account_name = None
        db.commit()

        fetched = get_my_wallet(db=db, current_vendor=vendor)

        assert fetched.bank == "GTBank"
        assert fetched.bank_code == "058"
        assert fetched.account_name == vendor.business_name
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
