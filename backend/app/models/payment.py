import datetime as dt
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    transaction_ref = Column(String, nullable=False, unique=True, index=True)
    customer_email = Column(String, nullable=False, index=True)
    customer_name = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False, default="NGN", index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    checkout_url = Column(String, nullable=True)
    squad_gateway_ref = Column(String, nullable=True, index=True)
    squad_transaction_type = Column(String, nullable=True)
    security_challenge_verified = Column(Boolean, nullable=False, default=False)
    fraud_status = Column(String, nullable=False, default="not_run", index=True)
    fraud_notes = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    squad_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    vendor = relationship("Vendor", back_populates="payments")
