import datetime as dt
from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False)

    vendor = relationship("Vendor", back_populates="documents")
