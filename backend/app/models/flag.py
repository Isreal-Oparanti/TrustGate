import datetime as dt
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Flag(Base):
    __tablename__ = "flags"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    verification_id = Column(String, ForeignKey("verifications.id"), nullable=False, index=True)
    code = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(Integer, nullable=False, default=1)
    source = Column(String, nullable=False, default="ai_engine")
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False)

    vendor = relationship("Vendor", back_populates="flags")
    verification = relationship("Verification", back_populates="flags")
