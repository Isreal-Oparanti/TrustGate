from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import settings
from app.schemas.verification import AgentToolResult, AgentVerificationResult, Flag, FlagSeverity
from app.services.nlp import NAME_TITLES
from app.utils.logger import agent_log

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

try:
    from ddgs import DDGS
    from ddgs.exceptions import DuckDuckGoSearchException
except ImportError:
    try:
        from duckduckgo_search import DDGS
        from duckduckgo_search.exceptions import DuckDuckGoSearchException
    except ImportError:
        DDGS = None
        DuckDuckGoSearchException = Exception

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    fuzz = None


NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DOJAH_BASE_URL = "https://sandbox.dojah.io"
DOJAH_BVN_URL = f"{DOJAH_BASE_URL}/api/v1/kyc/bvn"
DOJAH_NIN_URL = f"{DOJAH_BASE_URL}/api/v1/kyc/nin"
CAC_SEARCH_URL = "https://search.cac.gov.ng/home"
GOOGLE_MAPS_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Compatibility constants used by the existing regression test. The new primary
# footprint and summary providers are DuckDuckGo and NVIDIA LLaMA.
GOOGLE_CUSTOM_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_HAIKU_MODEL = "claude-haiku-4-5-20251001"

PLANNING_SYSTEM_PROMPT = """You are a fraud verification agent for a Nigerian fintech platform called TrustGate.
You have access to these verification tools:
- dojah_bvn: Verifies BVN identity against Dojah API. Input: bvn string.
- dojah_nin: Verifies NIN identity against Dojah API. Input: nin string.
- cac_registry: Checks CAC business registry. Input: rc_number string.
- google_maps: Geocodes and verifies business address. Input: address string.
- duckduckgo_search: Searches for business web presence. Input: business_name string.

Given the vendor facts provided, produce a JSON verification plan.
Respond ONLY with valid JSON — no explanation, no markdown, no preamble.

JSON format:
{
  "reasoning": "one sentence explaining your overall assessment of this vendor",
  "plan": [
    {"step": 1, "tool": "tool_name", "input": "input_value", "reason": "why this tool first"},
    {"step": 2, "tool": "tool_name", "input": "input_value", "reason": "why this tool next"}
  ],
  "risk_hypothesis": "initial hypothesis about this vendor's risk level"
}"""

REASONING_SYSTEM_PROMPT = """You are a fraud verification agent. You just ran a verification tool.
Analyze the result and decide what it means for this vendor's risk level.
Respond ONLY with valid JSON.

{
  "finding": "what this result tells you in one sentence",
  "risk_delta": "increased | decreased | unchanged",
  "risk_delta_reason": "why",
  "continue_plan": true or false,
  "override_next_tool": null or "tool_name",
  "flag_raised": null or {"type": "flag_type", "severity": "critical|high|medium|low", "detail": "explanation"}
}"""

SUMMARY_SYSTEM_PROMPT = """You are a compliance officer assistant for TrustGate, a Nigerian fintech fraud
prevention system. Write a 2-3 sentence summary of this vendor verification
for a human compliance officer. Be specific — name the signals that matter.
Do not make the final approve/block decision — that is the human's job.
Write in plain, professional English. No bullet points. No markdown."""

DEFAULT_TOOL_ORDER = ["dojah_bvn", "dojah_nin", "cac_registry", "google_maps", "duckduckgo_search"]
SEVERITY_DEDUCTIONS = {
    FlagSeverity.CRITICAL: 30,
    FlagSeverity.HIGH: 15,
    FlagSeverity.MEDIUM: 8,
    FlagSeverity.LOW: 3,
    FlagSeverity.INFO: 0,
}


@dataclass
class ToolResult:
    tool_name: str
    status: str
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    external_call_made: bool = False
    external_call_failed: bool = False
    provider: str = ""
    notes: str = ""

    def to_agent_tool_result(self) -> AgentToolResult:
        return AgentToolResult(
            tool_name=self.tool_name,
            fact_type=self.tool_name,
            status=self.status,
            confidence=round(self.confidence, 3),
            provider=self.provider or self.tool_name,
            external_call_used=self.external_call_made and not self.external_call_failed,
            external_call_failed=self.external_call_failed,
            evidence={**self.data, "external_call_failed": self.external_call_failed},
            notes=self.notes,
        )


def _make_flag(
    flag_type: str,
    severity: FlagSeverity,
    detail: str,
    source_doc: str,
    evidence: str,
    method: str,
    score: float | None = None,
) -> Flag:
    return Flag(
        flag_type=flag_type,
        severity=severity,
        detail=detail,
        source_doc=source_doc,
        evidence=re.sub(r"\s+", " ", evidence or "").strip()[:500],
        check_method=method,
        similarity_score=score,
    )


def _mask_secret(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 6:
        return "****"
    return f"{digits[:4]}****{digits[-2:]}"


def _normalise_rc(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    return f"RC{digits}" if digits else ""


def _normalise_name(value: str | None) -> str:
    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z]+", value or "")
        if token.lower().rstrip(".") not in NAME_TITLES
    ]
    return " ".join(sorted(tokens))


