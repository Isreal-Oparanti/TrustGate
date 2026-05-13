import datetime as dt
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class TierEnum(str, Enum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"


class VendorCreate(BaseModel):
    business_name: str
    rc_number: Optional[str] = None
    bvn: str
    nin: str
    email: EmailStr
    phone: str
    address: str
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

class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_name: str
    rc_number: Optional[str] = None
    tier: TierEnum
    status: str
    squad_account_id: Optional[str] = None
    squad_merchant_id: Optional[str] = None
    settlement_status: str = "not_started"
    payment_security_question: Optional[str] = None
    created_at: dt.datetime


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
    squad_response: dict
