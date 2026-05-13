import uuid
from app.database import SessionLocal, verify_database_connection
from fastapi import HTTPException
from app.routers.vendors import create_vendor
from app.schemas.vendor import VendorCreate
from app.services import squad_api


def test_healthcheck_database_connection():
    assert verify_database_connection() is True


def test_vendor_can_be_created_under_platform(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        result = create_vendor(
            payload=VendorCreate(
                business_name=f"Bright Future {suffix} Ltd",
                rc_number=f"RC{suffix}",
                bvn="12345678901",
                nin="10987654321",
                email=f"ops-{suffix}@brightfuture.ng",
                phone="08012345678",
                address="12 Marina Road, Lagos",
                tier="tier3",
                settlement_account_name=f"Bright Future {suffix} Ltd",
                settlement_account_number="0123456789",
                settlement_bank_code="058",
                settlement_bank="GTBank",
                payment_security_question="What is your payment PIN?",
                payment_security_answer="demo123",
            ),
            db=db,
        )

        assert result["vendor"].business_name == f"Bright Future {suffix} Ltd"
        assert result["vendor"].squad_account_id
        assert result["squad_response"]["success"] is True
    finally:
        db.close()


def test_vendor_rejects_duplicate_business_name(monkeypatch):
    monkeypatch.setattr(squad_api.settings, "SQUAD_MOCK_MODE", True)
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        payload = VendorCreate(
            business_name=f"Unique Demo {suffix} Ltd",
            rc_number=f"RC{suffix}",
            bvn="12345678901",
            nin="10987654321",
            email=f"unique-{suffix}@example.ng",
            phone="08012345678",
            address="12 Marina Road, Lagos",
            tier="tier2",
            settlement_account_name=f"Unique Demo {suffix} Ltd",
            settlement_account_number="0123456789",
            settlement_bank_code="058",
            settlement_bank="GTBank",
            payment_security_question="What is your payment PIN?",
            payment_security_answer="demo123",
        )
        create_vendor(payload=payload, db=db)

        try:
            create_vendor(payload=payload.model_copy(update={"email": "unique-2@example.ng"}), db=db)
        except HTTPException as exc:
            assert exc.status_code == 409
            assert exc.detail == "Business name already exists"
        else:
            raise AssertionError("Duplicate business name was accepted")
    finally:
        db.close()