def _token_set_ratio(left: str | None, right: str | None) -> float:
    left_value = left or ""
    right_value = right or ""
    if not left_value or not right_value:
        return 0.0
    if fuzz:
        return fuzz.token_set_ratio(left_value, right_value) / 100
    left_tokens = set(re.findall(r"\w+", left_value.lower()))
    right_tokens = set(re.findall(r"\w+", right_value.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _name_score(left: str | None, right: str | None) -> float:
    return _token_set_ratio(_normalise_name(left), _normalise_name(right))


def _dojah_headers() -> dict[str, str]:
    return {"AppId": settings.DOJAH_APP_ID, "Authorization": settings.DOJAH_API_KEY}


def _has_dojah_credentials() -> bool:
    return bool(settings.DOJAH_APP_ID and settings.DOJAH_API_KEY)


def _entity_value(entity: dict[str, Any], key: str) -> str:
    value = entity.get(key)
    if isinstance(value, dict):
        for nested_key in ("value", "full_name", "name", "phone_number"):
            nested_value = value.get(nested_key)
            if nested_value not in (None, ""):
                return str(nested_value)
        return ""
    return "" if value is None else str(value)


def _entity_name(entity: dict[str, Any]) -> str:
    explicit = _entity_value(entity, "full_name") or _entity_value(entity, "name")
    if explicit:
        return explicit
    parts = [
        _entity_value(entity, "first_name") or _entity_value(entity, "firstname"),
        _entity_value(entity, "middle_name") or _entity_value(entity, "middlename"),
        _entity_value(entity, "last_name") or _entity_value(entity, "surname"),
    ]
    return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()


async def _get_json(url: str, *, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


async def _post_text(url: str, *, form_data: dict[str, Any], headers: dict[str, str] | None = None) -> str:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, data=form_data, headers=headers)
        response.raise_for_status()
        return response.text


async def _post_json(
    url: str,
    *,
    json_payload: dict[str, Any] | None = None,
    form_data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=json_payload, data=form_data, headers=headers)
        response.raise_for_status()
        return response.json()


def _safe_json_parse(raw: str) -> dict[str, Any] | None:
    cleaned = (raw or "").strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                return None
    return None


def _llama_client():
    if not settings.NVIDIA_API_KEY or OpenAI is None:
        return None
    return OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=settings.NVIDIA_API_KEY,
        timeout=8.0,
        max_retries=0,
        http_client=httpx.Client(timeout=8.0),
    )


def _llm_provider() -> str:
    return (settings.LLM_EXPLANATION_PROVIDER or "local_template").lower()


def _use_nvidia_llama() -> bool:
    return bool(settings.NVIDIA_API_KEY) and _llm_provider() in {"nvidia", "nvidia_llama", "llama", "nvidia_agentic", "agentic_llm"}


def _use_llm_planning() -> bool:
    return bool(settings.NVIDIA_API_KEY) and _llm_provider() in {"nvidia_agentic", "agentic_llm"}


def _call_llama(system_prompt: str, user_payload: dict[str, Any], *, max_tokens: int) -> str:
    client = _llama_client()
    if client is None:
        raise RuntimeError("NVIDIA_API_KEY is not configured or openai package is unavailable")
    completion = client.chat.completions.create(
        model=NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, default=str)},
        ],
        temperature=0.3,
        max_tokens=max_tokens,
        stream=False,
    )
    choice = completion.choices[0]
    content = choice.message.content or ""

    # Nemotron is a thinking model — if content is empty, the answer
    # may be inside reasoning_content (the model "thinks" then answers).
    if not content.strip():
        reasoning = getattr(choice.message, "reasoning_content", None) or ""
        if reasoning:
            # Try to extract JSON from the thinking text
            json_match = re.search(r"\{.*\}", reasoning, flags=re.DOTALL)
            if json_match:
                content = json_match.group(0)
            else:
                content = reasoning

    return content or ""


def _default_plan(vendor_facts: dict[str, Any], reason: str = "fallback") -> dict[str, Any]:
    values = {
        "dojah_bvn": vendor_facts.get("bvn", ""),
        "dojah_nin": vendor_facts.get("nin", ""),
        "cac_registry": vendor_facts.get("rc_number", ""),
        "google_maps": vendor_facts.get("address", ""),
        "duckduckgo_search": vendor_facts.get("business_name", ""),
    }
    return {
        "reasoning": f"Default verification plan selected because {reason}.",
        "risk_hypothesis": "unknown until identity, registry, address, and web footprint checks complete",
        "plan": [
            {"step": index + 1, "tool": tool, "input": values.get(tool, ""), "reason": "standard TrustGate verification order"}
            for index, tool in enumerate(DEFAULT_TOOL_ORDER)
        ],
    }


def _plan_summary(plan_steps: list[dict[str, Any]]) -> str:
    return " | ".join(f"Step {item.get('step')}→{item.get('tool')}" for item in plan_steps)


def generate_verification_plan(vendor_facts: dict[str, Any]) -> dict[str, Any]:
    if not _use_llm_planning():
        plan = _default_plan(vendor_facts, f"LLM planning disabled ({_llm_provider()})")
        agent_log("── PLANNING: Using deterministic TrustGate plan")
        agent_log("── PLAN RECEIVED:")
        agent_log(f"   Hypothesis: {plan.get('risk_hypothesis', 'unknown')}")
        agent_log(f"   Plan: {_plan_summary(plan.get('plan', []))}")
        return plan

    agent_log("── PLANNING: Calling LLaMA to generate verification plan...")
    try:
        parsed = _safe_json_parse(_call_llama(PLANNING_SYSTEM_PROMPT, vendor_facts, max_tokens=512))
        if not parsed or not isinstance(parsed.get("plan"), list):
            raise ValueError("LLaMA plan response was not valid plan JSON")
        plan = parsed
    except Exception as exc:
        agent_log(f"   LLaMA unavailable — reason: {type(exc).__name__} | using default plan", "warning")
        plan = _default_plan(vendor_facts, str(exc))
    agent_log("── PLAN RECEIVED:")
    agent_log(f"   Hypothesis: {plan.get('risk_hypothesis', 'unknown')}")
    agent_log(f"   Plan: {_plan_summary(plan.get('plan', []))}")
    return plan


def reason_about_tool(tool_result: ToolResult) -> dict[str, Any]:
    if not _use_llm_planning():
        risk_delta = "increased" if tool_result.flags else "decreased" if tool_result.status in {"verified", "precise_match", "strong_footprint"} else "unchanged"
        return {
            "finding": f"{tool_result.tool_name} returned status={tool_result.status}.",
            "risk_delta": risk_delta,
            "risk_delta_reason": "Deterministic TrustGate reasoning used for fast verification.",
            "continue_plan": not any(flag.severity == FlagSeverity.CRITICAL for flag in tool_result.flags),
            "override_next_tool": None,
            "flag_raised": None,
        }

    payload = {tool_result.tool_name: tool_result_to_json(tool_result)}
    try:
        parsed = _safe_json_parse(_call_llama(REASONING_SYSTEM_PROMPT, payload, max_tokens=512))
        if not parsed:
            raise ValueError("LLaMA reasoning response was not valid JSON")
        return {
            "finding": parsed.get("finding", "No finding returned."),
            "risk_delta": parsed.get("risk_delta", "unchanged"),
            "risk_delta_reason": parsed.get("risk_delta_reason", "No reason returned."),
            "continue_plan": bool(parsed.get("continue_plan", True)),
            "override_next_tool": parsed.get("override_next_tool"),
            "flag_raised": parsed.get("flag_raised"),
        }
    except Exception as exc:
        risk_delta = "increased" if tool_result.flags else "decreased" if tool_result.status in {"verified", "precise_match", "strong_footprint"} else "unchanged"
        return {
            "finding": f"{tool_result.tool_name} returned status={tool_result.status}.",
            "risk_delta": risk_delta,
            "risk_delta_reason": f"Fallback deterministic reasoning because LLaMA was unavailable: {exc}",
            "continue_plan": not any(flag.severity == FlagSeverity.CRITICAL for flag in tool_result.flags),
            "override_next_tool": None,
            "flag_raised": None,
        }


