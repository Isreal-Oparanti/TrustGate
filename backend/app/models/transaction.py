import datetime as dt
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    squad_account_id = Column(String, nullable=True, index=True)
    transaction_ref = Column(String, unique=True, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    customer_email = Column(String, nullable=True)
    transaction_status = Column(String, default="pending", index=True)
    flagged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False)

    vendor = relationship("Vendor", back_populates="transactions")
