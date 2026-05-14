import time
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


def _legacy_flag_severity(flag: dict) -> int:
    value = flag.get("severity", 1)
    code = str(flag.get("code", "")).lower()
    if isinstance(value, str):
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(value.lower(), 1)
    severity = int(value or 0)
    if severity >= 3 and "critical" in code:
        return 4
    return severity


def _severity_penalty(flag: dict) -> int:
    return {
        4: 18,
        3: 12,
        2: 7,
        1: 3,
        0: 0,
    }.get(_legacy_flag_severity(flag), 3)


def _flag_bucket(flag: dict) -> str:
    source = str(flag.get("source", "")).lower()
    code = str(flag.get("code", "")).lower()
    text = f"{source} {code}"
    if "anomaly" in text or "behaviour" in text or "behavior" in text:
        return "behaviour"
    if any(token in text for token in ("bvn", "nin", "identity", "director")):
        return "identity"
    if any(token in text for token in ("cac", "registry", "web", "website", "category", "address", "maps", "footprint", "reputation")):
        return "business"
    if source in {"nlp", "ocr"} or any(token in text for token in ("document", "name", "rc")):
        return "document"
    return "business"


def _score_bucket(flags: list[dict], *, cap: int) -> int:
    penalty = min(cap, sum(_severity_penalty(flag) for flag in flags))
    return max(0, 100 - penalty)


def _risk_and_verdict(score: int, flags: list[dict]) -> tuple[str, str]:
    critical_count = sum(1 for flag in flags if _legacy_flag_severity(flag) >= 4)
    high_count = sum(1 for flag in flags if _legacy_flag_severity(flag) == 3)
    if score >= 75 and critical_count == 0:
        return "LOW", "approved"
    if score >= 50 and critical_count < 2 and high_count < 4:
        return "MEDIUM", "review"
    return "HIGH", "blocked"


def calculate_score_breakdown(
    flags: list[dict],
    *,
    ocr_confidence: float,
    has_documents: bool,
    agent_score: int,
) -> tuple[int, str, str, dict[str, int]]:
    buckets = {
        "identity": [flag for flag in flags if _flag_bucket(flag) == "identity"],
        "document": [flag for flag in flags if _flag_bucket(flag) == "document"],
        "business": [flag for flag in flags if _flag_bucket(flag) == "business"],
        "behaviour": [flag for flag in flags if _flag_bucket(flag) == "behaviour"],
    }

    identity_score = _score_bucket(buckets["identity"], cap=65)
    document_consistency = _score_bucket(buckets["document"], cap=70)
    ocr_quality = int(round(max(0.0, min(1.0, ocr_confidence)) * 100)) if has_documents else 0
    document_score = int(round((document_consistency * 0.65) + (ocr_quality * 0.35))) if has_documents else 20
    business_score = int(
        round((_score_bucket(buckets["business"], cap=65) * 0.65) + (max(0, min(100, agent_score)) * 0.35))
    )
    behaviour_score = _score_bucket(buckets["behaviour"], cap=55)

    score = int(round(
        identity_score * 0.30
        + document_score * 0.30
        + business_score * 0.25
        + behaviour_score * 0.15
    ))
    if not has_documents:
        score = min(score, 35)
    if sum(1 for flag in flags if _legacy_flag_severity(flag) >= 4) >= 2:
        score = min(score, 48)

    risk_level, verdict = _risk_and_verdict(score, flags)
    return score, risk_level, verdict, {
        "identity_score": identity_score,
        "document_score": document_score,
        "business_score": business_score,
        "behaviour_score": behaviour_score,
    }


def calculate_trust_score(flags: list[dict]) -> tuple[int, str, str]:
    """Backward-compatible wrapper for older tests and demo scripts."""
    score, risk_level, verdict, _ = calculate_score_breakdown(
        flags,
        ocr_confidence=1.0,
        has_documents=True,
        agent_score=80,
    )
    return score, risk_level, verdict


