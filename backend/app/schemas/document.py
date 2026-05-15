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
    file_size_kb: int | None = None
    uploaded_at: dt.datetime
