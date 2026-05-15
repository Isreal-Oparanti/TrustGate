import datetime as dt
import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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
    tier: TierEnum = TierEnum.tier2
    settlement_account_name: str = Field(min_length=1)
    settlement_account_number: str = Field(min_length=1)
    settlement_bank_code: str = Field(min_length=1)
    settlement_bank: str = Field(min_length=1)
    payment_security_question: str = Field(min_length=1)
    payment_security_answer: str = Field(min_length=1)

    @field_validator("rc_number")
    @classmethod
    def validate_rc_number(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not 6 <= len(value) <= 13:
            raise ValueError("RC number must be between 6 and 13 characters.")
        return value

    @field_validator("bvn")
    @classmethod
    def validate_bvn(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 11:
            raise ValueError("BVN must be exactly 11 numeric characters.")
        return value

    @field_validator("nin")
    @classmethod
    def validate_nin(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 11:
            raise ValueError("NIN must be exactly 11 numeric characters.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip().replace(" ", "").replace("-", "")
        if normalized.startswith("+"):
            normalized = normalized[1:]
        if not normalized.isdigit() or len(normalized) not in {11, 13}:
            raise ValueError("Mobile number length should be either 11 or 13 digits.")
        if not re.match(r"^(234|0)[789][01]\d{8}$", normalized):
            raise ValueError("Enter a valid Nigerian mobile number.")
        return normalized


class VendorLogin(BaseModel):
    business_name: str = Field(min_length=1)
    rc_number: str = Field(min_length=1)


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
    squad_account_id: Optional[str] = None
    squad_merchant_id: Optional[str] = None
    settlement_status: str = "not_started"
    payment_security_question: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime


class VendorSubMerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    rc_number: Optional[str] = None
    tier: TierEnum
    status: str
    squad_account_id: Optional[str] = None
    settlement_status: str = "not_started"
    payment_security_question: Optional[str] = None
    created_at: dt.datetime


class VendorCreateResponse(BaseModel):
    vendor: VendorSubMerchantOut
    squad_response: dict[str, Any]