def _external_check_status(tool) -> str:
    status = (tool.status or "").lower()
    provider = (tool.provider or "").lower()
    if tool.external_call_failed or "failed" in status or "not_found" in status:
        return "failed" if tool.confidence < 0.45 else "fallback"
    if "fallback" in status or "fallback" in provider or "local" in status or "local" in provider:
        return "fallback"
    return "confirmed"


def _tool_label(tool_name: str) -> str:
    return {
        "dojah_bvn": "BVN",
        "dojah_nin": "NIN",
        "cac_registry": "CAC Registry",
        "google_maps": "Address",
        "duckduckgo_search": "Web Presence",
    }.get(tool_name, tool_name.replace("_", " ").title())


def _external_checks(agent_result) -> list[dict]:
    checks = []
    for tool in agent_result.tools_called:
        if tool.tool_name == "llm_summary":
            continue
        evidence = tool.evidence or {}
        failure = evidence.get("failure_reason")
        if failure:
            detail = f"{tool.status.replace('_', ' ').title()} - {str(failure)[:120]}"
        elif tool.notes:
            detail = tool.notes
        else:
            detail = tool.status.replace("_", " ").title()
        checks.append(
            {
                "id": tool.tool_name,
                "name": _tool_label(tool.tool_name),
                "status": _external_check_status(tool),
                "detail": detail,
                "raw": {
                    "status": tool.status,
                    "confidence": tool.confidence,
                    "provider": tool.provider,
                    "evidence": evidence,
                    "notes": tool.notes,
                },
            }
        )
    return checks


def recommendation_for(verdict: str) -> str:
    if verdict == "approved":
        return "Approve merchant onboarding and continue normal monitoring."
    if verdict == "review":
        return "Manual compliance review required before Squad merchant creation."
    return "Block onboarding until identity and business evidence are resolved."


async def run_verification(db, vendor: Vendor) -> Verification:
    started = time.perf_counter()
    document_paths = {doc.doc_type: doc.path for doc in vendor.documents if doc.doc_type} if vendor.documents else {}
    
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
            "business_category": vendor.business_category or "",
            "website_url": vendor.website_url or "",
            "website": vendor.website_url or "",
            "expected_monthly_volume": vendor.expected_monthly_volume or 0,
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
    for tool in agent_result.tools_called:
        if tool.tool_name == "duckduckgo_search":
            has_web = float(tool.evidence.get("footprint_score", 0.0)) / 10.0
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
    score, risk_level, verdict, breakdown = calculate_score_breakdown(
        all_flags,
        ocr_confidence=ocr_result.avg_confidence,
        has_documents=bool(document_paths),
        agent_score=agent_result.agent_score,
    )
    dominant_flags = sorted(all_flags, key=lambda item: item.get("severity", 0), reverse=True)[:3]
    dominant_summary = ", ".join(flag["title"] for flag in dominant_flags) or "No material flags"
    summary = agent_result.explanation or (
        f"Trust score {score}/100. Risk level {risk_level}. Verdict: {verdict}. "
        f"Dominant signals: {dominant_summary}."
    )

    verification = Verification(
        id=str(uuid.uuid4()),
        vendor_id=vendor.id,
        trust_score=score,
        identity_score=breakdown["identity_score"],
        document_score=breakdown["document_score"],
        business_score=breakdown["business_score"],
        behaviour_score=breakdown["behaviour_score"],
        risk_level=risk_level,
        verdict=verdict,
        summary=summary,
        ocr_text=extracted_text or None,
        nlp_notes=nlp_notes,
        identity_status=identity_status,
        anomaly_notes=f"{anomaly_notes} Agent score={agent_result.agent_score}. {agent_result.explanation}",
        external_checks=_external_checks(agent_result),
        processing_time_ms=int((time.perf_counter() - started) * 1000),
    )
    db_log(
        f"→ Saving verification result: vendor={vendor.id} score={score} "
        f"verdict={verdict} breakdown={breakdown}"
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
    db_log(f"✓ Verification saved — {len(all_flags)} flags stored")
    db.refresh(verification)
    return verification