def tool_result_to_json(tool_result: ToolResult) -> dict[str, Any]:
    return {
        "tool_name": tool_result.tool_name,
        "status": tool_result.status,
        "confidence": tool_result.confidence,
        "provider": tool_result.provider,
        "data": tool_result.data,
        "flags": [flag.model_dump() for flag in tool_result.flags],
        "external_call_made": tool_result.external_call_made,
        "external_call_failed": tool_result.external_call_failed,
    }


def _local_identity_fallback(tool_name: str, reason: str, bvn_or_nin: str) -> ToolResult:
    valid = bool(re.fullmatch(r"\d{11}", bvn_or_nin or ""))
    flags = []
    if not valid:
        flags.append(
            _make_flag(
                f"{tool_name}_format_invalid",
                FlagSeverity.HIGH,
                f"{tool_name.upper()} format is invalid for provider verification.",
                "vendor_submission",
                _mask_secret(bvn_or_nin),
                "local_identity_format",
            )
        )
    return ToolResult(
        tool_name=tool_name,
        status="fallback_format_valid" if valid else "failed",
        confidence=0.55 if valid else 0.2,
        data={"external_call_failed": True, "failure_reason": reason},
        flags=flags,
        external_call_made=False,
        external_call_failed=True,
        provider=f"{tool_name}_local_fallback",
        notes="External identity call failed; local format fallback used.",
    )


async def tool_dojah_bvn(bvn: str, director_name: str) -> ToolResult:
    agent_log(f"   Input: BVN {_mask_secret(bvn)} (masked for security)")
    if not _has_dojah_credentials():
        agent_log("   Dojah BVN unavailable — missing credentials, using fallback", "warning")
        return _local_identity_fallback("dojah_bvn", "missing_dojah_credentials", bvn)

    flags: list[Flag] = []
    try:
        data = await _get_json(DOJAH_BVN_URL, params={"bvn": bvn}, headers=_dojah_headers())
        entity = data.get("entity", data)
        returned_name = _entity_name(entity)
        watch_listed = (_entity_value(entity, "watch_listed") or "UNKNOWN").upper()
        phone_number = _entity_value(entity, "phone_number") or _entity_value(entity, "phone_number1")

        # Detect Dojah sandbox mode — sandbox returns boolean validation objects
        # instead of actual name strings (e.g. {"first_name": {"status": true}})
        sandbox_mode = not returned_name and isinstance(entity.get("first_name"), dict)

        if sandbox_mode:
            # Sandbox only confirms BVN exists — treat as validated without name matching
            first_ok = (entity.get("first_name") or {}).get("status", False)
            last_ok = (entity.get("last_name") or {}).get("status", False)
            name_match = first_ok and last_ok
            name_match_score = 1.0 if name_match else 0.0
            agent_log(f"   ℹ️ Dojah sandbox mode detected — name returned as validation status, not actual text")
            agent_log(f"   ℹ️ first_name.status={first_ok} | last_name.status={last_ok}")
            status = "sandbox_verified" if name_match else "sandbox_unverified"
            confidence = 0.85 if name_match else 0.40
        else:
            # Production mode — compare actual returned name vs submitted director name
            name_match_score = _name_score(returned_name, director_name)
            name_match = name_match_score >= 0.80

            if not name_match:
                flags.append(
                    _make_flag(
                        "bvn_name_mismatch",
                        FlagSeverity.CRITICAL,
                        "BVN holder name does not match submitted director name.",
                        "dojah_bvn",
                        f"dojah_name={returned_name}; director_name={director_name}",
                        "rapidfuzz_token_set_ratio",
                        name_match_score,
                    )
                )
            status = "verified" if name_match else "mismatch"
            confidence = 0.95 if status == "verified" else 0.25

        if watch_listed == "YES":
            flags.append(
                _make_flag(
                    "bvn_watchlisted",
                    FlagSeverity.CRITICAL,
                    "BVN on fraud watchlist",
                    "dojah_bvn",
                    "watch_listed=YES",
                    "dojah_watchlist",
                )
            )
            status = "watchlisted"
            confidence = 0.25

        agent_log(
            f"BVN name cross-check: BVN returned '{returned_name or '(sandbox: validation only)'}' "
            f"vs director '{director_name}' \u2192 match: {name_match_score:.2f}"
        )
        agent_log(f"   Result: status={status} | name_match={name_match_score:.2f} | watchlisted={watch_listed}")
        return ToolResult(
            tool_name="dojah_bvn",
            status=status,
            confidence=confidence,
            data={
                "returned_name": returned_name or "(sandbox: validation only)",
                "phone_number": phone_number,
                "watch_listed": watch_listed,
                "name_match": name_match,
                "name_match_score": name_match_score,
                "sandbox_mode": sandbox_mode,
            },
            flags=flags,
            external_call_made=True,
            external_call_failed=False,
            provider="dojah_bvn",
            notes="BVN checked through Dojah sandbox." if sandbox_mode else "BVN checked through Dojah production.",
        )
    except Exception as exc:
        agent_log(f"   Dojah BVN failed — using fallback: {exc}", "warning")
        result = _local_identity_fallback("dojah_bvn", str(exc), bvn)
        result.external_call_made = True
        return result


async def tool_dojah_nin(nin: str, bvn_name: str) -> ToolResult:
    agent_log(f"   Input: NIN {_mask_secret(nin)} (masked for security)")
    if not _has_dojah_credentials():
        agent_log("   Dojah NIN unavailable — missing credentials, using fallback", "warning")
        return _local_identity_fallback("dojah_nin", "missing_dojah_credentials", nin)

    flags: list[Flag] = []
    try:
        data = await _get_json(DOJAH_NIN_URL, params={"nin": nin}, headers=_dojah_headers())
        entity = data.get("entity", data)
        returned_name = _entity_name(entity)
        score = _name_score(returned_name, bvn_name)
        same_person = score >= 0.85 if bvn_name else bool(returned_name)
        if bvn_name and not same_person:
            flags.append(
                _make_flag(
                    "bvn_nin_name_mismatch",
                    FlagSeverity.HIGH,
                    "NIN and BVN names do not match",
                    "dojah_nin",
                    f"nin_name={returned_name}; bvn_name={bvn_name}",
                    "rapidfuzz_token_set_ratio",
                    score,
                )
            )
        status = "verified" if same_person else "mismatch"
        confidence = 0.92 if same_person else 0.45
        agent_log(f"   Result: status={status} | bvn_nin_name_match={score:.2f}")
        return ToolResult(
            tool_name="dojah_nin",
            status=status,
            confidence=confidence,
            data={"returned_name": returned_name, "bvn_name": bvn_name, "bvn_nin_name_match": score},
            flags=flags,
            external_call_made=True,
            external_call_failed=False,
            provider="dojah_nin",
            notes="NIN checked through Dojah sandbox.",
        )
    except Exception as exc:
        agent_log(f"   Dojah NIN failed — using fallback: {exc}", "warning")
        result = _local_identity_fallback("dojah_nin", str(exc), nin)
        result.external_call_made = True
        return result


