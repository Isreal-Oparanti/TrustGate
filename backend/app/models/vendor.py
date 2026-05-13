import datetime as dt
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship
from app.database import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String, primary_key=True, index=True)
    business_name = Column(String, nullable=False, unique=True, index=True)
    rc_number = Column(String, nullable=True, index=True)
    bvn = Column(String, nullable=False)
    nin = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)
    address = Column(String, nullable=False)
    tier = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="pending", index=True)
    squad_account_id = Column(String, nullable=True, index=True)
    squad_merchant_id = Column(String, nullable=True, index=True)
    settlement_account_name = Column(String, nullable=True)
    settlement_account_number = Column(String, nullable=True)
    settlement_bank_code = Column(String, nullable=True)
    settlement_bank = Column(String, nullable=True)
    settlement_status = Column(String, nullable=False, default="not_started", index=True)
    payment_security_question = Column(String, nullable=True)
    payment_security_answer_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.UTC),
        onupdate=lambda: dt.datetime.now(dt.UTC),
        nullable=False,
    )

    documents = relationship("Document", back_populates="vendor", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="vendor", cascade="all, delete-orphan")
    flags = relationship("Flag", back_populates="vendor", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="vendor", cascade="all, delete-orphan")
    wallets = relationship("Wallet", back_populates="vendor", cascade="all, delete-orphan")
