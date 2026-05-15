from typing import Any
from pydantic import BaseModel, Field, field_validator


class TransferAccountLookupRequest(BaseModel):
    bank_code: str
    account_number: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")

    @field_validator("bank_code")
    @classmethod
    def validate_bank_code(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 6:
            raise ValueError("Bank code must be the 6-digit NIP code from Squad, for example 000013 for GTBank.")
        return value


class TransferInitiateRequest(BaseModel):
    amount: int = Field(gt=0, description="Amount in kobo.")
    bank_code: str
    account_number: str = Field(min_length=10, max_length=10, pattern=r"^\d{10}$")
    account_name: str = Field(min_length=1)
    remark: str = Field(min_length=1)
    security_answer: str = Field(min_length=1)

    @field_validator("bank_code")
    @classmethod
    def validate_bank_code(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 6:
            raise ValueError("Bank code must be the 6-digit NIP code from Squad, for example 000013 for GTBank.")
        return value


class TransferRequeryRequest(BaseModel):
    transaction_reference: str = Field(min_length=1)


class SquadPassthroughResponse(BaseModel):
    squad_response: dict[str, Any]
