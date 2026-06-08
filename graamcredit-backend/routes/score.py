from fastapi import APIRouter
from pydantic import BaseModel

from ml.predict import predict_score

router = APIRouter()


class ScoreRequest(BaseModel):
    age: int
    annual_income: float
    monthly_expenses: float
    existing_loans: int
    monthly_emi: float
    upi_transactions: int
    mobile_recharges: int
    in_shg: bool


class ScoreResponse(BaseModel):
    score: int
    probability: float


@router.post("/score", response_model=ScoreResponse)
def get_score(req: ScoreRequest):
    """Quick ML score without saving to database."""
    score = predict_score(
        age=req.age,
        annual_income=req.annual_income,
        monthly_expenses=req.monthly_expenses,
        existing_loans=req.existing_loans,
        monthly_emi=req.monthly_emi,
        upi_transactions=req.upi_transactions,
        mobile_recharges=req.mobile_recharges,
        in_shg=req.in_shg,
    )
    return ScoreResponse(score=score, probability=round(score / 100, 4))
