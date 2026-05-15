import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_vendor
from app.models.vendor import Vendor
from app.models.wallet import Wallet
from app.schemas.wallet import WalletCreateResponse, WalletOut
from app.services.squad_api import (
    create_business_virtual_account,
    query_virtual_account_transactions,
)


router = APIRouter()


SQUAD_VIRTUAL_ACCOUNT_BANKS = {
    "058": "GTBank",
    "000013": "GTBank",
}

SQUAD_BANK_CODES = set(SQUAD_VIRTUAL_ACCOUNT_BANKS)


def _is_gtbank_settlement(vendor: Vendor) -> bool:
    bank_code = (vendor.settlement_bank_code or "").strip()
    bank_name = (vendor.settlement_bank or "").strip().lower()
    return bank_code in SQUAD_BANK_CODES or "gtbank" in bank_name or "guaranty trust" in bank_name


def _ensure_vendor_active(vendor: Vendor):
    if vendor.status != "approved":
        raise HTTPException(status_code=409, detail="Vendor must be approved before creating a wallet")
    if not vendor.squad_account_id:
        raise HTTPException(status_code=409, detail="Vendor must be active as a Squad sub-merchant first")
    if not settings.SQUAD_MOCK_MODE and settings.SQUAD_SECRET_KEY and vendor.settlement_account_number:
        if not _is_gtbank_settlement(vendor):
            raise HTTPException(
                status_code=409,
                detail="Static virtual account settlement account must be a GTBank account",
            )


def _extract_wallet_data(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data")
    return data if isinstance(data, dict) else {}


def _wallet_bank_code(data: dict[str, Any], vendor: Vendor) -> str | None:
    bank_code = data.get("bank_code") or data.get("bankCode") or vendor.settlement_bank_code or vendor.bank_code
    return str(bank_code).strip() if bank_code else None


def _wallet_bank_name(data: dict[str, Any], vendor: Vendor) -> str | None:
    bank = data.get("bank") or data.get("bank_name")
    if bank:
        return str(bank)

    bank_code = _wallet_bank_code(data, vendor)
    if bank_code in SQUAD_VIRTUAL_ACCOUNT_BANKS:
        return SQUAD_VIRTUAL_ACCOUNT_BANKS[bank_code]

    fallback_bank = vendor.settlement_bank or vendor.bank_name
    if fallback_bank:
        return str(fallback_bank)

    if _is_gtbank_settlement(vendor):
        return "GTBank"

    if data.get("virtual_account_number"):
        return "GTBank"

    return None


def _wallet_account_name(data: dict[str, Any], vendor: Vendor) -> str | None:
    account_name = data.get("account_name") or data.get("business_name")
    if account_name:
        return str(account_name)
    return vendor.business_name or vendor.settlement_account_name or vendor.account_name


def _fill_missing_wallet_display_fields(wallet: Wallet, vendor: Vendor, data: dict[str, Any]) -> bool:
    changed = False

    if not wallet.account_name:
        wallet.account_name = _wallet_account_name(data, vendor)
        changed = True

    if not wallet.bank:
        wallet.bank = _wallet_bank_name(data, vendor)
        changed = True

    if not wallet.bank_code:
        wallet.bank_code = _wallet_bank_code(data, vendor)
        changed = True

    return changed


@router.post("", response_model=WalletCreateResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=WalletCreateResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    _ensure_vendor_active(current_vendor)

    existing = db.query(Wallet).filter(Wallet.vendor_id == current_vendor.id).first()
    if existing:
        data = _extract_wallet_data(existing.squad_response or {})
        if _fill_missing_wallet_display_fields(existing, current_vendor, data):
            db.commit()
            db.refresh(existing)
        return {"wallet": existing, "squad_response": {"message": "Vendor already has a virtual wallet"}}

    customer_identifier = f"TG{current_vendor.id.replace('-', '').upper()}"
    squad_response = create_business_virtual_account(
        current_vendor,
        customer_identifier=customer_identifier,
        beneficiary_account=current_vendor.settlement_account_number,
    )

    data = _extract_wallet_data(squad_response)
    wallet = Wallet(
        id=str(uuid.uuid4()),
        vendor_id=current_vendor.id,
        customer_identifier=data.get("customer_identifier") or customer_identifier,
        virtual_account_number=data.get("virtual_account_number"),
        account_name=_wallet_account_name(data, current_vendor),
        bank=_wallet_bank_name(data, current_vendor),
        bank_code=_wallet_bank_code(data, current_vendor),
        status="active",
        squad_response=squad_response,
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return {"wallet": wallet, "squad_response": squad_response}


@router.get("/me", response_model=WalletOut)
def get_my_wallet(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    wallet = db.query(Wallet).filter(Wallet.vendor_id == current_vendor.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found for current vendor")
    data = _extract_wallet_data(wallet.squad_response or {})
    if _fill_missing_wallet_display_fields(wallet, current_vendor, data):
        db.commit()
        db.refresh(wallet)
    return wallet


@router.get("/me/transactions")
def get_my_wallet_transactions(
    db: Session = Depends(get_db),
    current_vendor: Vendor = Depends(get_current_vendor),
):
    wallet = db.query(Wallet).filter(Wallet.vendor_id == current_vendor.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found for current vendor")
    return query_virtual_account_transactions(wallet.customer_identifier)
