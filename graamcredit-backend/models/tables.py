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
