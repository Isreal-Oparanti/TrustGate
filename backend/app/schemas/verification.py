import datetime as dt
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
