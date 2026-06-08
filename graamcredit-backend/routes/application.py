from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from ml.predict import predict_score
from models.database import get_db
from utils.email import send_result_notification
from models.schemas import (
    ApplicationDetailResponse,
    ApplicationRequest,
    ApplicationResponse,
    DeleteResponse,
    RuleCheck,
    ScoreDistribution,
    StatsResponse,
)
from models.tables import Application

router = APIRouter()


# ── Hard eligibility rule engine ──────────────────────────────────────────────

def _run_hard_rules(req: ApplicationRequest):
    """Returns (all_passed, reasons, top_rejection_reason_or_None)."""
    monthly_income = req.annual_income / 12 if req.annual_income > 0 else 1.0
    debt_ratio = req.monthly_emi / monthly_income

    reasons: List[RuleCheck] = []
    failures: List[str] = []

    # 1 — Age
    age_ok = 18 <= req.age <= 65
    reasons.append(RuleCheck(
        rule="Age check",
        passed=age_ok,
        detail=f"Age {req.age} {'meets' if age_ok else 'does not meet'} 18–65 requirement",
    ))
    if not age_ok:
        failures.append("Age outside 18–65 range")

    # 2 — Income
    income_ok = req.annual_income <= 300_000
    lakhs = req.annual_income / 100_000
    reasons.append(RuleCheck(
        rule="Income limit",
        passed=income_ok,
        detail=f"₹{lakhs:.1f}L {'within' if income_ok else 'exceeds'} ₹3L cap",
    ))
    if not income_ok:
        failures.append("Income exceeds ₹3L limit")

    # 3 — Debt ratio
    debt_ok = debt_ratio < 0.50
    reasons.append(RuleCheck(
        rule="Debt ratio",
        passed=debt_ok,
        detail=f"{debt_ratio:.0%} {'below' if debt_ok else 'exceeds'} 50% limit",
    ))
    if not debt_ok:
        failures.append("Debt ratio too high")

    # 4 — Existing loans
    loan_ok = req.existing_loans == 0
    reasons.append(RuleCheck(
        rule="No existing loan",
        passed=loan_ok,
        detail="Clean record" if loan_ok else f"{req.existing_loans} active loan(s) found",
    ))
    if not loan_ok:
        failures.append("Has existing loan(s)")

    all_passed = len(failures) == 0
    return all_passed, reasons, (failures[0] if failures else None)


def _improvement_tips(
    req: ApplicationRequest,
    rules_passed: bool,
    score: int,
    reasons: List[RuleCheck],
) -> List[str]:
    tips = []
    monthly_income = req.annual_income / 12 if req.annual_income > 0 else 1.0
    expense_ratio = req.monthly_expenses / monthly_income

    if not reasons[0].passed:
        tips.append("Applicant must be between 18 and 65 years old to qualify.")
    if not reasons[1].passed:
        tips.append("Annual income must be under ₹3,00,000 to qualify for this scheme.")
    if not reasons[2].passed:
        tips.append("Reduce monthly EMI commitments to below 50% of monthly income.")
    if not reasons[3].passed:
        tips.append("Clear existing loan obligations before submitting a new application.")

    if rules_passed and score < 80:
        monthly_income = req.annual_income / 12 if req.annual_income > 0 else 1.0
        if req.savings_balance < monthly_income:
            tips.append(
                "Building a savings buffer of at least 1 month's income significantly improves your credit score."
            )
        if req.upi_transactions <= 10:
            tips.append(
                "Increase UPI transaction activity (aim for 10+ per month) to build your digital credit history."
            )
        if not req.in_shg:
            tips.append(
                "Joining a Self-Help Group (SHG) or Joint Liability Group (JLG) can significantly boost your score."
            )
        if req.mobile_recharges < 4:
            tips.append(
                "Maintain consistent mobile recharge activity (4+ per 6 months) to signal digital engagement."
            )
        if expense_ratio > 0.60:
            tips.append(
                "Reducing monthly household expenses to below 60% of income will improve your financial health score."
            )

    return tips


def _max_loan(score: int, eligible: bool) -> int:
    if not eligible:
        return 0
    if score >= 80:
        return 50_000
    if score >= 60:
        return 35_000
    return 25_000


