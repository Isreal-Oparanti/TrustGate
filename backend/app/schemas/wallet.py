import datetime as dt
from typing import Any
from pydantic import BaseModel, ConfigDict


class WalletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_id: str
    customer_identifier: str
    virtual_account_number: str | None = None
    account_name: str | None = None
    bank: str | None = None
    bank_code: str | None = None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime


class WalletCreateResponse(BaseModel):
    wallet: WalletOut
    squad_response: dict[str, Any]
