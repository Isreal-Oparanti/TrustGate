import pytest
from pydantic import ValidationError

from app.schemas.vendor import VendorCreate


def valid_vendor_payload(**overrides):
    payload = {
        "business_name": "Schema Demo Ltd",
        "rc_number": "RC12345",
        "bvn": "12345678901",
        "nin": "10987654321",
        "email": "schema-demo@example.ng",
        "phone": "08012345678",
        "address": "12 Marina Road, Lagos",
        "tier": "tier3",
        "settlement_account_name": "Schema Demo Ltd",
        "settlement_account_number": "0123456789",
        "settlement_bank_code": "058",
        "settlement_bank": "GTBank",
        "payment_security_question": "What is your payment PIN?",
        "payment_security_answer": "demo123",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("rc_number", "message"),
    [
        ("RC123", "RC number must be between 6 and 13 characters."),
        ("RC123456789012", "RC number must be between 6 and 13 characters."),
    ],
)
def test_vendor_rejects_invalid_rc_number_lengths(rc_number, message):
    with pytest.raises(ValidationError) as exc_info:
        VendorCreate(**valid_vendor_payload(rc_number=rc_number))

    assert message in str(exc_info.value)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("bvn", "1234567890", "BVN must be exactly 11 numeric characters."),
        ("bvn", "1234567890A", "BVN must be exactly 11 numeric characters."),
        ("nin", "109876543210", "NIN must be exactly 11 numeric characters."),
        ("nin", "1098765432A", "NIN must be exactly 11 numeric characters."),
    ],
)
def test_vendor_rejects_invalid_bvn_and_nin_values(field, value, message):
    with pytest.raises(ValidationError) as exc_info:
        VendorCreate(**valid_vendor_payload(**{field: value}))

    assert message in str(exc_info.value)
