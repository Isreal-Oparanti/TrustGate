import hashlib
import hmac
import uuid
import httpx
from app.config import settings
from app.models.payment import Payment
from app.models.vendor import Vendor
from app.utils.logger import logger


def create_merchant(vendor: Vendor) -> dict:
    payload = {
        "business_name": vendor.business_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "rc_number": vendor.rc_number,
    }

    if settings.SQUAD_MOCK_MODE or not settings.SQUAD_SECRET_KEY:
        merchant_id = f"mock_squad_{uuid.uuid4().hex[:10]}"
        logger.info("🟢 Squad mock merchant created for vendor %s", vendor.id)
        return {"mode": "mock", "merchant_id": merchant_id, "payload": payload}

    headers = {"Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}"}
    with httpx.Client(base_url=settings.SQUAD_API_BASE_URL, timeout=20) as client:
        response = client.post("/merchant/create", json=payload, headers=headers)
        response.raise_for_status()
        logger.info("🟢 Squad merchant created for vendor %s", vendor.id)
        return response.json()


def squad_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def initiate_payment(payload: dict) -> dict:
    if settings.SQUAD_MOCK_MODE or not settings.SQUAD_SECRET_KEY:
        transaction_ref = payload["transaction_ref"]
        checkout_url = f"https://sandbox-pay.squadco.com/{transaction_ref}"
        logger.info("🟢 Squad mock payment initiated for ref %s", transaction_ref)
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "success",
            "data": {
                "checkout_url": checkout_url,
                "transaction_ref": transaction_ref,
                "transaction_amount": payload["amount"],
                "currency": payload["currency"],
                "authorized_channels": payload.get("payment_channels", []),
            },
        }

    with httpx.Client(base_url=settings.SQUAD_API_BASE_URL, timeout=30) as client:
        response = client.post("/transaction/initiate", json=payload, headers=squad_headers())
        response.raise_for_status()
        logger.info("🟢 Squad payment initiated for ref %s", payload["transaction_ref"])
        return response.json()


def verify_payment(transaction_ref: str) -> dict:
    if settings.SQUAD_MOCK_MODE or not settings.SQUAD_SECRET_KEY:
        logger.info("🟢 Squad mock payment verified for ref %s", transaction_ref)
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "transaction_ref": transaction_ref,
                "transaction_status": "Pending",
            },
        }

    with httpx.Client(base_url=settings.SQUAD_API_BASE_URL, timeout=20) as client:
        response = client.get(f"/transaction/verify/{transaction_ref}", headers=squad_headers())
        response.raise_for_status()
        logger.info("🟢 Squad payment verified for ref %s", transaction_ref)
        return response.json()


def query_squad_transactions(params: dict) -> dict:
    if settings.SQUAD_MOCK_MODE or not settings.SQUAD_SECRET_KEY:
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": []}

    with httpx.Client(base_url=settings.SQUAD_API_BASE_URL, timeout=30) as client:
        response = client.get("/transaction", params=params, headers=squad_headers())
        response.raise_for_status()
        return response.json()


def verify_security_answer(answer: str) -> bool:
    normalized = answer.strip()
    if not normalized:
        return False

    if settings.PAYMENT_SECURITY_ANSWER_HASH:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, settings.PAYMENT_SECURITY_ANSWER_HASH)

    if settings.PAYMENT_SECURITY_ANSWER:
        return hmac.compare_digest(normalized.lower(), settings.PAYMENT_SECURITY_ANSWER.strip().lower())

    return settings.SQUAD_MOCK_MODE or settings.APP_ENV != "production"


def validate_squad_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if settings.SQUAD_MOCK_MODE:
        return True
    if not signature or not settings.SQUAD_SECRET_KEY:
        return False

    digest = hmac.new(settings.SQUAD_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512).hexdigest().upper()
    return hmac.compare_digest(digest, signature.upper())


def run_payment_fraud_monitoring(payment: Payment, squad_data: dict | None = None) -> tuple[str, str]:
    notes: list[str] = []
    status = "clear"
    data = squad_data or {}

    if payment.amount >= 500000:
        status = "review"
        notes.append("High-value transaction requires review.")

    transaction_status = str(data.get("transaction_status") or "").lower()
    if transaction_status and transaction_status != "success":
        status = "review"
        notes.append(f"Squad returned non-success status: {data.get('transaction_status')}.")

    if data.get("currency") and data["currency"] != payment.currency:
        status = "review"
        notes.append("Currency mismatch between local payment and Squad webhook.")

    if data.get("amount"):
        try:
            squad_amount = int(data["amount"])
        except (TypeError, ValueError):
            squad_amount = None
        if squad_amount != payment.amount:
            status = "review"
            notes.append("Amount mismatch between local payment and Squad webhook.")

    return status, " ".join(notes) or "No fraud indicators detected."


def parse_webhook_event(payload: dict) -> dict:
    event_type = payload.get("event") or payload.get("type") or "unknown"
    data = payload.get("data", payload)
    return {"event": event_type, "data": data}
