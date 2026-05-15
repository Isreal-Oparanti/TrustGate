from __future__ import annotations

import asyncio
import hashlib
import hmac
import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.models.payment import Payment
from app.models.vendor import Vendor
from app.utils.logger import logger, squad_log


SQUAD_BASE = settings.SQUAD_BASE_URL or settings.SQUAD_API_BASE_URL


def _squad_enabled() -> bool:
    return bool(settings.SQUAD_SECRET_KEY) and not settings.SQUAD_MOCK_MODE


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def squad_headers() -> dict[str, str]:
    return _headers()


def _vendor_attr(vendor: Any, name: str, default: str = "") -> str:
    return str(getattr(vendor, name, default) or default)


def _provider_mobile(value: str) -> str:
    mobile = value.strip().replace(" ", "").replace("-", "")
    if mobile.startswith("+"):
        mobile = mobile[1:]
    return mobile


def _amount_naira(amount_kobo: int | float | None) -> float:
    return float(amount_kobo or 0) / 100


async def _request_json(method: str, path: str, *, json_payload: dict | None = None, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(base_url=SQUAD_BASE, timeout=10.0) as client:
        response = await client.request(method, path, json=json_payload, params=params, headers=_headers())
        if response.is_error:
            squad_log(f"Squad API error {response.status_code}: {response.text}", "error")
            try:
                detail = response.json()
            except Exception:
                detail = {"message": response.text}
            raise RuntimeError(detail.get("message") or detail.get("error") or str(detail))
        return response.json()


def _request_squad(method: str, path: str, **kwargs) -> dict:
    with httpx.Client(base_url=settings.SQUAD_API_BASE_URL, timeout=30) as client:
        response = client.request(method, path, headers=squad_headers(), **kwargs)
        if response.status_code >= 400:
            try:
                body = response.json()
            except ValueError:
                body = {"message": response.text}
            message = body.get("message") or response.reason_phrase
            status_code = response.status_code if response.status_code in {400, 401, 403, 404, 412, 424} else 502
            raise HTTPException(
                status_code=status_code,
                detail={
                    "message": f"Squad API error: {message}",
                    "squad_status": response.status_code,
                    "squad_response": body,
                },
            )
        return response.json()


def _extract_data(response: dict) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


async def create_sub_merchant(vendor: Vendor) -> dict:
    payload = {
        "display_name": vendor.business_name,
        "account_name": _vendor_attr(vendor, "settlement_account_name", vendor.business_name),
        "account_number": _vendor_attr(vendor, "settlement_account_number", "0123456789"),
        "bank_code": _vendor_attr(vendor, "settlement_bank_code", "058"),
        "bank": _vendor_attr(vendor, "settlement_bank", "GTBank"),
    }

    if not _squad_enabled():
        account_id = f"mock_sub_{uuid.uuid4().hex[:10]}"
        logger.info("🟢 Squad mock sub-merchant created for vendor %s", vendor.id)
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {"account_id": account_id, "merchant_id": account_id, "parent_business_id": settings.SQUAD_PARENT_BUSINESS_ID},
            "payload": payload,
        }

    result = await _request_json("POST", "/merchant/create-sub-users", json_payload=payload)
    logger.info("🟢 Squad sub-merchant created for vendor %s", vendor.id)
    return result


def create_merchant(vendor: Vendor) -> dict:
    return _run_sync(create_sub_merchant(vendor))


def create_business_virtual_account(vendor: Vendor, customer_identifier: str, beneficiary_account: str | None) -> dict:
    payload = {
        "customer_identifier": customer_identifier,
        "business_name": vendor.business_name,
        "mobile_num": _provider_mobile(vendor.phone),
        "bvn": vendor.bvn,
    }
    if beneficiary_account:
        payload["beneficiary_account"] = beneficiary_account

    if not _squad_enabled():
        virtual_account_number = str(int(uuid.uuid4().hex[:10], 16))[:10].ljust(10, "0")
        logger.info("🟢 Squad mock business virtual account created for vendor %s", vendor.id)
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "customer_identifier": customer_identifier,
                "business_name": vendor.business_name,
                "virtual_account_number": virtual_account_number,
                "account_name": vendor.business_name,
                "bank": "GTBank",
                "bank_code": "058",
            },
            "payload": payload,
        }

    result = _request_squad("POST", "/virtual-account/business", json=payload)
    logger.info("🟢 Squad business virtual account created for vendor %s", vendor.id)
    return result


def get_virtual_account_by_identifier(customer_identifier: str) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": {}}
    return _request_squad("GET", f"/virtual-account/{customer_identifier}")


def get_virtual_account_by_number(virtual_account_number: str) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": {}}
    return _request_squad("GET", f"/virtual-account/customer/{virtual_account_number}")


