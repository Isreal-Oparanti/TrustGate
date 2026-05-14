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
    website_url: Optional[str] = None
    social_media_url: Optional[str] = None
    business_category: Optional[str] = None
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    bvn: str
    nin: str
    email: EmailStr
    phone: str
    address: str
    director_name: Optional[str] = None
    expected_monthly_volume: Optional[int] = None
    tier: TierEnum


class VendorStatusUpdate(BaseModel):
    status: VerdictEnum


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    rc_number: Optional[str] = None
    website_url: Optional[str] = None
    social_media_url: Optional[str] = None
    business_category: Optional[str] = None
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    account_number: Optional[str] = None
    account_name: Optional[str] = None
    bvn: str
    nin: str
    email: str
    phone: str
    address: str
    director_name: Optional[str] = None
    expected_monthly_volume: Optional[int] = None
    tier: TierEnum
    status: str
    squad_merchant_id: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime
