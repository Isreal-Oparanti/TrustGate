import datetime as dt
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    title: str
    description: str
    severity: int
    source: str
    created_at: dt.datetime


class TrustScore(BaseModel):
    score: int
    risk_level: str
    verdict: str


class FlagSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Flag(BaseModel):
    flag_type: str
    severity: FlagSeverity
    detail: str
    source_doc: str
    evidence: str
    check_method: str
    similarity_score: Optional[float] = None


class ClassifierResult(BaseModel):
    predicted_class: str
    confidence: float
    top_suspicious_features: list[str]
    smoothing_applied: str


class OCRResult(BaseModel):
    raw_text: str
    doc_type: str
    confidence_score: float          # 0.0 to 1.0
    page_count: int
    file_type: str                   # "pdf" or "image"
    extraction_method: str           # "pymupdf_text", "tesseract", "tesseract_enhanced"
    warnings: list[str]              # Quality warnings
    char_count: int                  # Length of raw_text
    processing_time_ms: int
    corrections_applied: list[str]   # List of text corrections made


class OCRBatchResult(BaseModel):
    vendor_id: str
    documents: dict[str, OCRResult]  # doc_type -> result
    total_processing_time_ms: int
    avg_confidence: float
    low_confidence_docs: list[str]   # doc_types with confidence < 0.70


class NLPResult(BaseModel):
    nlp_score: int
    flags: list[Flag]
    extracted_fields: dict
    classifier_result: ClassifierResult
    processing_time_ms: int
    summary: str
    documents_processed: int
    checks_passed: int
    checks_failed: int


class AgentToolResult(BaseModel):
    tool_name: str
    fact_type: str
    status: str
    confidence: float
    provider: str
    external_call_used: bool
    external_call_failed: bool = False
    evidence: dict
    notes: str


class AgentVerificationResult(BaseModel):
    agent_score: int
    tools_called: list[AgentToolResult]
    flags: list[Flag]
    external_services_used: list[str]
    explanation: str
    recommended_action: str


class VerificationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_id: str
    trust_score: int
    risk_level: str
    verdict: str
    summary: str
    ocr_text: Optional[str] = None
    nlp_notes: Optional[str] = None
    identity_status: str
    anomaly_notes: Optional[str] = None
    flags: List[FlagOut] = []
    created_at: dt.datetime


class VerificationRunOut(BaseModel):
    verification: VerificationResult
    recommendation: str
