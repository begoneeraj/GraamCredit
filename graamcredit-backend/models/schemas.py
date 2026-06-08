import re
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


class ApplicationRequest(BaseModel):
    name: str
    age: int
    gender: str
    state: str
    id_type: str
    id_number: str
    annual_income: float
    monthly_expenses: float
    existing_loans: int
    monthly_emi: float
    employment_type: str
    savings_balance: float = 0.0
    num_dependents: int = 0
    upi_transactions: int
    mobile_recharges: int
    in_shg: bool
    email: Optional[str] = None

    @field_validator("annual_income")
    @classmethod
    def income_positive(cls, v):
        if v <= 0:
            raise ValueError("Annual income must be positive")
        return v

    @field_validator("monthly_expenses", "monthly_emi")
    @classmethod
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v

    @field_validator("existing_loans", "upi_transactions", "mobile_recharges")
    @classmethod
    def non_negative_int(cls, v):
        if v < 0:
            raise ValueError("Value cannot be negative")
        return v


class RuleCheck(BaseModel):
    rule: str
    passed: bool
    detail: str


class ApplicationResponse(BaseModel):
    application_id: str
    eligible: bool
    score: int
    max_loan_amount: int
    reasons: List[RuleCheck]
    improvement_tips: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationDetailResponse(ApplicationResponse):
    name: str
    age: int
    gender: str
    state: str
    annual_income: float
    monthly_expenses: float
    existing_loans: int
    monthly_emi: float
    employment_type: str
    upi_transactions: int
    mobile_recharges: int
    in_shg: bool


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v.strip()):
            raise ValueError("Invalid email address")
        return v.strip()

    @field_validator("message")
    @classmethod
    def message_min_length(cls, v):
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Message must be at least 20 characters")
        return v


class ContactResponse(BaseModel):
    success: bool
    message: str


class ScoreDistribution(BaseModel):
    very_low: int   # 0–39
    low: int        # 40–59
    medium: int     # 60–79
    high: int       # 80–100


class StatsResponse(BaseModel):
    total_applications: int
    approval_rate: float
    average_score: float
    top_rejection_reason: str
    score_distribution: ScoreDistribution


class DeleteResponse(BaseModel):
    deleted: bool
