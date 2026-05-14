"""
TrustGate - Full Pipeline Demo
Run: python test_full_pipeline_demo.py

Shows the complete verification loop from document submission to Squad merchant
creation and post-approval transaction monitoring. Every component logs to the
terminal in real time.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from types import SimpleNamespace

from app.database import Base, SessionLocal, engine
from app.models.transaction import Transaction
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.schemas.verification import FlagSeverity
from app.services.agentic_verification import agent_flags_to_legacy, run_agentic_verification_async
from app.services.anomaly import detect_anomalies
from app.services.nlp import run_nlp_pipeline
from app.services.squad_api import create_sub_merchant
from app.services.transaction_monitor import monitor_transaction
from test_nlp_demo import FRAUD_OCR_OUTPUT, FRAUD_VENDOR_SUBMISSION, MOCK_OCR_OUTPUT, MOCK_VENDOR_SUBMISSION


print("=" * 70)
print("TRUSTGATE FULL PIPELINE DEMO")
print("Nigeria Squad Hack 2026")
print("=" * 70)


CLEAN_VENDOR = {
    **MOCK_VENDOR_SUBMISSION,
    "bvn": "22222222222",
    "nin": "12345678901",
    "email": "ops@zephyrdigital.ng",
    "phone": "08012345678",
    "bank_code": "058",
    "bank_name": "GTBank",
    "account_number": "0123456789",
    "account_name": "Zephyr Digital Supplies Ltd",
}

FRAUD_VENDOR = {
    **FRAUD_VENDOR_SUBMISSION,
    "bvn": "11111111111",
    "nin": "12345678901",
    "email": "northgate@gmail.com",
    "phone": "08000000000",
    "bank_code": "058",
    "bank_name": "GTBank",
    "account_number": "0000000000",
    "account_name": "Northgate Supplies Nigeria Ltd",
}

CLEAN_THEN_FRAUD_TRANSACTIONS = [
    {"amount": 5000_00, "customer_email": "buyer1@gmail.com"},
    {"amount": 8000_00, "customer_email": "buyer2@gmail.com"},
    {"amount": 12000_00, "customer_email": "buyer3@gmail.com"},
    {"amount": 500000_00, "customer_email": "mule@temp.com"},
    {"amount": 500000_00, "customer_email": "mule@temp.com"},
    {"amount": 1000000_00, "customer_email": "mule@temp.com"},
]


def _severity_to_legacy(severity: FlagSeverity) -> int:
    return {
        FlagSeverity.INFO: 0,
        FlagSeverity.LOW: 1,
        FlagSeverity.MEDIUM: 2,
        FlagSeverity.HIGH: 3,
        FlagSeverity.CRITICAL: 3,
    }[severity]


def _vendor_obj(payload: dict, *, vendor_id: str | None = None, status: str = "pending") -> Vendor:
    return Vendor(
        id=vendor_id or str(uuid.uuid4()),
        business_name=payload["business_name"],
        rc_number=payload.get("rc_number"),
        bvn=payload.get("bvn", ""),
        nin=payload.get("nin", ""),
        email=payload.get("email", "ops@example.com"),
        phone=payload.get("phone", "08012345678"),
        address=payload.get("address", ""),
        tier=payload.get("tier", "tier2"),
        status=status,
        created_at=dt.datetime.now(dt.UTC),
    )


def _demo_score(nlp_score: int, agent_score: int, anomaly_flags: list[dict]) -> tuple[int, str]:
    anomaly_penalty = sum(flag.get("severity", 1) * 6 for flag in anomaly_flags)
    anomaly_score = max(0, 100 - anomaly_penalty)
    score = int((0.45 * nlp_score) + (0.35 * agent_score) + (0.20 * anomaly_score))
    score = max(0, min(100, score))
    verdict = "approved" if score >= 70 else "review" if score >= 45 else "blocked"
    return score, verdict


async def run_vendor_case(label: str, vendor_payload: dict, ocr_output: dict, *, create_squad: bool) -> tuple[int, str]:
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)

    nlp_result = await run_nlp_pipeline(ocr_output, vendor_payload)
    agent_result = await run_agentic_verification_async(vendor_payload, nlp_result.extracted_fields)
    vendor = _vendor_obj(vendor_payload)
    anomaly_flags, anomaly_notes = detect_anomalies(vendor)
    score, verdict = _demo_score(nlp_result.nlp_score, agent_result.agent_score, anomaly_flags)

    nlp_legacy = [
        {
            "code": flag.flag_type.upper(),
            "title": flag.flag_type.replace("_", " ").title(),
            "description": flag.detail,
            "severity": _severity_to_legacy(flag.severity),
            "source": "nlp",
        }
        for flag in nlp_result.flags
        if flag.severity != FlagSeverity.INFO
    ]
    all_flags = [*nlp_legacy, *agent_flags_to_legacy(agent_result.flags), *anomaly_flags]

    print(f"\nTRUSTGATE SCORE: {score}/100")
    print(f"VERDICT: {verdict}")
    print(f"NLP SCORE: {nlp_result.nlp_score}/100 | AGENT SCORE: {agent_result.agent_score}/100")
    print(f"FLAGS: {len(all_flags)} | ANOMALY NOTES: {anomaly_notes}")
    print(f"AI ASSESSMENT: {agent_result.explanation}")

    if create_squad and verdict == "approved":
        vendor.status = "approved"
        for key in ("account_name", "account_number", "bank_code", "bank_name"):
            setattr(vendor, key, vendor_payload.get(key, ""))
        squad_result = await create_sub_merchant(vendor)
        account_id = squad_result.get("account_id") or squad_result.get("merchant_id") or squad_result.get("data", {}).get("account_id")
        print(f"SQUAD SUB-MERCHANT: {account_id}")
    elif create_squad:
        print("SQUAD SUB-MERCHANT: not created because vendor was not approved")

    return score, verdict


def _create_monitor_vendor(db) -> Vendor:
    vendor = _vendor_obj(CLEAN_VENDOR, status="approved")
    vendor.squad_merchant_id = f"demo_squad_{uuid.uuid4().hex[:8]}"
    db.add(vendor)
    db.flush()
    db.add(
        Verification(
            id=str(uuid.uuid4()),
            vendor_id=vendor.id,
            trust_score=88,
            risk_level="LOW",
            verdict="approved",
            summary="Demo vendor approved for transaction monitoring.",
            identity_status="demo_verified",
        )
    )
    db.commit()
    db.refresh(vendor)
    return vendor


async def run_transaction_monitoring_demo() -> None:
    print("\n" + "=" * 70)
    print("DEMO CASE 3: Post-Approval Transaction Monitoring")
    print("=" * 70)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        vendor = _create_monitor_vendor(db)
        merchant_id = vendor.squad_merchant_id or vendor.id
        for index, txn in enumerate(CLEAN_THEN_FRAUD_TRANSACTIONS, start=1):
            transaction_ref = f"demo_txn_{uuid.uuid4().hex[:10]}"
            payload = {
                **txn,
                "transaction_ref": transaction_ref,
                "created_at": dt.datetime.now(dt.UTC),
            }
            print(f"\nTRANSACTION {index}: ₦{txn['amount'] / 100:,.0f} from {txn['customer_email']}")
            result = await monitor_transaction(merchant_id, payload, db)
            db.add(
                Transaction(
                    merchant_id=vendor.id,
                    squad_account_id=merchant_id,
                    transaction_ref=transaction_ref,
                    amount=txn["amount"],
                    customer_email=txn["customer_email"],
                    transaction_status="Success",
                    flagged=bool(result.flags),
                )
            )
            db.commit()
            if result.suspended:
                print(f"MERCHANT SUSPENDED after transaction {index}")
                break
    finally:
        db.close()


async def run_demo():
    await run_vendor_case(
        "DEMO CASE 1: Clean Vendor - expect approval + Squad account creation",
        CLEAN_VENDOR,
        MOCK_OCR_OUTPUT,
        create_squad=True,
    )
    await run_vendor_case(
        "DEMO CASE 2: Fraud Vendor - expect block with multiple critical flags",
        FRAUD_VENDOR,
        FRAUD_OCR_OUTPUT,
        create_squad=False,
    )
    await run_transaction_monitoring_demo()


if __name__ == "__main__":
    asyncio.run(run_demo())