def _parse_cac_html(html: str, rc_number: str) -> dict[str, str]:
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is not installed")
    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text(" ", strip=True)
    if re.search(r"captcha|verify you are human", page_text, flags=re.IGNORECASE):
        raise RuntimeError("CAC registry returned captcha or bot challenge")
    normalised_rc = _normalise_rc(rc_number)
    date_pattern = re.compile(r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
    for row in soup.select("tr"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip() for cell in row.select("td,th")]
        if not cells or normalised_rc not in _normalise_rc(" ".join(cells)):
            continue
        status = next((cell for cell in cells if cell.lower() in {"active", "inactive"}), "unknown")
        date_value = next((cell for cell in cells if date_pattern.search(cell)), "")
        name = next(
            (
                cell
                for cell in cells
                if normalised_rc not in _normalise_rc(cell)
                and cell.lower() not in {"active", "inactive", "status"}
                and not date_pattern.search(cell)
            ),
            "",
        )
        if name:
            return {"registered_name": name, "status": status, "incorporation_date": date_value}
    raise RuntimeError("CAC registry response could not be parsed")


def _cac_local_fallback(
    rc_number: str,
    submitted_name: str,
    doc_rc_numbers: list[str] | None,
    reason: str,
    external_call_made: bool = True,
) -> ToolResult:
    submitted_rc = _normalise_rc(rc_number)
    doc_rcs = [_normalise_rc(value) for value in (doc_rc_numbers or []) if value]
    flags: list[Flag] = []
    valid_format = bool(re.fullmatch(r"RC\d{5,7}", submitted_rc))
    found_in_docs = submitted_rc in doc_rcs if doc_rcs else False
    if doc_rcs and submitted_rc not in doc_rcs:
        flags.append(
            _make_flag(
                "cac_rc_document_mismatch",
                FlagSeverity.CRITICAL,
                "Submitted RC number differs from document RC number.",
                "cac_registry_fallback",
                f"submitted={submitted_rc}; documents={doc_rcs}",
                "local_cac_rc_match",
            )
        )
    status = "locally_consistent" if valid_format and (found_in_docs or not doc_rcs) and not flags else "failed"
    confidence = 0.65 if status == "locally_consistent" else 0.25
    agent_log(f"   CAC fallback used: valid_format={valid_format} | found_in_docs={found_in_docs}")
    return ToolResult(
        tool_name="cac_registry",
        status=status,
        confidence=confidence,
        data={
            "submitted_rc": submitted_rc,
            "submitted_name": submitted_name,
            "document_rcs": doc_rcs,
            "valid_format": valid_format,
            "found_in_documents": found_in_docs,
            "external_call_failed": True,
            "failure_reason": reason,
        },
        flags=flags,
        external_call_made=external_call_made,
        external_call_failed=True,
        provider="cac_local_fallback",
        notes="CAC scrape unavailable; local heuristic fallback used.",
    )


async def tool_cac_registry(
    rc_number: str,
    submitted_name: str,
    doc_rc_numbers: list[str] | None = None,
) -> ToolResult:
    agent_log(f"   Input: RC {_normalise_rc(rc_number) or 'missing'}")
    try:
        html = await _post_text(
            CAC_SEARCH_URL,
            form_data={
                "search": _normalise_rc(rc_number),
                "searchTerm": _normalise_rc(rc_number),
                "rcNumber": _normalise_rc(rc_number),
                "registrationNumber": _normalise_rc(rc_number),
            },
            headers={"User-Agent": "TrustGate-Hackathon-Demo/1.0"},
        )
        parsed = _parse_cac_html(html, rc_number)
        registered_name = parsed.get("registered_name", "")
        status_value = (parsed.get("status") or "unknown").lower()
        score = _token_set_ratio(submitted_name, registered_name)
        flags: list[Flag] = []
        if score < 0.85:
            flags.append(
                _make_flag(
                    "cac_registry_name_mismatch",
                    FlagSeverity.CRITICAL,
                    "CAC registry name does not match submission.",
                    "cac_registry",
                    f"submitted={submitted_name}; cac={registered_name}",
                    "rapidfuzz_token_set_ratio",
                    score,
                )
            )
        if status_value != "active":
            flags.append(
                _make_flag(
                    "cac_company_inactive",
                    FlagSeverity.CRITICAL,
                    "Company status is not Active in CAC registry.",
                    "cac_registry",
                    f"status={status_value}",
                    "cac_status",
                )
            )
        result_status = "verified" if not flags else "failed"
        agent_log(f"   Result: status={result_status} | registry_name={registered_name} | name_match={score:.2f} | cac_status={status_value}")
        return ToolResult(
            tool_name="cac_registry",
            status=result_status,
            confidence=0.90 if not flags else 0.30,
            data={
                "registered_name": registered_name,
                "incorporation_date": parsed.get("incorporation_date", ""),
                "status": status_value,
                "name_match_score": score,
            },
            flags=flags,
            external_call_made=True,
            external_call_failed=False,
            provider="cac_public_registry",
            notes="CAC public registry scrape completed.",
        )
    except Exception as exc:
        agent_log(f"   CAC scrape unavailable — using local fallback: {exc}", "warning")
        return _cac_local_fallback(rc_number, submitted_name, doc_rc_numbers, str(exc), external_call_made=True)


async def tool_google_maps(address: str) -> ToolResult:
    agent_log(f"   Input: address {address}")
    try:
        # Nominatim OpenStreetMap fallback since Maps JS API requires frontend and Geocoding requires billing
        data = await _get_json(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{address}, Nigeria", "format": "json", "limit": 1},
            headers={"User-Agent": "TrustGate-Backend-Verification/1.0"}
        )
        flags: list[Flag] = []
        if not data:
            flags.append(
                _make_flag(
                    "address_not_found",
                    FlagSeverity.HIGH,
                    "Address not found on Maps",
                    "nominatim_geocoder",
                    address,
                    "osm_geocode",
                )
            )
            agent_log("   Result: status=not_found | results=0")
            return ToolResult("google_maps", "not_found", 0.25, {"result_count": 0}, flags, True, False, "nominatim_maps")
        
        top = data[0]
        formatted = top.get("display_name", "")
        location_type = top.get("class", "UNKNOWN")
        country_ok = "nigeria" in formatted.lower()
        precise = location_type in {"building", "amenity", "shop", "office", "historic", "place", "leisure"}
        
        if not country_ok:
            flags.append(
                _make_flag(
                    "address_outside_nigeria",
                    FlagSeverity.CRITICAL,
                    "Address resolves outside Nigeria",
                    "nominatim_geocoder",
                    formatted,
                    "osm_country_check",
                )
            )
        if country_ok and not precise:
            flags.append(
                _make_flag(
                    "address_low_precision",
                    FlagSeverity.LOW,
                    "Address is approximate only",
                    "nominatim_geocoder",
                    f"location_type={location_type}",
                    "osm_precision_check",
                )
            )
        status = "precise_match" if precise and country_ok else "found"
        agent_log(
            f"   Result: status={status} | formatted={formatted} | precision={location_type} | lat={top.get('lat')} lng={top.get('lon')}"
        )
        return ToolResult(
            "google_maps",
            status,
            0.88 if precise and country_ok else 0.62 if country_ok else 0.30,
            {
                "formatted_address": formatted,
                "location_type": location_type,
                "lat": top.get("lat"),
                "lng": top.get("lon"),
                "country_confirmed": country_ok,
                "result_count": len(data),
            },
            flags,
            True,
            False,
            "nominatim_maps",
            "Nominatim Geocode completed (bypassing Google Maps billing).",
        )
    except Exception as exc:
        agent_log(f"   Google Maps failed — using fallback: {exc}", "warning")
        return ToolResult(
            "google_maps",
            "fallback_failed",
            0.50,
            {"address": address, "external_call_failed": True, "failure_reason": str(exc)},
            [],
            True,
            True,
            "google_maps_local_fallback",
            "Google Maps call failed; no fraud flag raised for provider outage.",
        )


async def check_category_web_consistency(
    business_name: str,
    declared_category: str,
    search_results: list[dict],
) -> Flag | None:
    if not declared_category or not search_results:
        return None

    search_context = " ".join(
        f"{result.get('title', '')} {result.get('body', '') or result.get('snippet', '')}"
        for result in search_results[:5]
    )
    prompt = f"""
    A business declares its category as: "{declared_category}"
    Web search results for this business show: "{search_context[:500]}"

    Does the web presence match the declared business category?
    Respond ONLY with JSON: {{"match": true/false, "reason": "one sentence"}}
    """

    try:
        if not _use_nvidia_llama():
            category_terms = {
                "retail": {"store", "shop", "goods", "market", "sales", "merchant"},
                "food": {"food", "restaurant", "catering", "kitchen", "meal", "eatery"},
                "tech": {"software", "technology", "digital", "it", "app", "cloud", "data"},
                "financial": {"investment", "finance", "loan", "credit", "forex", "crypto"},
                "construction": {"building", "contractor", "construction", "estate", "property"},
                "logistics": {"delivery", "courier", "logistics", "transport", "haulage"},
            }
            declared = declared_category.lower()
            expected = category_terms.get(declared, {declared})
            context = search_context.lower()
            match = any(term in context for term in expected)
            competing_finance = declared not in {"financial", "finance"} and any(
                term in context for term in category_terms["financial"]
            )
            category_match = match and not competing_finance
            agent_log(
                f"[CHECK] Category vs web presence: declared={declared_category} | "
                f"LLaMA verdict: {category_match} (deterministic fallback)"
            )
            if not category_match and (match or competing_finance):
                return Flag(
                    flag_type="category_web_mismatch",
                    severity=FlagSeverity.HIGH,
                    detail=f"Declared category '{declared_category}' conflicts with web presence signals.",
                    source_doc="duckduckgo_search",
                    evidence=search_context[:200],
                    check_method="category_keyword_reasoning",
                )
            return None

        client = _llama_client()
        if client is None:
            raise RuntimeError("NVIDIA_API_KEY is not configured or openai package is unavailable")
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )
        result = _safe_json_parse(response.choices[0].message.content or "") or {}
        raw_match = result.get("match")
        category_match = raw_match if isinstance(raw_match, bool) else str(raw_match).lower() == "true"
        agent_log(
            f"[CHECK] Category vs web presence: declared={declared_category} | "
            f"LLaMA verdict: {category_match}"
        )
        if not category_match:
            return Flag(
                flag_type="category_web_mismatch",
                severity=FlagSeverity.HIGH,
                detail=(
                    f"Declared category '{declared_category}' conflicts with web presence: "
                    f"{result.get('reason')}"
                ),
                source_doc="duckduckgo_search",
                evidence=search_context[:200],
                check_method="llm_semantic_reasoning",
            )
    except Exception as exc:
        agent_log(f"Category check failed: {exc}", "warning")

    return None


