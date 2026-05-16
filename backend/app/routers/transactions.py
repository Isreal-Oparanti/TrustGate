from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.payment import Payment
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionOut, TransactionStats


router = APIRouter()


def _is_flagged(status: str | None) -> bool:
    return (status or "").lower() in {"review", "flagged", "blocked", "suspended"}


def _flag_type(status: str | None, notes: str | None = None) -> str | None:
    if not _is_flagged(status):
        return None
    if notes:
        return notes.split(".")[0][:80]
    return "Review required"


def _payment_to_transaction(payment: Payment) -> TransactionOut:
    vendor = payment.vendor
    return TransactionOut(
        id=payment.id,
        merchant_id=payment.vendor_id,
        transaction_ref=payment.transaction_ref,
        amount=payment.amount,
        customer_email=payment.customer_email,
        transaction_status=payment.status,
        flagged=_is_flagged(payment.fraud_status),
        created_at=payment.created_at,
        business_name=vendor.business_name if vendor else None,
        rc_number=vendor.rc_number if vendor else None,
        flag_type=_flag_type(payment.fraud_status, payment.fraud_notes),
    )


def _webhook_transaction_to_out(transaction: Transaction) -> TransactionOut:
    vendor = transaction.vendor
    return TransactionOut(
        id=transaction.id,
        merchant_id=transaction.merchant_id,
        transaction_ref=transaction.transaction_ref,
        amount=transaction.amount,
        customer_email=transaction.customer_email,
        transaction_status=transaction.transaction_status,
        flagged=bool(transaction.flagged),
        created_at=transaction.created_at,
        business_name=vendor.business_name if vendor else None,
        rc_number=vendor.rc_number if vendor else None,
        flag_type="Behaviour anomaly" if transaction.flagged else None,
    )


def _list_transaction_feed(db: Session, limit: int = 100) -> list[TransactionOut]:
    payments = (
        db.query(Payment)
        .options(joinedload(Payment.vendor))
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .all()
    )
    feed = [_payment_to_transaction(payment) for payment in payments]
    payment_refs = {item.transaction_ref for item in feed}

    remaining = max(limit - len(feed), 0)
    if remaining:
        webhook_transactions = (
            db.query(Transaction)
            .options(joinedload(Transaction.vendor))
            .filter(~Transaction.transaction_ref.in_(payment_refs) if payment_refs else True)
            .order_by(Transaction.created_at.desc())
            .limit(remaining)
            .all()
        )
        feed.extend(_webhook_transaction_to_out(transaction) for transaction in webhook_transactions)

    return sorted(feed, key=lambda item: item.created_at, reverse=True)[:limit]


@router.get("", response_model=list[TransactionOut])
@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: Session = Depends(get_db),
):
    return _list_transaction_feed(db, limit=limit)


@router.get("/stats", response_model=TransactionStats)
def get_transaction_stats(db: Session = Depends(get_db)):
    today = dt.datetime.now(dt.UTC).date()
    transactions = [item for item in _list_transaction_feed(db, limit=500) if item.created_at.date() == today]
    merchant_volume: dict[str, int] = defaultdict(int)

    for transaction in transactions:
        merchant_volume[transaction.business_name or transaction.merchant_id] += transaction.amount

    return {
        "total_volume": sum(transaction.amount for transaction in transactions),
        "transactions": len(transactions),
        "flagged": sum(1 for transaction in transactions if transaction.flagged),
        "suspended": sum(1 for transaction in transactions if "suspend" in transaction.transaction_status.lower()),
        "top_merchants": [
            {"name": name, "volume": volume}
            for name, volume in sorted(merchant_volume.items(), key=lambda item: item[1], reverse=True)[:3]
        ],
    }
