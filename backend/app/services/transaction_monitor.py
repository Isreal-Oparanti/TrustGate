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
    risk_score: int
    dynamic_trust_score: int | None
    action: str
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


def _resolve_vendor(merchant_id: str, db: Session) -> Vendor | None:
    return (
        db.query(Vendor)
        .filter(or_(Vendor.squad_merchant_id == merchant_id, Vendor.squad_account_id == merchant_id, Vendor.id == merchant_id))
        .first()
    )


def _latest_verification(vendor_id: str, db: Session) -> Verification | None:
    return (
        db.query(Verification)
        .filter(Verification.vendor_id == vendor_id)
        .order_by(Verification.created_at.desc())
        .first()
    )


def _created_at_from_payload(payload: dict) -> dt.datetime:
    value = payload.get("created_at")
    if isinstance(value, dt.datetime):
        return _as_aware(value)
    return dt.datetime.now(dt.UTC)


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
    vendor = _resolve_vendor(merchant_id, db)
    if not vendor:
        txn_log(f"   Unable to save transaction flags — vendor not found for merchant {merchant_id}", "warning")
        return
    verification = _latest_verification(vendor.id, db)
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


def _risk_points(severity: FlagSeverity) -> int:
    return {
        FlagSeverity.INFO: 0,
        FlagSeverity.LOW: 6,
        FlagSeverity.MEDIUM: 14,
        FlagSeverity.HIGH: 24,
        FlagSeverity.CRITICAL: 38,
    }[severity]


def _apply_behaviour_score(
    vendor: Vendor | None,
    transaction_ref: str,
    flags: list[Flag],
    db: Session,
) -> tuple[int, int | None, str, bool]:
    risk_score = min(100, sum(_risk_points(flag.severity) for flag in flags))
    high_signal_count = sum(1 for flag in flags if flag.severity in {FlagSeverity.HIGH, FlagSeverity.CRITICAL})
    suspended = risk_score >= 65 or high_signal_count >= 2
    action = "restrict" if suspended else "review" if flags else "monitor"
    dynamic_score: int | None = None

    if vendor:
        transaction = db.query(Transaction).filter(Transaction.transaction_ref == transaction_ref).first()
        if transaction:
            transaction.flagged = bool(flags)

        verification = _latest_verification(vendor.id, db)
        if verification:
            dynamic_score = max(0, int(verification.trust_score or 0) - risk_score)
            verification.behaviour_score = max(0, int(verification.behaviour_score or 0) - risk_score)
            verification.trust_score = min(int(verification.trust_score or 0), dynamic_score)
            if suspended:
                verification.risk_level = "HIGH"
                verification.verdict = "flagged"

        if suspended:
            vendor.status = "flagged"

        db.commit()

    return risk_score, dynamic_score, action, suspended


