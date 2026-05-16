import datetime as dt
from pydantic import BaseModel, ConfigDict


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    transaction_ref: str
    amount: int
    customer_email: str | None = None
    transaction_status: str
    flagged: bool
    created_at: dt.datetime
    business_name: str | None = None
    rc_number: str | None = None
    flag_type: str | None = None


class TopMerchant(BaseModel):
    name: str
    volume: int


class TransactionStats(BaseModel):
    total_volume: int
    transactions: int
    flagged: int
    suspended: int
    top_merchants: list[TopMerchant]