async def _google_search_compatibility(business_name: str, declared_category: str = "") -> ToolResult:
    query = f'"{business_name}" Nigeria'
    data = await _get_json(
        GOOGLE_CUSTOM_SEARCH_URL,
        params={"key": settings.GOOGLE_API_KEY, "cx": settings.GOOGLE_CX, "q": query},
    )
    items = data.get("items") or []
    total_raw = data.get("searchInformation", {}).get("totalResults") or len(items)
    try:
        result_count = max(int(total_raw), len(items))
    except Exception:
        result_count = len(items)
    flags: list[Flag] = []
    status = "strong_footprint"
    confidence = 0.85
    if result_count == 0:
        status = "no_footprint"
        confidence = 0.35
        flags.append(_make_flag("no_web_presence", FlagSeverity.MEDIUM, "No web presence found for this business", "google_search", query, "google_custom_search"))
    elif result_count < 3:
        status = "weak_footprint"
        confidence = 0.50
        flags.append(_make_flag("weak_web_presence", FlagSeverity.LOW, "Weak web presence", "google_search", query, "google_custom_search"))
    category_flag = await check_category_web_consistency(business_name, declared_category, items)
    if category_flag:
        flags.append(category_flag)
    return ToolResult(
        "duckduckgo_search",
        status,
        confidence,
        {"query": query, "result_count": result_count, "top_titles": [item.get("title") for item in items[:2]]},
        flags,
        True,
        False,
        "google_search",
        "Compatibility Google Custom Search footprint check completed.",
    )


