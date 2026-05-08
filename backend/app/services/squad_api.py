import uuid
import httpx
from app.config import settings
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


def parse_webhook_event(payload: dict) -> dict:
    event_type = payload.get("event") or payload.get("type") or "unknown"
    data = payload.get("data", payload)
    return {"event": event_type, "data": data}