def query_virtual_account_transactions(customer_identifier: str) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": []}
    return _request_squad("GET", f"/virtual-account/customer/transactions/{customer_identifier}")


def query_merchant_virtual_account_transactions(params: dict) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": {"count": 0, "rows": []}}
    return _request_squad("GET", "/virtual-account/merchant/transactions/all", params=params)


def initiate_payment(payload: dict) -> dict:
    if not _squad_enabled():
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
                "sub_merchant_id": payload.get("sub_merchant_id"),
            },
        }

    result = _request_squad("POST", "/transaction/initiate", json=payload)
    logger.info("🟢 Squad payment initiated for ref %s", payload["transaction_ref"])
    return result


def lookup_transfer_account(payload: dict) -> dict:
    if not _squad_enabled():
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "account_name": "MOCK ACCOUNT",
                "account_number": payload["account_number"],
            },
        }
    return _request_squad("POST", "/payout/account/lookup", json=payload)


def initiate_transfer(payload: dict) -> dict:
    if not _squad_enabled():
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "transaction_reference": payload["transaction_reference"],
                "response_description": "Approved or completed successfully",
                "currency_id": payload["currency_id"],
                "amount": payload["amount"],
                "account_number": payload["account_number"],
                "account_name": payload["account_name"],
            },
        }
    return _request_squad("POST", "/payout/transfer", json=payload)


def requery_transfer(payload: dict) -> dict:
    if not _squad_enabled():
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "transaction_reference": payload["transaction_reference"],
                "transaction_status": "pending",
            },
        }
    return _request_squad("POST", "/payout/requery", json=payload)


def list_transfers(params: dict) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": []}
    return _request_squad("GET", "/payout/list", params=params)


def verify_payment(transaction_ref: str) -> dict:
    if not _squad_enabled():
        logger.info("🟢 Squad mock payment verified for ref %s", transaction_ref)
        return {
            "mode": "mock",
            "status": 200,
            "success": True,
            "message": "Success",
            "data": {
                "transaction_ref": transaction_ref,
                "transaction_status": "Success",
            },
        }
    result = _request_squad("GET", f"/transaction/verify/{transaction_ref}")
    logger.info("🟢 Squad payment verified for ref %s", transaction_ref)
    return result


def query_squad_transactions(params: dict) -> dict:
    if not _squad_enabled():
        return {"mode": "mock", "status": 200, "success": True, "message": "Success", "data": []}
    return _request_squad("GET", "/transaction", params=params)


def verify_security_answer(answer: str) -> bool:
    normalized = answer.strip()
    if not normalized:
        return False

    if settings.PAYMENT_SECURITY_ANSWER_HASH:
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, settings.PAYMENT_SECURITY_ANSWER_HASH)

    if settings.PAYMENT_SECURITY_ANSWER:
        return hmac.compare_digest(normalized.lower(), settings.PAYMENT_SECURITY_ANSWER.strip().lower())

    return not _squad_enabled() or settings.APP_ENV != "production"


def hash_security_answer(answer: str) -> str:
    return hashlib.sha256(answer.strip().encode("utf-8")).hexdigest()


def verify_vendor_security_answer(vendor: Vendor, answer: str) -> bool:
    normalized = answer.strip()
    if not normalized:
        return False

    if vendor.payment_security_answer_hash:
        digest = hash_security_answer(normalized)
        return hmac.compare_digest(digest, vendor.payment_security_answer_hash)

    return verify_security_answer(normalized)


def validate_squad_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not _squad_enabled():
        return True
    if settings.APP_ENV != "production" and not signature:
        logger.warning("🟡 Accepting unsigned Squad webhook outside production")
        return True
    if not signature or not settings.SQUAD_SECRET_KEY:
        return False

    digest = hmac.new(settings.SQUAD_SECRET_KEY.encode("utf-8"), raw_body, hashlib.sha512).hexdigest().upper()
    return hmac.compare_digest(digest, signature.upper())


async def verify_webhook_signature(body: bytes, signature_header: str) -> bool:
    if not _squad_enabled():
        return True
    if not signature_header:
        return settings.APP_ENV != "production"
    expected = hmac.new(settings.SQUAD_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    valid = hmac.compare_digest(signature_header, expected)
    if not valid:
        squad_log("Webhook signature verification failed — rejecting event", "critical")
    return valid


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
    event_type = payload.get("event") or payload.get("type") or payload.get("event_type") or "unknown"
    data = payload.get("data", payload)
    return {"event": event_type, "data": data}


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
    data = _extract_data(result)
    status = data.get("transaction_status") or data.get("status") or "unknown"
    amount = _amount_naira(data.get("amount"))
    merchant = data.get("merchant_name") or data.get("merchant") or "unknown merchant"
    squad_log(f"   ✓ Transaction verified — status: {status} | amount: ₦{amount:,.0f} | merchant: {merchant}")
    return result


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