async def tool_duckduckgo_search(
    business_name: str,
    website: str = "",
    director_name: str = "",
    declared_category: str = "",
) -> ToolResult:
    """Enhanced web footprint tool — runs multiple search layers for rigorous verification."""
    query = f'"{business_name}" Nigeria'
    social_query = f'"{business_name}" site:linkedin.com OR site:facebook.com OR site:instagram.com OR site:x.com'
    director_query = f'"{director_name}" "{business_name}" Nigeria' if director_name else ""
    scam_query = f"{business_name} Nigeria scam fraud complaint"

    if settings.GOOGLE_API_KEY and settings.GOOGLE_CX:
        try:
            result = await _google_search_compatibility(business_name, declared_category)
            agent_log(f"   Result: status={result.status} | query={query} | result_count={result.data.get('result_count')}")
            return result
        except Exception as exc:
            agent_log(f"   Google search compatibility failed — trying DuckDuckGo: {exc}", "warning")
    try:
        if DDGS is None:
            raise DuckDuckGoSearchException("duckduckgo-search is not installed")

        # ── Layer 1: General web presence ────────────────────────────────
        agent_log(f"   🔎 Search layer 1/4: General web presence")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5, region="ng-en"))

        # ── Layer 2: Social media profiles ───────────────────────────────
        agent_log(f"   🔎 Search layer 2/4: Social media profiles")
        try:
            with DDGS() as ddgs:
                social_results = list(ddgs.text(social_query, max_results=5, region="wt-wt"))
        except Exception:
            social_results = []

        # ── Layer 3: Director/owner presence ─────────────────────────────
        director_results = []
        if director_query:
            agent_log(f"   🔎 Search layer 3/4: Director/owner presence")
            try:
                with DDGS() as ddgs:
                    director_results = list(ddgs.text(director_query, max_results=3, region="ng-en"))
            except Exception:
                director_results = []
        else:
            agent_log(f"   🔎 Search layer 3/4: Director/owner presence — skipped (no director name)")

        # ── Layer 4: Negative reputation / scam signals ──────────────────
        agent_log(f"   🔎 Search layer 4/4: Negative reputation signals")
        with DDGS() as ddgs:
            scam_results = list(ddgs.text(scam_query, max_results=3, region="ng-en"))

        # ── Website validation ───────────────────────────────────────────
        website_reachable = False
        if website:
            agent_log(f"   🌐 Validating declared website: {website}")
            try:
                url = website if website.startswith("http") else f"https://{website}"
                async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                    resp = await client.head(url)
                    website_reachable = resp.status_code < 400
                    agent_log(f"   🌐 Website status: {resp.status_code} {'(reachable)' if website_reachable else '(unreachable)'}")
            except Exception:
                agent_log(f"   🌐 Website unreachable: {website}", "warning")

        # ── Scoring ──────────────────────────────────────────────────────
        result_count = len(results)
        social_count = len(social_results)
        director_count = len(director_results)
        scam_count = len(scam_results)

        # Classify social media platforms found
        social_platforms = set()
        for item in social_results:
            url = (item.get("href") or item.get("link") or "").lower()
            if "linkedin.com" in url:
                social_platforms.add("LinkedIn")
            elif "facebook.com" in url:
                social_platforms.add("Facebook")
            elif "instagram.com" in url:
                social_platforms.add("Instagram")
            elif "x.com" in url or "twitter.com" in url:
                social_platforms.add("X/Twitter")

        # Combined footprint strength
        footprint_score = result_count + (social_count * 1.5) + (director_count * 2)
        if website_reachable:
            footprint_score += 3

        flags: list[Flag] = []
        if footprint_score >= 5:
            status = "strong_footprint"
            confidence = 0.88
        elif footprint_score >= 2:
            status = "moderate_footprint"
            confidence = 0.65
        elif footprint_score >= 1:
            status = "weak_footprint"
            confidence = 0.45
            flags.append(_make_flag("weak_web_presence", FlagSeverity.LOW, "Weak web presence — limited online visibility", "duckduckgo_search", query, "duckduckgo_multi_layer"))
        else:
            status = "no_footprint"
            confidence = 0.30
            flags.append(_make_flag("no_web_presence", FlagSeverity.MEDIUM, "No web presence found — business has zero online visibility across search, social media, and directories", "duckduckgo_search", query, "duckduckgo_multi_layer"))

        if social_count == 0 and result_count > 0:
            flags.append(_make_flag("no_social_media", FlagSeverity.LOW, "No social media presence found (LinkedIn, Facebook, Instagram, X)", "duckduckgo_search", social_query, "duckduckgo_social_search"))

        if director_query and director_count == 0 and result_count > 0:
            flags.append(_make_flag("director_not_found_online", FlagSeverity.LOW, f"Director '{director_name}' not found in online search results associated with the business", "duckduckgo_search", director_query, "duckduckgo_director_search"))

        if website and not website_reachable:
            flags.append(_make_flag("website_unreachable", FlagSeverity.MEDIUM, f"Declared website '{website}' is unreachable or returns an error", "duckduckgo_search", website, "website_validation"))

        if scam_count >= 2:
            snippet = (scam_results[0].get("body") or scam_results[0].get("snippet") or "")[:100]
            flags.append(
                _make_flag(
                    "negative_reputation_signals",
                    FlagSeverity.HIGH,
                    f"Negative reputation signals found online: {snippet}",
                    "duckduckgo_search",
                    scam_query,
                    "duckduckgo_reputation_search",
                )
            )

        agent_log(f"   📊 Footprint summary: web={result_count} | social={social_count} ({', '.join(social_platforms) or 'none'}) | director={director_count} | scam={scam_count} | website={'✅' if website_reachable else '❌' if website else 'N/A'}")
        agent_log(f"   📊 Combined footprint score: {footprint_score:.1f} → {status}")
        category_flag = await check_category_web_consistency(business_name, declared_category, results)
        if category_flag:
            flags.append(category_flag)

        agent_log(f"   Top titles: {[item.get('title') for item in results[:2]]}")
        return ToolResult(
            "duckduckgo_search",
            status,
            confidence,
            {
                "query": query,
                "result_count": result_count,
                "top_titles": [item.get("title") for item in results[:2]],
                "social_media_count": social_count,
                "social_platforms_found": sorted(social_platforms),
                "director_search_count": director_count,
                "scam_query": scam_query,
                "scam_result_count": scam_count,
                "website_declared": website or None,
                "website_reachable": website_reachable if website else None,
                "footprint_score": round(footprint_score, 1),
            },
            flags,
            True,
            False,
            "duckduckgo",
            "DuckDuckGo multi-layer footprint and reputation search completed.",
        )
    except DuckDuckGoSearchException as exc:
        agent_log(f"DuckDuckGo rate limited — using fallback: {exc}", "warning")
        return _web_footprint_fallback(business_name, website, str(exc), external_call_made=True)
    except Exception as exc:
        agent_log(f"   DuckDuckGo failed — using fallback: {exc}", "warning")
        return _web_footprint_fallback(business_name, website, str(exc), external_call_made=True)


