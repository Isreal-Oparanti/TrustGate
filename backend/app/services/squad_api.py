from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from typing import Any

import httpx

from app.config import settings
from app.models.vendor import Vendor
from app.utils.logger import squad_log


SQUAD_BASE = settings.SQUAD_BASE_URL or settings.SQUAD_API_BASE_URL


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def _amount_naira(amount_kobo: int | float | None) -> float:
    return float(amount_kobo or 0) / 100


def _vendor_attr(vendor: Any, name: str, default: str = "") -> str:
    return str(getattr(vendor, name, default) or default)


def _squad_enabled() -> bool:
    return bool(settings.SQUAD_SECRET_KEY) and not settings.SQUAD_MOCK_MODE


async def _request_json(method: str, path: str, *, json_payload: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=SQUAD_BASE, timeout=10.0) as client:
        response = await client.request(method, path, json=json_payload, headers=_headers())
        if response.is_error:
            squad_log(f"Squad API error {response.status_code}: {response.text}", "error")
            try:
                detail = response.json()
            except Exception:
                detail = {"message": response.text}
            raise RuntimeError(detail.get("message") or detail.get("error") or str(detail))
        return response.json()


async def create_sub_merchant(vendor: Vendor) -> dict:
    """
    Creates a Squad sub-merchant for an approved vendor.
    Called after trust score >= 70.
    """

    squad_log(f"▶ Creating Squad sub-merchant for: {vendor.business_name}")
    squad_log("   Endpoint: POST /merchant/create-sub-users")
    payload = {
        "display_name": vendor.business_name,
        "account_name": _vendor_attr(vendor, "account_name", vendor.business_name),
        "account_number": _vendor_attr(vendor, "account_number", "0123456789"),
        "bank_code": _vendor_attr(vendor, "bank_code", "058"),
        "bank": _vendor_attr(vendor, "bank_name", "GTBank"),
    }

    if not _squad_enabled():
        account_id = f"mock_squad_{uuid.uuid4().hex[:10]}"
        squad_log(f"   ✓ Sub-merchant created — account_id: {account_id}")
        squad_log("   Saving squad_account_id to vendor record...")
        return {"mode": "mock", "account_id": account_id, "merchant_id": account_id, "payload": payload}

    result = await _request_json("POST", "/merchant/create-sub-users", json_payload=payload)
    data = result.get("data", result)
    account_id = data.get("account_id") or data.get("merchant_id") or data.get("id")
    squad_log(f"   ✓ Sub-merchant created — account_id: {account_id}")
    squad_log("   Saving squad_account_id to vendor record...")
    return result


async def create_virtual_account(vendor: Vendor, squad_account_id: str) -> dict:
    squad_log(f"▶ Creating virtual account for: {vendor.business_name}")
    squad_log("   Endpoint: POST /virtual-account/create")
    squad_log("   Squad applies strict BVN validation here as a second fraud-prevention layer.")
    squad_log("   Instant settlement requires GTCO bank accounts.")
    payload = {
        "customer_identifier": squad_account_id,
        "business_name": vendor.business_name,
        "bvn": vendor.bvn,
        "bank_code": _vendor_attr(vendor, "bank_code", "058"),
    }
    if not _squad_enabled():
        return {
            "mode": "mock",
            "account_number": "0001234567",
            "bank_name": "GTBank",
            "customer_identifier": squad_account_id,
            "payload": payload,
        }
    return await _request_json("POST", "/virtual-account/create", json_payload=payload)


async def initiate_payment(
    vendor_squad_id: str,
    amount_kobo: int,
    customer_email: str,
    transaction_ref: str,
    callback_url: str,
) -> dict:
    amount = _amount_naira(amount_kobo)
    squad_log(f"▶ Initiating payment for merchant {vendor_squad_id}")
    squad_log(f"   amount: ₦{amount:,.0f} | ref: {transaction_ref} | customer: {customer_email}")
    payload = {
        "amount": amount_kobo,
        "email": customer_email,
        "transaction_ref": transaction_ref,
        "callback_url": callback_url,
        "submerchant_id": vendor_squad_id,
    }
    if not _squad_enabled():
        return {
            "mode": "mock",
            "checkout_url": f"https://sandbox-checkout.squadco.com/pay/{transaction_ref}",
            "payload": payload,
        }
    return await _request_json("POST", "/transaction/initiate", json_payload=payload)


async def verify_transaction(transaction_ref: str) -> dict:
    squad_log(f"▶ Verifying transaction: {transaction_ref}")
    if not _squad_enabled():
        result = {
            "transaction_ref": transaction_ref,
            "transaction_status": "Success",
            "amount": 500000,
            "merchant_name": "Mock Squad Merchant",
        }
        squad_log("   ✓ Transaction verified — status: Success | amount: ₦5,000")
        return result

    result = await _request_json("GET", f"/transaction/verify/{transaction_ref}")
    data = result.get("data", result)
    status = data.get("transaction_status") or data.get("status") or "unknown"
    amount = _amount_naira(data.get("amount"))
    merchant = data.get("merchant_name") or data.get("merchant") or "unknown merchant"
    squad_log(f"   ✓ Transaction verified — status: {status} | amount: ₦{amount:,.0f} | merchant: {merchant}")
    return result


async def update_merchant_status(squad_account_id: str, verdict: str) -> dict:
    status_map = {
        "approved": "active",
        "review": "pending",
        "blocked": "restricted",
    }
    new_status = status_map.get(verdict, verdict)
    squad_log(f"▶ Updating Squad merchant status — merchant_id: {squad_account_id}")
    squad_log(f"   old status: inferred | new status: {new_status} | reason: TrustGate verdict={verdict}")
    payload = {"status": new_status}
    if not _squad_enabled():
        return {"mode": "mock", "account_id": squad_account_id, "status": new_status, "payload": payload}
    return await _request_json("PATCH", f"/merchant/{squad_account_id}/status", json_payload=payload)


async def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    signature = signature_header or ""
    expected = hmac.new(
        settings.SQUAD_SECRET_KEY.encode(),
        body,
        hashlib.sha512,
    ).hexdigest()
    valid = hmac.compare_digest(signature, expected)
    if not valid:
        squad_log("Webhook signature verification failed — rejecting event", "critical")
    return valid


def parse_webhook_event(payload: dict) -> dict:
    event_type = payload.get("event") or payload.get("type") or payload.get("event_type") or "unknown"
    data = payload.get("data", payload)
    return {"event": event_type, "data": data}


def _run_sync(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    if loop.is_running():
        raise RuntimeError("Cannot run Squad async helper synchronously inside an active event loop")
    return loop.run_until_complete(coro)


def create_merchant(vendor: Vendor) -> dict:
    """Backward-compatible wrapper used by older synchronous code paths."""
    return _run_sync(create_sub_merchant(vendor))
