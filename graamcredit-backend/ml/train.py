"""
GraamCredit ML Model Training — Enhanced Pipeline
===================================================
Generates realistic synthetic microloan data modelled on rural India
demographics, trains multiple classifiers with extensive hyperparameter
search, cross-validation, and ensemble stacking, then saves the best
model to ml/model.pkl.

Run:  python ml/train.py
"""
import os
import time
import warnings
import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
    StackingClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

warnings.filterwarnings("ignore")

RANDOM_SEED = 42
N_SAMPLES = 10_000

FEATURE_COLS = [
    "age",
    "annual_income",
    "monthly_expenses",
    "existing_loans",
    "monthly_emi",
    "upi_transactions",
    "mobile_recharges",
    "in_shg",
    "savings_balance",
    "num_dependents",
    "expense_ratio",
    "debt_ratio",
    "savings_rate",
    "liquidity_ratio",
    "income_regularity",
]


# ── Realistic synthetic data generator ────────────────────────────────────────

def generate_data(n: int = N_SAMPLES) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)

    # ── Demographics ──────────────────────────────────────────────────────
    age = np.clip(rng.normal(loc=35, scale=12, size=n).astype(int), 18, 65)

    # ── Income (annual, INR) ──────────────────────────────────────────────
    annual_income = np.clip(
        rng.lognormal(mean=11.2, sigma=0.55, size=n),
        30_000, 300_000,
    )
    monthly_income = annual_income / 12

    # ── Expenses ──────────────────────────────────────────────────────────
    base_expense_ratio = np.clip(rng.beta(a=3, b=2, size=n), 0.35, 0.95)
    income_effect = np.clip(1.0 - (annual_income - 30_000) / 270_000 * 0.15, 0.85, 1.0)
    adjusted_expense_ratio = np.clip(base_expense_ratio * income_effect, 0.35, 0.95)
    monthly_expenses = monthly_income * adjusted_expense_ratio

    # ── Loans ─────────────────────────────────────────────────────────────
    existing_loans = rng.choice([0, 1, 2, 3], size=n, p=[0.55, 0.30, 0.10, 0.05])
    emi_ratio_raw = np.where(
        existing_loans > 0,
        rng.beta(a=2, b=5, size=n) * 0.60,
        0.0,
    )
    monthly_emi = monthly_income * emi_ratio_raw

    # ── Digital footprint ─────────────────────────────────────────────────
    digital_active = rng.random(size=n) < 0.45
    upi_low = rng.integers(0, 8, size=n)
    upi_high = rng.integers(8, 61, size=n)
    upi_transactions = np.where(digital_active, upi_high, upi_low)

    mobile_recharges = np.where(
        digital_active,
        rng.integers(3, 13, size=n),
        rng.integers(0, 5, size=n),
    )

    in_shg = rng.choice([0, 1], size=n, p=[0.70, 0.30]).astype(int)

    # ── Employment type → income regularity ───────────────────────────────
    # salaried=1.0, business=0.7, farmer=0.5, other=0.5, laborer=0.4
    emp_codes = rng.choice([1.0, 0.7, 0.5, 0.5, 0.4], size=n, p=[0.20, 0.20, 0.30, 0.10, 0.20])
    income_regularity = emp_codes

    # ── Savings ───────────────────────────────────────────────────────────
    # Disposable income per month × 3–9 months saved (with some having zero)
    disposable = np.maximum(monthly_income - monthly_expenses - monthly_emi, 0)
    months_saved = np.where(
        rng.random(size=n) < 0.25,   # 25% have no savings
        0.0,
        rng.uniform(1, 9, size=n),
    )
    savings_balance = disposable * months_saved

    # ── Number of dependents ──────────────────────────────────────────────
    num_dependents = rng.choice([0, 1, 2, 3, 4, 5], size=n, p=[0.05, 0.10, 0.25, 0.30, 0.20, 0.10])

    # ── Derived features ──────────────────────────────────────────────────
    expense_ratio = monthly_expenses / monthly_income
    debt_ratio = monthly_emi / monthly_income
    savings_rate = np.clip(disposable / monthly_income, 0, 1)
    liquidity_ratio = np.clip(savings_balance / np.maximum(monthly_expenses, 1), 0, 20)

    # ── Scoring function ──────────────────────────────────────────────────
    # Weights sum to 1.0
    score = np.zeros(n, dtype=float)

    # Expense ratio (20%)
    score += np.clip(1.0 - (expense_ratio - 0.40) / 0.50, 0, 1) * 0.20

    # Debt ratio (15%)
    score += np.clip(1.0 - debt_ratio / 0.50, 0, 1) * 0.15

    # UPI activity (12%)
    score += np.clip(upi_transactions / 30, 0, 1) * 0.12

    # Existing loans (13%)
    score += np.where(existing_loans == 0, 0.13,
             np.where(existing_loans == 1, 0.06, 0.0))

    # SHG membership (8%)
    score += in_shg * 0.08

    # Mobile activity (4%)
    score += np.clip(mobile_recharges / 8, 0, 1) * 0.04

    # Age stability (4%)
    age_stability = np.where((age >= 25) & (age <= 55), 1.0,
                    np.where(age < 25, 0.6, 0.5))
    score += age_stability * 0.04

    # Income adequacy (4%)
    score += np.clip((annual_income - 30_000) / 200_000, 0, 1) * 0.04

    # Savings rate (10%) — NEW
    score += savings_rate * 0.10

    # Liquidity (5%) — NEW: having 3+ months expenses saved is ideal
    score += np.clip(liquidity_ratio / 3, 0, 1) * 0.05

    # Income regularity (5%) — NEW
    score += income_regularity * 0.05

    # ── Convert to binary label ───────────────────────────────────────────
    prob = 1 / (1 + np.exp(-8 * (score - 0.50)))
    noise = rng.normal(0, 0.10, size=n)
    prob_noisy = np.clip(prob + noise, 0, 1)
    will_repay = (rng.random(size=n) < prob_noisy).astype(int)

    return pd.DataFrame({
        "age": age,
        "annual_income": annual_income,
        "monthly_expenses": monthly_expenses,
        "existing_loans": existing_loans,
        "monthly_emi": monthly_emi,
        "upi_transactions": upi_transactions,
        "mobile_recharges": mobile_recharges,
        "in_shg": in_shg,
        "savings_balance": savings_balance,
        "num_dependents": num_dependents,
        "expense_ratio": expense_ratio,
        "debt_ratio": debt_ratio,
        "savings_rate": savings_rate,
        "liquidity_ratio": liquidity_ratio,
        "income_regularity": income_regularity,
        "will_repay": will_repay,
    })