def _gen_app_id(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.query(func.count(Application.id)).scalar() or 0
    return f"GC-{year}-{str(count + 1).zfill(5)}"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/apply", response_model=ApplicationResponse, status_code=201)
def apply(req: ApplicationRequest, db: Session = Depends(get_db)):
    rules_passed, reasons, rejection_reason = _run_hard_rules(req)

    if rules_passed:
        score = predict_score(
            age=req.age,
            annual_income=req.annual_income,
            monthly_expenses=req.monthly_expenses,
            existing_loans=req.existing_loans,
            monthly_emi=req.monthly_emi,
            upi_transactions=req.upi_transactions,
            mobile_recharges=req.mobile_recharges,
            in_shg=req.in_shg,
            savings_balance=req.savings_balance,
            num_dependents=req.num_dependents,
            employment_type=req.employment_type,
        )
        eligible = score >= 40
        if not eligible:
            rejection_reason = "Score below minimum threshold"
    else:
        score = 0
        eligible = False

    max_loan = _max_loan(score, eligible)
    tips = _improvement_tips(req, rules_passed, score, reasons)
    app_id = _gen_app_id(db)
    now = datetime.utcnow()

    record = Application(
        application_id=app_id,
        name=req.name,
        email=req.email,
        age=req.age,
        gender=req.gender,
        state=req.state,
        id_type=req.id_type,
        id_number=req.id_number,
        annual_income=req.annual_income,
        monthly_expenses=req.monthly_expenses,
        existing_loans=req.existing_loans,
        monthly_emi=req.monthly_emi,
        employment_type=req.employment_type,
        savings_balance=req.savings_balance,
        num_dependents=req.num_dependents,
        upi_transactions=req.upi_transactions,
        mobile_recharges=req.mobile_recharges,
        in_shg=req.in_shg,
        eligible=eligible,
        score=score,
        max_loan_amount=max_loan,
        rejection_reason=rejection_reason,
        created_at=now,
    )
    db.add(record)
    db.commit()

    if req.email:
        send_result_notification(
            to_email=req.email,
            applicant_name=req.name,
            application_id=app_id,
            eligible=eligible,
            score=score,
            max_loan_amount=max_loan,
            improvement_tips=tips,
        )

    return ApplicationResponse(
        application_id=app_id,
        eligible=eligible,
        score=score,
        max_loan_amount=max_loan,
        reasons=reasons,
        improvement_tips=tips,
        created_at=now,
    )


@router.get("/application/{application_id}", response_model=ApplicationDetailResponse)
def get_application(application_id: str, db: Session = Depends(get_db)):
    record = (
        db.query(Application)
        .filter(
            Application.application_id == application_id,
            Application.deleted == False,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Application not found.")

    monthly_income = record.annual_income / 12 if record.annual_income > 0 else 1.0
    debt_ratio = record.monthly_emi / monthly_income
    lakhs = record.annual_income / 100_000

    age_ok = 18 <= record.age <= 65
    income_ok = record.annual_income <= 300_000
    debt_ok = debt_ratio < 0.50
    loan_ok = record.existing_loans == 0

    reasons = [
        RuleCheck(
            rule="Age check",
            passed=age_ok,
            detail=f"Age {record.age} {'meets' if age_ok else 'does not meet'} 18–65 requirement",
        ),
        RuleCheck(
            rule="Income limit",
            passed=income_ok,
            detail=f"₹{lakhs:.1f}L {'within' if income_ok else 'exceeds'} ₹3L cap",
        ),
        RuleCheck(
            rule="Debt ratio",
            passed=debt_ok,
            detail=f"{debt_ratio:.0%} {'below' if debt_ok else 'exceeds'} 50% limit",
        ),
        RuleCheck(
            rule="No existing loan",
            passed=loan_ok,
            detail="Clean record" if loan_ok else f"{record.existing_loans} active loan(s) found",
        ),
    ]

    rules_passed = all(r.passed for r in reasons)
    mock_req = ApplicationRequest(
        name=record.name or "",
        age=record.age,
        gender=record.gender or "",
        state=record.state or "",
        id_type=record.id_type or "",
        id_number=record.id_number or "",
        annual_income=record.annual_income,
        monthly_expenses=record.monthly_expenses,
        existing_loans=record.existing_loans,
        monthly_emi=record.monthly_emi,
        employment_type=record.employment_type or "",
        savings_balance=record.savings_balance or 0.0,
        num_dependents=record.num_dependents or 0,
        upi_transactions=record.upi_transactions,
        mobile_recharges=record.mobile_recharges,
        in_shg=record.in_shg,
    )
    tips = _improvement_tips(mock_req, rules_passed, record.score, reasons)

    return ApplicationDetailResponse(
        application_id=record.application_id,
        eligible=record.eligible,
        score=record.score,
        max_loan_amount=record.max_loan_amount,
        reasons=reasons,
        improvement_tips=tips,
        created_at=record.created_at,
        name=record.name,
        age=record.age,
        gender=record.gender,
        state=record.state,
        annual_income=record.annual_income,
        monthly_expenses=record.monthly_expenses,
        existing_loans=record.existing_loans,
        monthly_emi=record.monthly_emi,
        employment_type=record.employment_type,
        upi_transactions=record.upi_transactions,
        mobile_recharges=record.mobile_recharges,
        in_shg=record.in_shg,
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    total = (
        db.query(func.count(Application.id))
        .filter(Application.deleted == False)
        .scalar()
        or 0
    )

    if total == 0:
        return StatsResponse(
            total_applications=0,
            approval_rate=0.0,
            average_score=0.0,
            top_rejection_reason="N/A",
            score_distribution=ScoreDistribution(very_low=0, low=0, medium=0, high=0),
        )

    approved = (
        db.query(func.count(Application.id))
        .filter(Application.eligible == True, Application.deleted == False)
        .scalar()
        or 0
    )

    avg_score = (
        db.query(func.avg(Application.score))
        .filter(Application.deleted == False)
        .scalar()
        or 0.0
    )

    top_reason_row = (
        db.query(
            Application.rejection_reason,
            func.count(Application.rejection_reason).label("cnt"),
        )
        .filter(
            Application.eligible == False,
            Application.deleted == False,
            Application.rejection_reason.isnot(None),
        )
        .group_by(Application.rejection_reason)
        .order_by(func.count(Application.rejection_reason).desc())
        .first()
    )
    top_reason = top_reason_row[0] if top_reason_row else "N/A"

    dist_row = db.query(
        func.sum(case((Application.score < 40, 1), else_=0)).label("very_low"),
        func.sum(case(((Application.score >= 40) & (Application.score < 60), 1), else_=0)).label("low"),
        func.sum(case(((Application.score >= 60) & (Application.score < 80), 1), else_=0)).label("medium"),
        func.sum(case((Application.score >= 80, 1), else_=0)).label("high"),
    ).filter(Application.deleted == False).one()

    score_dist = ScoreDistribution(
        very_low=int(dist_row.very_low or 0),
        low=int(dist_row.low or 0),
        medium=int(dist_row.medium or 0),
        high=int(dist_row.high or 0),
    )

    return StatsResponse(
        total_applications=total,
        approval_rate=round(approved / total, 4),
        average_score=round(float(avg_score), 1),
        top_rejection_reason=top_reason or "N/A",
        score_distribution=score_dist,
    )


@router.get("/stats/applications")
def get_recent_applications(limit: int = 10, db: Session = Depends(get_db)):
    """Returns last N applications with anonymised fields only (for admin panel)."""
    records = (
        db.query(Application)
        .filter(Application.deleted == False)
        .order_by(Application.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "application_id": r.application_id,
            "score": r.score,
            "eligible": r.eligible,
            "state": r.state,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@router.delete("/application/{application_id}", response_model=DeleteResponse)
def delete_application(application_id: str, db: Session = Depends(get_db)):
    record = (
        db.query(Application)
        .filter(Application.application_id == application_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Application not found.")

    # Anonymise personal data — DPDP Act right to erasure
    record.name = "[DELETED]"
    record.id_type = None
    record.id_number = None
    record.gender = None
    record.annual_income = 0
    record.monthly_expenses = 0
    record.monthly_emi = 0
    record.existing_loans = 0
    record.employment_type = None
    record.upi_transactions = 0
    record.mobile_recharges = 0
    record.in_shg = False
    record.deleted = True
    db.commit()

    return DeleteResponse(deleted=True)
