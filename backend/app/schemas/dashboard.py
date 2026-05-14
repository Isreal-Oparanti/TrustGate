from typing import List
from pydantic import BaseModel
from app.schemas.vendor import VendorOut
from app.schemas.verification import VerificationResult


class DashboardStats(BaseModel):
    total_today: int
    approved: int
    pending_review: int
    blocked: int
    avg_score: float


class QueueItem(BaseModel):
    vendor: VendorOut
    latest_verification: VerificationResult | None = None


class QueueOut(BaseModel):
    items: List[QueueItem]