async def monitor_transaction(
    merchant_id: str,
    new_transaction: dict,
    db: Session,
) -> MonitorResult:
    flags: list[Flag] = []
    history = get_transaction_history(merchant_id, db)
    transaction_ref = new_transaction["transaction_ref"]
    previous_history = [txn for txn in history if txn.transaction_ref != transaction_ref]
    vendor = _resolve_vendor(merchant_id, db)
    amount_naira = _amount_naira(new_transaction["amount"])
    total_naira = sum(txn.amount for txn in previous_history) / 100

    txn_log(f"▶ Monitoring transaction for merchant: {merchant_id}")
    txn_log(f"   New txn: ₦{amount_naira:,.0f} from {new_transaction.get('customer_email', '')}")
    txn_log(f"   Merchant history: {len(previous_history)} previous transactions | total: ₦{total_naira:,.0f}")

    now = _created_at_from_payload(new_transaction)
    week_ago = now - dt.timedelta(days=7)
    week_transactions = [txn for txn in previous_history if _as_aware(txn.created_at) > week_ago]
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
        txn_log("   [CHECK] Velocity: 7-day total ₦0 → new txn is baseline → PASS")

    expected_monthly = _amount_naira(getattr(vendor, "expected_monthly_volume", 0))
    if expected_monthly > 0:
        month_ago = now - dt.timedelta(days=30)
        month_total = sum(txn.amount for txn in previous_history if _as_aware(txn.created_at) > month_ago) / 100
        projected_month_total = month_total + amount_naira
        expected_ratio = projected_month_total / expected_monthly
        txn_log(
            f"   [CHECK] Expected volume: projected ₦{projected_month_total:,.0f} vs expected ₦{expected_monthly:,.0f} → {expected_ratio:.1f}x"
        )
        if expected_ratio >= 4:
            flags.append(
                _make_flag(
                    "expected_volume_breakout",
                    FlagSeverity.HIGH,
                    f"Merchant projected volume is {expected_ratio:.1f}x expected monthly volume.",
                    f"projected_month_total={projected_month_total}, expected_monthly={expected_monthly}, ratio={expected_ratio:.2f}",
                    "expected_volume_deviation",
                )
            )
        elif expected_ratio >= 2:
            flags.append(
                _make_flag(
                    "expected_volume_breakout",
                    FlagSeverity.MEDIUM,
                    f"Merchant projected volume is {expected_ratio:.1f}x expected monthly volume.",
                    f"projected_month_total={projected_month_total}, expected_monthly={expected_monthly}, ratio={expected_ratio:.2f}",
                    "expected_volume_deviation",
                )
            )

    if amount_naira >= 100000 and amount_naira % 50000 == 0:
        historical_round = sum(
            1
            for txn in previous_history
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

    if len(previous_history) >= 5:
        revenue_by_email: Counter[str] = Counter()
        for txn in previous_history:
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

    if now.hour < 5 and amount_naira >= 250000:
        flags.append(
            _make_flag(
                "odd_hour_high_value",
                FlagSeverity.MEDIUM,
                f"High-value transaction occurred at {now.hour:02d}:00, outside normal trading hours.",
                f"hour={now.hour}, amount={amount_naira}",
                "transaction_timing",
            )
        )
        txn_log("   [CHECK] Timing behaviour → FLAG MEDIUM")
    else:
        txn_log("   [CHECK] Timing behaviour → PASS")

    if len(previous_history) >= 3:
        day_ago = now - dt.timedelta(hours=24)
        recent = [txn for txn in previous_history if _as_aware(txn.created_at) > day_ago]
        recent_total = sum(txn.amount for txn in recent) / 100
        recent_total_with_new = recent_total + amount_naira
        if len(recent) >= 5 and recent_total_with_new > 1_000_000:
            flags.append(
                _make_flag(
                    "rapid_volume_accumulation",
                    FlagSeverity.MEDIUM,
                    f"₦{recent_total_with_new:,.0f} accumulated in 24 hours across {len(recent) + 1} transactions.",
                    f"recent_total={recent_total_with_new}, recent_count={len(recent) + 1}",
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

    risk_score, dynamic_score, action, suspended = _apply_behaviour_score(vendor, transaction_ref, flags, db)
    if flags:
        save_transaction_flags(merchant_id, transaction_ref, flags, db)

    if suspended:
        txn_log("⚠ CRITICAL PATTERN DETECTED — initiating merchant suspension")
        squad_id = getattr(vendor, "squad_merchant_id", None) or getattr(vendor, "squad_account_id", None) or merchant_id
        await update_merchant_status(squad_id, "flagged")
        txn_log(f"✓ Merchant {merchant_id} suspended via Squad API")

    return MonitorResult(
        merchant_id=merchant_id,
        transaction_ref=transaction_ref,
        flags=flags,
        risk_score=risk_score,
        dynamic_trust_score=dynamic_score,
        action=action,
        suspended=suspended,
        checked_at=now,
    )
