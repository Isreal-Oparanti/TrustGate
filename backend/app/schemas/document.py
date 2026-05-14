import datetime as dt
from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_id: str
    doc_type: str
    filename: str
    content_type: str
    path: str
    uploaded_at: dt.datetime
