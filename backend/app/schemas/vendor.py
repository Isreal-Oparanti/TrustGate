import datetime as dt
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class TierEnum(str, Enum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"


class VerdictEnum(str, Enum):
    approved = "approved"
    review = "review"
    blocked = "blocked"


class VendorCreate(BaseModel):
    business_name: str
    rc_number: Optional[str] = None
    bvn: str
    nin: str
    email: EmailStr
    phone: str
    address: str
    tier: TierEnum


class VendorStatusUpdate(BaseModel):
    status: VerdictEnum


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    rc_number: Optional[str] = None
    tier: TierEnum
    status: str
    squad_merchant_id: Optional[str] = None
    created_at: dt.datetime
