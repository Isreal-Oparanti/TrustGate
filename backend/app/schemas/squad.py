import datetime as dt
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SquadCreateMerchantRequest(BaseModel):
    vendor_id: str


class PaymentCurrency(str, Enum):
    ngn = "NGN"
    usd = "USD"


class PaymentChannel(str, Enum):
    card = "card"
    bank = "bank"
    ussd = "ussd"
    transfer = "transfer"


class PaymentInitiateRequest(BaseModel):
    amount: int = Field(gt=0, description="Amount in the lowest currency unit, for example kobo for NGN.")
    customer_email: EmailStr
    customer_name: str = Field(min_length=1)
    security_answer: str = Field(min_length=1)
    currency: PaymentCurrency = PaymentCurrency.ngn
    callback_url: str | None = None
    payment_channels: list[PaymentChannel] = Field(
        default_factory=lambda: [
            PaymentChannel.card,
            PaymentChannel.bank,
            PaymentChannel.ussd,
            PaymentChannel.transfer,
        ]
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    pass_charge: bool = False


class PaymentInitiateResponse(BaseModel):
    transaction_ref: str
    status: str
    checkout_url: str | None
    security_challenge_verified: bool
    squad_response: dict[str, Any] | None = None


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_id: str
    transaction_ref: str
    customer_email: str
    customer_name: str
    amount: int
    currency: str
    status: str
    checkout_url: str | None = None
    squad_gateway_ref: str | None = None
    squad_transaction_type: str | None = None
    security_challenge_verified: bool
    fraud_status: str
    fraud_notes: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class PaymentStatusResponse(BaseModel):
    payment: PaymentOut
    squad_verification: dict[str, Any] | None = None