def _web_footprint_fallback(business_name: str, website: str, reason: str, external_call_made: bool) -> ToolResult:
    flags: list[Flag] = []
    if website:
        status = "declared_website"
        confidence = 0.55
    else:
        status = "fallback_no_website"
        confidence = 0.35
        flags.append(
            _make_flag(
                "weak_web_footprint",
                FlagSeverity.LOW,
                "Vendor has weak local web-footprint evidence.",
                "vendor_submission",
                f"business={business_name}; website={website}",
                "local_web_fallback",
            )
        )
    return ToolResult(
        "duckduckgo_search",
        status,
        confidence,
        {"business_name": business_name, "website": website, "external_call_failed": True, "failure_reason": reason},
        flags,
        external_call_made,
        True,
        "duckduckgo_local_fallback",
        "Web search unavailable; website fallback used.",
    )


def _score_agent_flags(flags: list[Flag], tools: list[ToolResult]) -> int:
    score = 100
    for flag in flags:
        score -= SEVERITY_DEDUCTIONS[flag.severity]
    if any(flag.severity == FlagSeverity.CRITICAL for flag in flags):
        score = min(score, 35)
    if sum(1 for flag in flags if flag.severity == FlagSeverity.HIGH) >= 2:
        score = min(score, 55)
    return max(0, min(100, score))


