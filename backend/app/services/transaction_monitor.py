from __future__ import annotations

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.flag import Flag as DBFlag
from app.models.transaction import Transaction
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.verification import Flag, FlagSeverity
from app.services.squad_api import update_merchant_status
from app.utils.logger import txn_log


@dataclass
class MonitorResult:
    merchant_id: str
    transaction_ref: str
    flags: list[Flag]
    suspended: bool
    checked_at: dt.datetime


def _amount_naira(amount_kobo: int | float | None) -> float:
    return float(amount_kobo or 0) / 100


def _as_aware(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value


def get_transaction_history(merchant_id: str, db: Session) -> list[Transaction]:
    return (
        db.query(Transaction)
        .filter(or_(Transaction.squad_account_id == merchant_id, Transaction.merchant_id == merchant_id))
        .order_by(Transaction.created_at.asc())
        .all()
    )


def _make_flag(
    flag_type: str,
    severity: FlagSeverity,
    detail: str,
    evidence: str,
    method: str,
) -> Flag:
    return Flag(
        flag_type=flag_type,
        severity=severity,
        detail=detail,
        source_doc="transaction_monitor",
        evidence=evidence,
        check_method=method,
    )


def _legacy_severity(severity: FlagSeverity) -> int:
    return {
        FlagSeverity.INFO: 0,
        FlagSeverity.LOW: 1,
        FlagSeverity.MEDIUM: 2,
        FlagSeverity.HIGH: 3,
        FlagSeverity.CRITICAL: 3,
    }[severity]


def save_transaction_flags(merchant_id: str, transaction_ref: str, flags: list[Flag], db: Session) -> None:
    if not flags:
        return
    vendor = (
        db.query(Vendor)
        .filter(or_(Vendor.squad_merchant_id == merchant_id, Vendor.id == merchant_id))
        .first()
    )
    if not vendor:
        txn_log(f"   Unable to save transaction flags — vendor not found for merchant {merchant_id}", "warning")
        return
    verification = (
        db.query(Verification)
        .filter(Verification.vendor_id == vendor.id)
        .order_by(Verification.created_at.desc())
        .first()
    )
    if not verification:
        txn_log(f"   Unable to save transaction flags — no verification row for vendor {vendor.id}", "warning")
        return

    for flag in flags:
        db.add(
            DBFlag(
                id=str(uuid.uuid4()),
                vendor_id=vendor.id,
                verification_id=verification.id,
                code=flag.flag_type.upper(),
                title=flag.flag_type.replace("_", " ").title(),
                description=f"{flag.detail} Transaction ref: {transaction_ref}.",
                severity=_legacy_severity(flag.severity),
                source="transaction_monitor",
            )
        )
    db.commit()


async def monitor_transaction(
    merchant_id: str,
    new_transaction: dict,
    db: Session,
) -> MonitorResult:
    flags: list[Flag] = []
    history = get_transaction_history(merchant_id, db)
    amount_naira = _amount_naira(new_transaction["amount"])
    total_naira = sum(txn.amount for txn in history) / 100

    txn_log(f"▶ Monitoring transaction for merchant: {merchant_id}")
    txn_log(f"   New txn: ₦{amount_naira:,.0f} from {new_transaction.get('customer_email', '')}")
    txn_log(f"   Merchant history: {len(history)} transactions | total: ₦{total_naira:,.0f}")

    now = dt.datetime.now(dt.UTC)
    week_ago = now - dt.timedelta(days=7)
    week_transactions = [txn for txn in history if _as_aware(txn.created_at) > week_ago]
    week_total = sum(txn.amount for txn in week_transactions) / 100

    if week_total > 0:
        ratio = amount_naira / week_total
        status = "PASS"
        if ratio > 10:
            flags.append(
                _make_flag(
                    "velocity_spike",
                    FlagSeverity.CRITICAL,
                    f"Transaction ₦{amount_naira:,.0f} is {ratio:.1f}x the 7-day total ₦{week_total:,.0f}",
                    f"amount={amount_naira}, week_total={week_total}, ratio={ratio:.2f}",
                    "velocity_ratio",
                )
            )
            status = "FLAG"
            txn_log(f"   [CHECK] Velocity → FLAG CRITICAL (ratio {ratio:.1f}x exceeds 10x threshold)")
        elif ratio > 5:
            flags.append(
                _make_flag(
                    "velocity_spike",
                    FlagSeverity.HIGH,
                    f"Transaction ₦{amount_naira:,.0f} is {ratio:.1f}x the 7-day total ₦{week_total:,.0f}",
                    f"amount={amount_naira}, week_total={week_total}, ratio={ratio:.2f}",
                    "velocity_ratio",
                )
            )
            status = "FLAG"
            txn_log("   [CHECK] Velocity → FLAG HIGH")
        else:
            txn_log("   [CHECK] Velocity → PASS")
        txn_log(f"   [CHECK] Velocity: 7-day total ₦{week_total:,.0f} → new txn is {ratio:.1f}x → {status}")
    else:
        txn_log(f"   [CHECK] Velocity: 7-day total ₦0 → new txn is baseline → PASS")

    if amount_naira >= 100000 and amount_naira % 50000 == 0:
        historical_round = sum(
            1
            for txn in history
            if (txn.amount / 100) >= 100000 and (txn.amount / 100) % 50000 == 0
        )
        txn_log(f"   [CHECK] Round amount: ₦{amount_naira:,.0f} | historical round txns: {historical_round}")
        if historical_round >= 2:
            flags.append(
                _make_flag(
                    "round_amount_pattern",
                    FlagSeverity.HIGH,
                    f"Repeated perfectly round amounts (₦{amount_naira:,.0f}) — {historical_round + 1} occurrences. Not typical retail behaviour.",
                    f"amount={amount_naira}, occurrences={historical_round + 1}",
                    "round_amount_pattern",
                )
            )
            txn_log(f"   [CHECK] Round amount → FLAG HIGH (pattern of {historical_round + 1} round txns)")
        else:
            flags.append(
                _make_flag(
                    "round_amount_single",
                    FlagSeverity.LOW,
                    f"Large round transaction amount ₦{amount_naira:,.0f}.",
                    f"amount={amount_naira}, historical_round={historical_round}",
                    "round_amount_pattern",
                )
            )
            txn_log("   [CHECK] Round amount → FLAG LOW (single occurrence)")
    else:
        txn_log(f"   [CHECK] Round amount: ₦{amount_naira:,.0f} → PASS")

    if len(history) >= 5:
        revenue_by_email: Counter[str] = Counter()
        for txn in history:
            if txn.customer_email:
                revenue_by_email[txn.customer_email] += txn.amount
        if new_transaction.get("customer_email"):
            revenue_by_email[new_transaction["customer_email"]] += int(new_transaction["amount"])
        total_revenue = sum(revenue_by_email.values())
        if revenue_by_email and total_revenue:
            top_email, top_amount = revenue_by_email.most_common(1)[0]
            top_pct = top_amount / total_revenue
            txn_log(f"   [CHECK] Customer diversity: top payer = {top_pct:.0%} of revenue → {'FLAG' if top_pct > 0.6 else 'PASS'}")
            if top_pct > 0.6:
                flags.append(
                    _make_flag(
                        "single_customer_concentration",
                        FlagSeverity.HIGH,
                        f"{top_pct:.0%} of revenue from one customer. Money laundering pattern.",
                        f"top_email={top_email}, amount_kobo={top_amount}, total_kobo={total_revenue}",
                        "customer_diversity",
                    )
                )
        else:
            txn_log("   [CHECK] Customer diversity: no customer emails available → PASS")
    else:
        txn_log("   [CHECK] Customer diversity: insufficient history → PASS")

    if len(history) >= 3:
        day_ago = now - dt.timedelta(hours=24)
        recent = [txn for txn in history if _as_aware(txn.created_at) > day_ago]
        recent_total = sum(txn.amount for txn in recent) / 100
        if len(recent) >= 5 and recent_total > 1_000_000:
            flags.append(
                _make_flag(
                    "rapid_volume_accumulation",
                    FlagSeverity.MEDIUM,
                    f"₦{recent_total:,.0f} accumulated in 24 hours across {len(recent)} transactions",
                    f"recent_total={recent_total}, recent_count={len(recent)}",
                    "rapid_volume_24h",
                )
            )
            txn_log("   [CHECK] Immediate withdrawal pattern: FLAG")
        else:
            txn_log("   [CHECK] Immediate withdrawal pattern: PASS")
    else:
        txn_log("   [CHECK] Immediate withdrawal pattern: PASS")

    critical_count = sum(1 for flag in flags if flag.severity in {FlagSeverity.CRITICAL, FlagSeverity.HIGH})
    txn_log(f"   Result: {len(flags)} flags raised ({critical_count} critical/high)")

    suspended = critical_count >= 2
    if suspended:
        txn_log("⚠ CRITICAL PATTERN DETECTED — initiating merchant suspension")
        await update_merchant_status(merchant_id, "blocked")
        txn_log(f"✓ Merchant {merchant_id} suspended via Squad API")
        save_transaction_flags(merchant_id, new_transaction["transaction_ref"], flags, db)

    return MonitorResult(
        merchant_id=merchant_id,
        transaction_ref=new_transaction["transaction_ref"],
        flags=flags,
        suspended=suspended,
        checked_at=now,
    )
