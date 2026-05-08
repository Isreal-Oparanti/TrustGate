import datetime as dt
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    trust_score = Column(Integer, nullable=False)
    risk_level = Column(String, nullable=False, index=True)
    verdict = Column(String, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    ocr_text = Column(Text, nullable=True)
    nlp_notes = Column(Text, nullable=True)
    identity_status = Column(String, nullable=False, default="mock_checked")
    anomaly_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False, index=True)

    vendor = relationship("Vendor", back_populates="verifications")
    flags = relationship("Flag", back_populates="verification", cascade="all, delete-orphan")