async def _legacy_anthropic_summary(payload: dict[str, Any]) -> tuple[str, ToolResult] | None:
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        data = await _post_json(
            ANTHROPIC_MESSAGES_URL,
            json_payload={
                "model": CLAUDE_HAIKU_MODEL,
                "max_tokens": 200,
                "system": SUMMARY_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": json.dumps(payload, default=str)}],
            },
            headers={
                "x-api-key": settings.ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        content = data.get("content") or []
        text = " ".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
        if text:
            return text, ToolResult("llm_summary", "generated", 0.90, {"model": CLAUDE_HAIKU_MODEL}, [], True, False, "claude_haiku")
    except Exception as exc:
        agent_log(f"   Legacy Claude summary failed — using local summary: {exc}", "warning")
    return None


async def generate_compliance_summary(tools: list[ToolResult], flags: list[Flag], score: int, action: str) -> tuple[str, ToolResult]:
    payload = {
        "agent_score": score,
        "recommended_action": action,
        "tools": [tool_result_to_json(tool) for tool in tools],
        "flags": [flag.model_dump() for flag in flags],
    }
    agent_log("── GENERATING COMPLIANCE SUMMARY...")
    started = time.perf_counter()
    try:
        if not _use_nvidia_llama():
            raise RuntimeError(f"NVIDIA summary disabled ({_llm_provider()})")
        text = _call_llama(SUMMARY_SYSTEM_PROMPT, payload, max_tokens=200).strip()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        agent_log(f"   Summary: {text}")
        return text, ToolResult("llm_summary", "generated", 0.90, {"model": NVIDIA_MODEL, "latency_ms": elapsed_ms}, [], True, False, "nvidia_llama")
    except Exception as exc:
        legacy = await _legacy_anthropic_summary(payload)
        if legacy:
            agent_log(f"   Summary: {legacy[0]}")
            return legacy
        agent_log(f"   LLaMA summary unavailable — using local template: {exc}", "warning")
        critical = sum(1 for flag in flags if flag.severity == FlagSeverity.CRITICAL)
        high = sum(1 for flag in flags if flag.severity == FlagSeverity.HIGH)
        if critical:
            text = "The verification found critical inconsistencies in the vendor evidence, including identity or registry signals that require compliance attention. Provider outages, if any, were treated as operational warnings rather than fraud evidence."
        elif high:
            text = "The verification found high-risk signals that should be reviewed before onboarding. Identity, registry, address, and web-footprint results are available in the tool log for the compliance reviewer."
        else:
            text = "The verification found mostly reassuring identity, registry, address, and web-footprint signals. Any external provider fallback is logged separately and was not treated as a fraud finding."
        agent_log(f"   Summary: {text}")
        return text, ToolResult(
            "llm_summary",
            "local_fallback",
            0.70,
            {"external_call_failed": True, "failure_reason": str(exc)},
            [],
            False,
            True,
            "local_template_explainer",
        )


def _flag_counts(flags: list[Flag]) -> dict[FlagSeverity, int]:
    return {severity: sum(1 for flag in flags if flag.severity == severity) for severity in FlagSeverity}


def _external_services_used(tools: list[ToolResult]) -> list[str]:
    order = ["dojah_bvn", "dojah_nin", "cac_public_registry", "nominatim_maps", "duckduckgo", "google_search", "nvidia_llama", "claude_haiku"]
    used = {tool.provider for tool in tools if tool.external_call_made and not tool.external_call_failed}
    return [provider for provider in order if provider in used]


async def _execute_tool(
    tool_name: str,
    vendor_facts: dict[str, Any],
    extracted_fields: dict[str, Any],
    context: dict[str, Any],
) -> ToolResult:
    if not settings.EXTERNAL_VERIFICATION_ENABLED:
        if tool_name == "dojah_bvn":
            return _local_identity_fallback("dojah_bvn", "external_verification_disabled", vendor_facts.get("bvn", ""))
        if tool_name == "dojah_nin":
            return _local_identity_fallback("dojah_nin", "external_verification_disabled", vendor_facts.get("nin", ""))
        if tool_name == "cac_registry":
            return _cac_local_fallback(
                vendor_facts.get("rc_number", ""),
                vendor_facts.get("business_name", ""),
                extracted_fields.get("rc_numbers", []),
                "external_verification_disabled",
                external_call_made=False,
            )
        if tool_name == "google_maps":
            return ToolResult(
                "google_maps",
                "local_review",
                0.50,
                {"address": vendor_facts.get("address", ""), "external_call_failed": True, "failure_reason": "external_verification_disabled"},
                [],
                False,
                True,
                "google_maps_local_fallback",
                "External verification disabled; address left for local review.",
            )
        if tool_name == "duckduckgo_search":
            return _web_footprint_fallback(
                vendor_facts.get("business_name", ""),
                vendor_facts.get("website", ""),
                "external_verification_disabled",
                external_call_made=False,
            )
    if tool_name == "dojah_bvn":
        result = await tool_dojah_bvn(vendor_facts.get("bvn", ""), vendor_facts.get("director_name", ""))
        if result.data.get("returned_name"):
            context["bvn_name"] = result.data["returned_name"]
        return result
    if tool_name == "dojah_nin":
        return await tool_dojah_nin(vendor_facts.get("nin", ""), context.get("bvn_name", ""))
    if tool_name == "cac_registry":
        return await tool_cac_registry(
            vendor_facts.get("rc_number", ""),
            vendor_facts.get("business_name", ""),
            extracted_fields.get("rc_numbers", []),
        )
    if tool_name == "google_maps":
        return await tool_google_maps(vendor_facts.get("address", ""))
    if tool_name == "duckduckgo_search":
        return await tool_duckduckgo_search(
            vendor_facts.get("business_name", ""),
            vendor_facts.get("website", ""),
            vendor_facts.get("director_name", ""),
            vendor_facts.get("business_category", ""),
        )
    return ToolResult(tool_name, "skipped_unknown_tool", 0.0, {"tool_name": tool_name}, [], False, False, "local")


async def run_agentic_verification_async(vendor_submission: dict, extracted_fields: dict | None = None) -> AgentVerificationResult:
    extracted_fields = extracted_fields or {}
    start = time.perf_counter()
    business_name = vendor_submission.get("business_name", "unknown vendor")
    tier = vendor_submission.get("tier", "unknown")
    agent_log(f"▶ AGENT START — vendor: {business_name} | tier: {tier}")

    vendor_facts = {
        "business_name": business_name,
        "rc_number": vendor_submission.get("rc_number", ""),
        "director_name": vendor_submission.get("director_name", ""),
        "bvn": vendor_submission.get("bvn", ""),
        "nin": vendor_submission.get("nin", ""),
        "address": vendor_submission.get("address", ""),
        "tier": tier,
        "website": vendor_submission.get("website") or vendor_submission.get("website_url", ""),
        "business_category": vendor_submission.get("business_category", ""),
        "email": vendor_submission.get("email", ""),
        "extracted_fields": extracted_fields,
    }

    if not settings.EXTERNAL_VERIFICATION_ENABLED:
        agent_log("   External verification disabled — graceful local/fallback mode active", "warning")

    plan = generate_verification_plan(vendor_facts)
    plan_steps = [step for step in plan.get("plan", []) if step.get("tool") in DEFAULT_TOOL_ORDER]
    if not plan_steps:
        plan_steps = _default_plan(vendor_facts, "empty plan").get("plan", [])

    tools: list[ToolResult] = []
    scored_flags: list[Flag] = []
    advisory_flags: list[Flag] = []
    context: dict[str, Any] = {}
    step_index = 0
    override_next_tool: str | None = None

    while step_index < len(plan_steps):
        planned = plan_steps[step_index]
        tool_name = override_next_tool or planned.get("tool")
        override_next_tool = None
        agent_log(f"── STEP {step_index + 1}/{len(plan_steps)}: Running tool → {tool_name}")
        result = await _execute_tool(tool_name, vendor_facts, extracted_fields, context)
        tools.append(result)
        scored_flags.extend(result.flags)
        if result.flags:
            agent_log(f"   Flags raised: {', '.join(flag.flag_type for flag in result.flags)}")
        else:
            agent_log("   Flags raised: none")

        agent_log(f"── LLaMA REASONING after {tool_name}:")
        reasoning = reason_about_tool(result)
        agent_log(f"   Finding: {reasoning['finding']}")
        agent_log(f"   Risk delta: {reasoning['risk_delta']} — {reasoning['risk_delta_reason']}")
        agent_log(f"   Continue plan: {reasoning['continue_plan']}")
        raised = reasoning.get("flag_raised")
        if isinstance(raised, dict):
            severity = FlagSeverity(raised.get("severity", "low"))
            advisory_flags.append(
                _make_flag(
                    raised.get("type", "llama_advisory_flag"),
                    severity,
                    raised.get("detail", "LLaMA advisory finding."),
                    "llama_reasoning",
                    json.dumps(reasoning, default=str),
                    "llama_reasoning_advisory",
                )
            )
        if not reasoning.get("continue_plan", True):
            critical_count = sum(1 for f in scored_flags + advisory_flags if f.severity == FlagSeverity.CRITICAL)
            if reasoning.get("risk_delta") != "critical" and critical_count < 2:
                agent_log("   Plan continues — no critical flags to justify early stop")
            else:
                break
        if reasoning.get("override_next_tool") in DEFAULT_TOOL_ORDER:
            override_next_tool = reasoning["override_next_tool"]
        step_index += 1

    score = _score_agent_flags(scored_flags, tools)
    action = "approve" if score >= 75 else "manual_review" if score >= 45 else "block"
    summary, summary_tool = await generate_compliance_summary(tools, scored_flags + advisory_flags, score, action)
    tools.append(summary_tool)

    counts = _flag_counts(scored_flags)
    tool_scores = " | ".join(f"{tool.tool_name.replace('dojah_', '')}={int(tool.confidence * 100)}" for tool in tools if tool.tool_name != "llm_summary")
    agent_log("── SCORING:")
    agent_log(f"   Tool scores: {tool_scores}")
    agent_log(
        f"   Flags: {counts[FlagSeverity.CRITICAL]} critical | {counts[FlagSeverity.HIGH]} high | {counts[FlagSeverity.MEDIUM]} medium | {counts[FlagSeverity.LOW]} low"
    )
    agent_log(f"   Agent score: {score}/100")
    agent_log(f"   Recommended action: {action}")
    services_used = _external_services_used(tools)
    elapsed = time.perf_counter() - start
    agent_log(f"✓ AGENT COMPLETE — {elapsed:.1f}s | score: {score} | action: {action}")
    agent_log(f"   External services used: [{', '.join(services_used)}]")

    return AgentVerificationResult(
        agent_score=score,
        tools_called=[tool.to_agent_tool_result() for tool in tools],
        flags=scored_flags + advisory_flags,
        external_services_used=services_used,
        explanation=summary,
        recommended_action=action,
    )


def _run_coroutine_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[Any] = []
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if errors:
        raise errors[0]
    return result[0]


def run_agentic_verification(vendor_submission: dict, extracted_fields: dict | None = None) -> AgentVerificationResult:
    return _run_coroutine_sync(run_agentic_verification_async(vendor_submission, extracted_fields))


def agent_flags_to_legacy(flags: list[Flag]) -> list[dict]:
    severity_map = {
        FlagSeverity.INFO: 0,
        FlagSeverity.LOW: 1,
        FlagSeverity.MEDIUM: 2,
        FlagSeverity.HIGH: 3,
        FlagSeverity.CRITICAL: 3,
    }
    return [
        {
            "code": flag.flag_type.upper(),
            "title": flag.flag_type.replace("_", " ").title(),
            "description": flag.detail,
            "severity": severity_map[flag.severity],
            "source": "agentic_verification",
        }
        for flag in flags
        if flag.severity != FlagSeverity.INFO
    ]
