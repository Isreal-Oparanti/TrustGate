import uuid
from app.models.flag import Flag
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.services.anomaly import detect_anomalies
from app.services.identity import verify_identity
from app.services.nlp import check_consistency
from app.services.ocr import parse_documents


def calculate_trust_score(flags: list[dict]) -> tuple[int, str, str]:
    penalty = sum(flag.get("severity", 1) * 10 for flag in flags)
    score = max(0, min(100, 100 - penalty))
    if score >= 75:
        return score, "LOW", "approved"
    if score >= 45:
        return score, "MEDIUM", "review"
    return score, "HIGH", "blocked"


def recommendation_for(verdict: str) -> str:
    if verdict == "approved":
        return "Approve merchant onboarding and continue normal monitoring."
    if verdict == "review":
        return "Manual compliance review required before Squad merchant creation."
    return "Block onboarding until identity and business evidence are resolved."


def run_verification(db, vendor: Vendor) -> Verification:
    extracted_text = parse_documents(vendor.documents)
    identity_flags, identity_status = verify_identity(vendor)
    nlp_flags, nlp_notes = check_consistency(vendor, extracted_text)
    anomaly_flags, anomaly_notes = detect_anomalies(vendor)
    all_flags = [*identity_flags, *nlp_flags, *anomaly_flags]
    score, risk_level, verdict = calculate_trust_score(all_flags)

    verification = Verification(
        id=str(uuid.uuid4()),
        vendor_id=vendor.id,
        trust_score=score,
        risk_level=risk_level,
        verdict=verdict,
        summary=f"Trust score {score}/100. Risk level {risk_level}. Verdict: {verdict}.",
        ocr_text=extracted_text or None,
        nlp_notes=nlp_notes,
        identity_status=identity_status,
        anomaly_notes=anomaly_notes,
    )
    db.add(verification)
    db.flush()

    for item in all_flags:
        db.add(
            Flag(
                id=str(uuid.uuid4()),
                vendor_id=vendor.id,
                verification_id=verification.id,
                code=item["code"],
                title=item["title"],
                description=item["description"],
                severity=item["severity"],
                source=item["source"],
            )
        )

    vendor.status = verdict
    db.commit()
    db.refresh(verification)
    return verification