# ── Training pipeline ────────────────────────────────────────────────────────

def train():
    start_time = time.time()
    print("=" * 70)
    print("  GraamCredit ML Training Pipeline - Enhanced")
    print("=" * 70)

    print(f"\n>> Generating {N_SAMPLES:,} synthetic training samples...")
    df = generate_data()
    repay_rate = df["will_repay"].mean()
    print(f"  Dataset shape : {df.shape}")
    print(f"  Repayment rate: {repay_rate:.1%}")
    print("  Feature stats:")
    print(df[FEATURE_COLS].describe().round(2).to_string())

    X = df[FEATURE_COLS]
    y = df["will_repay"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED, stratify=y
    )
    print(f"\n  Train set: {len(X_train):,}  |  Test set: {len(X_test):,}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)

    print("\n" + "=" * 70)
    print("  Phase 1: Individual Model Training + Cross-Validation")
    print("=" * 70)

    results = {}

    # ── 1. Logistic Regression ────────────────────────────────────────────
    print("\n>> [1/5] Logistic Regression -- Grid Search...")
    lr_pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(random_state=RANDOM_SEED, max_iter=2000)),
    ])
    lr_params = {
        "clf__C": [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0],
        "clf__penalty": ["l1", "l2"],
        "clf__solver": ["liblinear", "saga"],
    }
    lr_grid = GridSearchCV(lr_pipe, lr_params, cv=cv, scoring="roc_auc", n_jobs=-1, verbose=0)
    lr_grid.fit(X_train, y_train)
    best_lr = lr_grid.best_estimator_
    print(f"  Best params: {lr_grid.best_params_}")
    print(f"  Best CV AUC: {lr_grid.best_score_:.4f}")
    results["LogisticRegression"] = {"model": best_lr, "cv_auc": lr_grid.best_score_}

    # ── 2. Random Forest ──────────────────────────────────────────────────
    print("\n>> [2/5] Random Forest -- Grid Search...")
    rf_pipe = Pipeline([
        ("clf", RandomForestClassifier(random_state=RANDOM_SEED, n_jobs=-1)),
    ])
    rf_params = {
        "clf__n_estimators": [100, 200, 300],
        "clf__max_depth": [5, 10, 15, 20, None],
        "clf__min_samples_split": [2, 5, 10],
        "clf__min_samples_leaf": [1, 2, 4],
    }
    rf_grid = GridSearchCV(rf_pipe, rf_params, cv=cv, scoring="roc_auc", n_jobs=-1, verbose=0)
    rf_grid.fit(X_train, y_train)
    best_rf = rf_grid.best_estimator_
    print(f"  Best params: {rf_grid.best_params_}")
    print(f"  Best CV AUC: {rf_grid.best_score_:.4f}")
    results["RandomForest"] = {"model": best_rf, "cv_auc": rf_grid.best_score_}

    # ── 3. Gradient Boosting ──────────────────────────────────────────────
    print("\n>> [3/5] Gradient Boosting -- Grid Search...")
    gb_pipe = Pipeline([
        ("clf", GradientBoostingClassifier(random_state=RANDOM_SEED)),
    ])
    gb_params = {
        "clf__n_estimators": [100, 200, 300],
        "clf__max_depth": [3, 5, 7],
        "clf__learning_rate": [0.01, 0.05, 0.1, 0.2],
        "clf__subsample": [0.8, 1.0],
        "clf__min_samples_split": [2, 5],
    }
    gb_grid = GridSearchCV(gb_pipe, gb_params, cv=cv, scoring="roc_auc", n_jobs=-1, verbose=0)
    gb_grid.fit(X_train, y_train)
    best_gb = gb_grid.best_estimator_
    print(f"  Best params: {gb_grid.best_params_}")
    print(f"  Best CV AUC: {gb_grid.best_score_:.4f}")
    results["GradientBoosting"] = {"model": best_gb, "cv_auc": gb_grid.best_score_}

    # ── 4. AdaBoost ───────────────────────────────────────────────────────
    print("\n>> [4/5] AdaBoost -- Grid Search...")
    ada_pipe = Pipeline([
        ("clf", AdaBoostClassifier(
            estimator=DecisionTreeClassifier(max_depth=3),
            random_state=RANDOM_SEED,
        )),
    ])
    ada_params = {
        "clf__n_estimators": [50, 100, 200, 300],
        "clf__learning_rate": [0.01, 0.05, 0.1, 0.5, 1.0],
    }
    ada_grid = GridSearchCV(ada_pipe, ada_params, cv=cv, scoring="roc_auc", n_jobs=-1, verbose=0)
    ada_grid.fit(X_train, y_train)
    best_ada = ada_grid.best_estimator_
    print(f"  Best params: {ada_grid.best_params_}")
    print(f"  Best CV AUC: {ada_grid.best_score_:.4f}")
    results["AdaBoost"] = {"model": best_ada, "cv_auc": ada_grid.best_score_}

    # ── 5. Stacking Ensemble ──────────────────────────────────────────────
    print("\n>> [5/5] Stacking Ensemble (LR + RF + GB -> meta LR)...")
    stacking = Pipeline([
        ("clf", StackingClassifier(
            estimators=[("lr", best_lr), ("rf", best_rf), ("gb", best_gb)],
            final_estimator=LogisticRegression(C=1.0, max_iter=2000, random_state=RANDOM_SEED),
            cv=cv,
            n_jobs=-1,
            passthrough=False,
        )),
    ])
    stacking.fit(X_train, y_train)
    stack_cv_scores = cross_val_score(stacking, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=-1)
    stack_cv_auc = stack_cv_scores.mean()
    print(f"  CV AUC: {stack_cv_auc:.4f} (±{stack_cv_scores.std():.4f})")
    results["StackingEnsemble"] = {"model": stacking, "cv_auc": stack_cv_auc}

    # ── Final evaluation ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  Phase 2: Final Evaluation on Test Set")
    print("=" * 70)

    best_name = None
    best_auc = 0.0
    best_model = None

    for name, info in results.items():
        model = info["model"]
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]

        acc = accuracy_score(y_test, y_pred)
        auc = roc_auc_score(y_test, y_prob)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)

        print(f"\n{'-' * 50}")
        print(f"  {name}")
        print(f"{'-' * 50}")
        print(f"  CV AUC-ROC   : {info['cv_auc']:.4f}")
        print(f"  Test AUC-ROC : {auc:.4f}")
        print(f"  Test Accuracy: {acc:.4f}")
        print(f"  Precision    : {prec:.4f}")
        print(f"  Recall       : {rec:.4f}")
        print(f"  F1-Score     : {f1:.4f}")
        print(classification_report(y_test, y_pred, target_names=["Default", "Repay"], digits=4))

        if auc > best_auc:
            best_auc = auc
            best_name = name
            best_model = model

    print("\n" + "=" * 70)
    print(f"  ** BEST MODEL: {best_name}")
    print(f"     Test AUC-ROC: {best_auc:.4f}")
    print("=" * 70)

    out_path = os.path.join(os.path.dirname(__file__), "model.pkl")
    joblib.dump({"model": best_model, "features": FEATURE_COLS}, out_path)
    print(f"\n  Saved -> {out_path}")

    elapsed = time.time() - start_time
    minutes, seconds = divmod(elapsed, 60)
    print(f"\n  Total training time: {int(minutes)}m {seconds:.1f}s")
    print("\n  Done. Start the server with:  python main.py")


if __name__ == "__main__":
    train()
