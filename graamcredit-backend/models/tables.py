from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100))
    email = Column(String(200), nullable=True)
    age = Column(Integer)
    gender = Column(String(10))
    state = Column(String(100))
    id_type = Column(String(50))
    id_number = Column(String(50))
    annual_income = Column(Float)
    monthly_expenses = Column(Float)
    existing_loans = Column(Integer)
    monthly_emi = Column(Float)
    employment_type = Column(String(100))
    savings_balance = Column(Float, nullable=True, default=0.0)
    num_dependents = Column(Integer, nullable=True, default=0)
    upi_transactions = Column(Integer)
    mobile_recharges = Column(Integer)
    in_shg = Column(Boolean)
    eligible = Column(Boolean)
    score = Column(Integer)
    max_loan_amount = Column(Integer)
    rejection_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted = Column(Boolean, default=False)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    email = Column(String(200))
    subject = Column(String(200))
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    replied = Column(Boolean, default=False)


class AASession(Base):
    """
    Account Aggregator consent session — backs both the mock AA flow
    (see routes/account_aggregator.py) and, when USE_MOCK_AA=false, the
    real Setu integration. Persists across requests instead of the old
    in-memory dict so the flow survives server restarts.
    """
    __tablename__ = "aa_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    consent_handle = Column(String(64), unique=True, nullable=False)
    mobile = Column(String(50))
    purpose = Column(String(200))
    status = Column(String(20), default="pending")  # pending|approved|denied|fi_ready|error
    bank_name = Column(String(100), nullable=True)
    account_masked = Column(String(50), nullable=True)
    ifsc = Column(String(20), nullable=True)
    fi_data = Column(Text, nullable=True)          # JSON: AAFetchResponse fields
    transactions = Column(Text, nullable=True)      # JSON: list of raw transactions
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
