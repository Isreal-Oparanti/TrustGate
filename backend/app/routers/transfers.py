import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.schemas.transfer import (
    SquadPassthroughResponse,
    TransferAccountLookupRequest,
    TransferInitiateRequest,
    TransferRequeryRequest,
)
from app.services.squad_api import (
    initiate_transfer,
    lookup_transfer_account,
    requery_transfer,
    verify_vendor_security_answer,
)


router = APIRouter()


def _extract_squad_data(response: dict) -> dict:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def _extract_verified_account_name(response: dict, fallback: str) -> str:
    data = _extract_squad_data(response)
    return (
        data.get("account_name")
        or data.get("accountName")
        or data.get("beneficiary_name")
        or data.get("beneficiaryName")
        or fallback
    )


def _ensure_vendor_can_transact(vendor: Vendor):
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before sending money")
    if not vendor.squad_account_id:
        raise HTTPException(status_code=409, detail="Vendor must be activated as a Squad sub-merchant first")


@router.post("/account-lookup", response_model=SquadPassthroughResponse)
def lookup_account(
    payload: TransferAccountLookupRequest,
    current_vendor: Vendor = Depends(get_current_vendor),
):
    _ensure_vendor_can_transact(current_vendor)
    try:
        squad_response = lookup_transfer_account(payload.model_dump())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad account lookup failed: {exc}") from exc
    return {"squad_response": squad_response}


@router.post("", response_model=SquadPassthroughResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SquadPassthroughResponse, status_code=status.HTTP_201_CREATED)
def send_money(
    payload: TransferInitiateRequest,
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    _ensure_vendor_can_transact(current_vendor)
    if not verify_vendor_security_answer(current_vendor, payload.security_answer):
        raise HTTPException(status_code=403, detail="Security question answer is invalid")

    try:
        lookup_response = lookup_transfer_account(
            {"bank_code": payload.bank_code, "account_number": payload.account_number}
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad account lookup failed: {exc}") from exc

    transaction_reference = f"{settings.SQUAD_PARENT_BUSINESS_ID}_{uuid.uuid4().hex[:18].upper()}"
    squad_payload = {
        "transaction_reference": transaction_reference,
        "amount": str(payload.amount),
        "bank_code": payload.bank_code,
        "account_number": payload.account_number,
        "account_name": _extract_verified_account_name(lookup_response, payload.account_name),
        "currency_id": "NGN",
        "remark": payload.remark,
    }

    try:
        squad_response = initiate_transfer(squad_payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad transfer failed: {exc}") from exc

    db.commit()
    return {"squad_response": squad_response}


@router.post("/requery", response_model=SquadPassthroughResponse)
def requery_money_transfer(
    payload: TransferRequeryRequest,
    current_vendor: Vendor = Depends(get_current_vendor),
):
    _ensure_vendor_can_transact(current_vendor)
    try:
        squad_response = requery_transfer(payload.model_dump())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Squad transfer requery failed: {exc}") from exc
    return {"squad_response": squad_response}
