from pydantic import BaseModel


class SquadCreateMerchantRequest(BaseModel):
    vendor_id: str
