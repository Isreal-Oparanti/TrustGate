import datetime as dt
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    customer_identifier = Column(String, nullable=False, unique=True, index=True)
    virtual_account_number = Column(String, nullable=True, unique=True, index=True)
    account_name = Column(String, nullable=True)
    bank = Column(String, nullable=True)
    bank_code = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    squad_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    vendor = relationship("Vendor", back_populates="wallets")


class WalletActivity(Base):
    __tablename__ = "wallet_activities"

    id = Column(String, primary_key=True, index=True)
    vendor_id = Column(String, ForeignKey("vendors.id"), nullable=False, index=True)
    wallet_id = Column(String, ForeignKey("wallets.id"), nullable=True, index=True)
    activity_type = Column(String, nullable=False, index=True)
    direction = Column(String, nullable=False, index=True)
    reference = Column(String, nullable=False, unique=True, index=True)
    amount = Column(Integer, nullable=False, default=0)
    currency = Column(String, nullable=False, default="NGN")
    account_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    bank_code = Column(String, nullable=True)
    narration = Column(String, nullable=True)
    status = Column(String, nullable=True)
    squad_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False, index=True)
