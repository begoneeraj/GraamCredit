import os
from typing import Any, Dict

import joblib
import pandas as pd

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")
_cache: Dict[str, Any] = {}

# Maps employment_type string → income regularity score (0–1)
_REGULARITY = {
    "salaried": 1.0,
    "business": 0.7,
    "farmer": 0.5,
    "other": 0.5,
    "laborer": 0.4,
}


def _load():
    if "model" not in _cache:
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                "ml/model.pkl not found. Run 'python ml/train.py' first."
            )
        _cache.update(joblib.load(_MODEL_PATH))
    return _cache["model"], _cache["features"]


def predict_score(
    age: int,
    annual_income: float,
    monthly_expenses: float,
    existing_loans: int,
    monthly_emi: float,
    upi_transactions: int,
    mobile_recharges: int,
    in_shg: bool,
    savings_balance: float = 0.0,
    num_dependents: int = 0,
    employment_type: str = "other",
) -> int:
    """Return repayment probability as an integer score 0–100."""
    model, features = _load()

    monthly_income = annual_income / 12 if annual_income > 0 else 1.0
    expense_ratio = monthly_expenses / monthly_income
    debt_ratio = monthly_emi / monthly_income
    disposable = monthly_income - monthly_expenses - monthly_emi
    savings_rate = max(disposable / monthly_income, 0.0)
    liquidity_ratio = savings_balance / max(monthly_expenses, 1.0)
    income_regularity = _REGULARITY.get(employment_type.lower(), 0.5)

    row = {
        "age": age,
        "annual_income": annual_income,
        "monthly_expenses": monthly_expenses,
        "existing_loans": existing_loans,
        "monthly_emi": monthly_emi,
        "upi_transactions": upi_transactions,
        "mobile_recharges": mobile_recharges,
        "in_shg": int(in_shg),
        "savings_balance": savings_balance,
        "num_dependents": num_dependents,
        "expense_ratio": expense_ratio,
        "debt_ratio": debt_ratio,
        "savings_rate": savings_rate,
        "liquidity_ratio": liquidity_ratio,
        "income_regularity": income_regularity,
    }

    X = pd.DataFrame([row])[features]
    prob = model.predict_proba(X)[0][1]
    return int(round(prob * 100))
