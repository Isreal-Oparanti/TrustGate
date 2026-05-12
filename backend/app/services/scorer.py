import uuid
from datetime import datetime
from dateutil import parser
from rapidfuzz import fuzz
from app.models.flag import Flag
from app.models.vendor import Vendor
from app.models.verification import Verification
from app.services.agentic_verification import agent_flags_to_legacy, run_agentic_verification
from app.services.anomaly import detect_anomalies
from app.services.identity import verify_identity
from app.services.nlp import NigerianDocumentFieldExtractor, check_consistency
from app.services.ocr import TrustGateOCR
from app.schemas.verification import OCRBatchResult
from app.utils.logger import db_log


def calculate_trust_score(flags: list[dict]) -> tuple[int, str, str]:
    source_weights = {
        "identity": 1.2,
        "agentic_verification": 1.1,
        "anomaly_ml": 1.0,
        "anomaly": 0.9,
        "nlp": 1.0,
        "ocr": 1.0,
    }
    penalty = 0
    for flag in flags:
        severity = flag.get("severity", 1)
        source = flag.get("source", "")
        penalty += int(severity * 10 * source_weights.get(source, 1.0))
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


async def run_verification(db, vendor: Vendor) -> Verification:
    document_paths = {doc.doc_type: doc.path for doc in vendor.documents} if vendor.documents else {}
    
    if not document_paths:
        db_log(f"No documents found for vendor {vendor.id} — NLP will run with empty input")
        ocr_result = OCRBatchResult(
            vendor_id=vendor.id,
            documents={},
            total_processing_time_ms=0,
            avg_confidence=0.0,
            low_confidence_docs=[]
        )
    else:
        ocr_engine = TrustGateOCR()
        ocr_result = await ocr_engine.process_vendor_documents(vendor.id, document_paths)

    extracted_text = "\n\n".join([res.raw_text for res in ocr_result.documents.values() if res.raw_text])
    
    identity_flags, identity_status = verify_identity(vendor)
    nlp_flags, nlp_notes = check_consistency(vendor, extracted_text)
    
    if not document_paths:
        nlp_flags.append({
            "code": "missing_all_documents",
            "title": "No Documents Uploaded",
            "description": "Vendor has not uploaded any documents.",
            "severity": 3,
            "source": "nlp",
        })
        
    extracted_fields = NigerianDocumentFieldExtractor().extract_all_fields(extracted_text, "combined_documents") if extracted_text else {}
    agent_result = run_agentic_verification(
        {
            "business_name": vendor.business_name,
            "rc_number": vendor.rc_number or "",
            "director_name": vendor.director_name or "",
            "address": vendor.address,
            "bvn": vendor.bvn,
            "nin": vendor.nin,
            "email": vendor.email,
            "phone": vendor.phone,
            "tier": vendor.tier,
        },
        extracted_fields,
    )
    
    # Calculate ML features for anomaly detection
    age_days = 365
    if "incorporation_date" in extracted_fields and extracted_fields["incorporation_date"]:
        try:
            dt = parser.parse(extracted_fields["incorporation_date"], fuzzy=True)
            age_days = (datetime.now() - dt).days
            if age_days < 0: age_days = 365
        except Exception:
            pass

    doc_names = " ".join(extracted_fields.get("director_names", []) + extracted_fields.get("company_names", []))
    vendor_names = f"{vendor.business_name} {vendor.director_name or ''}"
    name_sim = fuzz.token_set_ratio(vendor_names, doc_names) / 100.0 if doc_names else 0.5
    
    has_web = 0.0
    addr_spec = 0.5
    for tool in agent_result.tools:
        if tool.tool_name == "duckduckgo_search":
            has_web = float(tool.data.get("footprint_score", 0.0)) / 10.0
            has_web = min(1.0, max(has_web, 0.8 if tool.status == "strong_footprint" else 0.0))
        elif tool.tool_name == "google_maps":
            addr_spec = 1.0 if tool.status == "precise_match" else (0.5 if tool.status == "found" else 0.0)
            
    ml_features = {
        "registration_age_days": age_days,
        "doc_confidence_avg": ocr_result.avg_confidence,
        "name_similarity_score": name_sim,
        "has_web_presence": has_web,
        "address_specificity": addr_spec,
        "share_capital_round": 0,
        "director_count": max(1, len(extracted_fields.get("director_names", []))),
        "nin_bvn_format_valid": 1 if (vendor.bvn and len(vendor.bvn) == 11) else 0,
        "registration_to_payment_gap_days": age_days
    }
    
    anomaly_flags, anomaly_notes = detect_anomalies(vendor, ml_features)
    
    agent_flags = agent_flags_to_legacy(agent_result.flags)
    all_flags = [*identity_flags, *nlp_flags, *anomaly_flags, *agent_flags]
    score, risk_level, verdict = calculate_trust_score(all_flags)
    dominant_flags = sorted(all_flags, key=lambda item: item.get("severity", 0), reverse=True)[:3]
    dominant_summary = ", ".join(flag["title"] for flag in dominant_flags) or "No material flags"

    verification = Verification(
        id=str(uuid.uuid4()),
        vendor_id=vendor.id,
        trust_score=score,
        risk_level=risk_level,
        verdict=verdict,
        summary=(
            f"Trust score {score}/100. Risk level {risk_level}. Verdict: {verdict}. "
            f"Dominant signals: {dominant_summary}."
        ),
        ocr_text=extracted_text or None,
        nlp_notes=nlp_notes,
        identity_status=identity_status,
        anomaly_notes=f"{anomaly_notes} Agent score={agent_result.agent_score}. {agent_result.explanation}",
    )
    db_log(f"→ Saving verification result: vendor={vendor.id} score={score} verdict={verdict}")
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
    db_log(f"✓ Verification saved — {len(all_flags)} flags stored")
    db.refresh(verification)
    return verification
