"""
Account Aggregator (AA) integration — Phase 3.

  MOCKED: real Setu AA calls require registered business KYC (GST /
  incorporation documents) to activate the sandbox — Setu returns HTTP 403
  on consent creation for individual/student accounts, which blocks this
  flow end-to-end. Since a real business entity isn't available for this
  student project, this module ships a MOCK Account Aggregator layer that
  is functionally and visually identical to the real flow: same routes,
  same request/response shapes, same status progression
  (pending → approved → fi_ready), same downstream contract into
  /parse-statement's autofill and the ML scoring pipeline. The mock
  generates realistic synthetic bank account + transaction data instead
  of calling Setu.

  The original real-Setu implementation is preserved unmodified in the
  "REAL SETU INTEGRATION (PRESERVED FOR PRODUCTION)" section below and is
  used automatically instead of the mock when USE_MOCK_AA=false is set in
  .env (along with valid SETU_CLIENT_ID / SETU_CLIENT_SECRET / SETU_FIU_ID)
  — no rewrite needed to go live once business KYC is completed.

Flow (identical for mock and real):
  1.  POST /api/aa/initiate            → create consent request, return session_id
  2.  POST /api/aa/approve             → simulate/receive user's consent approval
  3.  GET  /api/aa/accounts/{session_id} → linked bank account(s)
  4.  GET  /api/aa/status/{session_id}  → poll until FI data is ready
  5.  GET  /api/aa/fetch/{session_id}   → parsed financial fields (same shape as /parse-statement)
  6.  GET  /api/aa/data/{session_id}    → richer FI-type detail (balance + transactions) for display

Prerequisites for the real path:
  Register at https://setu.co/products/data/account-aggregator
  Set in .env:
    USE_MOCK_AA        false            (switches off the mock)
    SETU_BASE_URL       https://fiu-uat.setu.co   (UAT sandbox)
    SETU_CLIENT_ID      from Setu dashboard
    SETU_CLIENT_SECRET  from Setu dashboard
    SETU_FIU_ID         from Setu dashboard
    BACKEND_PUBLIC_URL  https://your-ngrok-or-deployed-url.com
"""

import asyncio
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import AASession

router = APIRouter()


# ── Config helpers ────────────────────────────────────────────────────────────

def _cfg() -> dict:
    return {
        'base':    os.getenv('SETU_BASE_URL', 'https://fiu-uat.setu.co'),
        'id':      os.getenv('SETU_CLIENT_ID', ''),
        'secret':  os.getenv('SETU_CLIENT_SECRET', ''),
        'fiu_id':  os.getenv('SETU_FIU_ID', ''),
        'public':  os.getenv('BACKEND_PUBLIC_URL', 'http://127.0.0.1:8000'),
    }


def _headers(cfg: dict) -> dict:
    return {
        'x-client-id':          cfg['id'],
        'x-client-secret':      cfg['secret'],
        'x-product-instance-id': cfg['fiu_id'],
        'Content-Type':         'application/json',
    }


def _is_configured() -> bool:
    cfg = _cfg()
    return bool(cfg['id'] and cfg['secret'] and cfg['fiu_id'])


def _use_mock() -> bool:
    # Mock is the default active path — flip USE_MOCK_AA=false once
    # business KYC is done and real Setu credentials are configured.
    return os.getenv("USE_MOCK_AA", "true").strip().lower() != "false"


# ── Request / response models (shared by mock + real paths) ───────────────────

class AAInitiateRequest(BaseModel):
    customer_id: str    # Mobile number or AA VUA (e.g. "9999999999@onemoney")
    purpose: str = "Loan underwriting"


class AAInitiateResponse(BaseModel):
    session_id: str
    consent_handle: str
    redirect_url: str | None = None   # null in mock mode — frontend shows an inline consent modal instead
    status: str
    expires_at: str
    mock: bool = False


class AAApproveRequest(BaseModel):
    session_id: str


class AAApproveResponse(BaseModel):
    session_id: str
    status: str
    message: str


class AAAccount(BaseModel):
    bank_name: str
    account_masked: str
    ifsc: str
    account_type: str


class AAAccountsResponse(BaseModel):
    session_id: str
    accounts: list[AAAccount]


class AATransaction(BaseModel):
    date: str
    amount: float
    type: str        # credit | debit
    narration: str


class AADataSummary(BaseModel):
    avg_balance: float
    income_frequency: str
    expense_ratio: float


class AADataResponse(BaseModel):
    session_id: str
    account: AAAccount
    current_balance: float
    transactions: list[AATransaction]
    summary: AADataSummary


class AAStatusResponse(BaseModel):
    session_id: str
    status: str             # pending | approved | denied | fi_ready | error
    message: str


class AAFetchResponse(BaseModel):
    annual_income: float
    monthly_expenses: float
    savings_balance: float
    monthly_emi: float
    existing_loans: int
    upi_transactions: int
    mobile_recharges: int
    confidence: float


# ── Mock data generation ───────────────────────────────────────────────────────

_MOCK_BANKS = [
    ("State Bank of India", "SBIN"),
    ("HDFC Bank",           "HDFC"),
    ("ICICI Bank",          "ICIC"),
    ("Axis Bank",           "UTIB"),
    ("Punjab National Bank", "PUNB"),
]

_CREDIT_NARRATIONS = [
    "UPI-SALARY", "NEFT-CR-WAGES", "UPI-CR-FAMILY", "CASH DEPOSIT",
    "UPI-CR-MGNREGA", "IMPS-CR",
]
_DEBIT_NARRATIONS = [
    "UPI-GROCERY", "ATM-WDL", "UPI-DEBT-REPAY", "UPI-MEDICAL",
    "MOBILE-RECHARGE", "UPI-FERTILIZER", "ELECTRICITY-BILL", "UPI-TRANSPORT",
]


def _generate_fake_account() -> dict:
    bank_name, ifsc_prefix = random.choice(_MOCK_BANKS)
    acct_num = "".join(random.choices("0123456789", k=12))
    return {
        "bank_name":      bank_name,
        "account_masked": "XXXXXXXX" + acct_num[-4:],
        "ifsc":           f"{ifsc_prefix}0{random.randint(0, 999999):06d}",
        "account_type":   random.choice(["Savings", "Savings", "Savings", "Current"]),
    }


def _generate_fake_transactions(months: int = None) -> list[dict]:
    """Synthetic transaction history for a rural/low-income borrower profile:
    small irregular UPI credits, ATM withdrawals, occasional debt payments."""
    months = months or random.randint(3, 6)
    now = datetime.now(timezone.utc)
    txns: list[dict] = []

    for m in range(months):
        month_start = now - timedelta(days=30 * (m + 1))

        # One roughly-monthly income credit (wages / MGNREGA / family remittance)
        income_day = random.randint(1, 28)
        txns.append({
            "date":      (month_start + timedelta(days=income_day)).strftime("%Y-%m-%d"),
            "amount":    round(random.uniform(3000, 9000), 2),
            "type":      "credit",
            "narration": random.choice(_CREDIT_NARRATIONS),
        })

        # A few smaller irregular UPI credits
        for _ in range(random.randint(1, 4)):
            day = random.randint(1, 28)
            txns.append({
                "date":      (month_start + timedelta(days=day)).strftime("%Y-%m-%d"),
                "amount":    round(random.uniform(100, 1500), 2),
                "type":      "credit",
                "narration": random.choice(_CREDIT_NARRATIONS),
            })

        # Everyday debits: groceries, ATM withdrawals, recharges, bills
        for _ in range(random.randint(6, 14)):
            day = random.randint(1, 28)
            txns.append({
                "date":      (month_start + timedelta(days=day)).strftime("%Y-%m-%d"),
                "amount":    round(random.uniform(50, 1200), 2),
                "type":      "debit",
                "narration": random.choice(_DEBIT_NARRATIONS),
            })

        # Occasional existing debt repayment (not every month)
        if random.random() < 0.5:
            day = random.randint(1, 28)
            txns.append({
                "date":      (month_start + timedelta(days=day)).strftime("%Y-%m-%d"),
                "amount":    round(random.uniform(500, 2500), 2),
                "type":      "debit",
                "narration": "UPI-DEBT-REPAY",
            })

    txns.sort(key=lambda t: t["date"])
    return txns


def _summarize_transactions(txns: list[dict]) -> dict:
    """Compute AAFetchResponse-shaped summary fields from raw transactions —
    the same feature schema the ML pipeline already consumes from PDF parsing."""
    credits = [t["amount"] for t in txns if t["type"] == "credit"]
    debits  = [t["amount"] for t in txns if t["type"] == "debit"]
    debt_repayments = [t["amount"] for t in txns if t["narration"] == "UPI-DEBT-REPAY"]
    upi_count = sum(1 for t in txns if "UPI" in t["narration"])
    recharge_count = sum(1 for t in txns if t["narration"] == "MOBILE-RECHARGE")

    months = max(len({t["date"][:7] for t in txns}), 1)
    monthly_income  = sum(credits) / months if credits else 0.0
    monthly_expense = sum(debits) / months if debits else 0.0
    monthly_emi     = (sum(debt_repayments) / months) if debt_repayments else 0.0
    savings_balance = round(random.uniform(500, 15000), 2)

    return {
        "annual_income":    round(monthly_income * 12, 2),
        "monthly_expenses": round(monthly_expense, 2),
        "savings_balance":  savings_balance,
        "monthly_emi":      round(monthly_emi, 2),
        "existing_loans":   1 if debt_repayments else 0,
        "upi_transactions": upi_count,
        "mobile_recharges":  recharge_count,
        "confidence":       0.98,   # AA data is consent-verified, so higher than PDF-parsed confidence
    }


def _row_to_account(s: AASession) -> AAAccount:
    return AAAccount(
        bank_name=s.bank_name, account_masked=s.account_masked,
        ifsc=s.ifsc, account_type="Savings",
    )


# ── Step 1: Initiate consent ──────────────────────────────────────────────────

@router.post("/aa/initiate", response_model=AAInitiateResponse)
async def aa_initiate(req: AAInitiateRequest, db: Session = Depends(get_db)):
    if _use_mock():
        session_id     = str(uuid.uuid4())
        consent_handle = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        db.add(AASession(
            session_id=session_id,
            consent_handle=consent_handle,
            mobile=req.customer_id,
            purpose=req.purpose,
            status="pending",
        ))
        db.commit()

        return AAInitiateResponse(
            session_id=session_id,
            consent_handle=consent_handle,
            redirect_url=None,
            status="PENDING",
            expires_at=(now + timedelta(days=30)).isoformat(),
            mock=True,
        )

    return await _real_aa_initiate(req, db)


# ── Step 2: Approve consent (mock only — real flow uses Setu's webhook) ───────

@router.post("/aa/approve", response_model=AAApproveResponse)
async def aa_approve(req: AAApproveRequest, db: Session = Depends(get_db)):
    """Simulates the user approving the consent request on their AA app."""
    if not _use_mock():
        raise HTTPException(
            status_code=400,
            detail="Manual approval is only used in mock mode; the real Setu "
                   "flow is approved via the Setu consent UI and reported through /aa/webhook.",
        )

    session = db.query(AASession).filter(AASession.session_id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Artificial delay to mimic the real-world latency of the AA approval round-trip.
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # Rare simulated failure so the frontend keeps a real (friendly) retry path.
    if random.random() < 0.05:
        session.status = "error"
        db.commit()
        return AAApproveResponse(
            session_id=req.session_id, status="error",
            message="Bank did not respond in time. Please try again.",
        )

    account = _generate_fake_account()
    txns    = _generate_fake_transactions()
    summary = _summarize_transactions(txns)

    session.status         = "fi_ready"
    session.bank_name      = account["bank_name"]
    session.account_masked = account["account_masked"]
    session.ifsc           = account["ifsc"]
    session.transactions   = json.dumps(txns)
    session.fi_data        = json.dumps(summary)
    db.commit()

    return AAApproveResponse(
        session_id=req.session_id, status="fi_ready",
        message="Consent approved. Financial data is ready.",
    )


# ── Step 1b: Browser callback after Setu consent UI (real flow only) ─────────

@router.get("/aa/callback/{session_id}")
async def aa_callback(session_id: str):
    frontend_url = os.getenv("CORS_ORIGINS", "http://localhost:5500").split(",")[0].strip()
    return RedirectResponse(url=f"{frontend_url}/form.html?aa_session={session_id}", status_code=302)


# ── Step 2b: Setu webhook (real flow only — no-op while mocked) ───────────────

@router.post("/aa/webhook")
async def aa_webhook(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    if _use_mock():
        return {"ok": True, "message": "Mock mode active — consent is approved via POST /aa/approve, not this webhook."}
    return await _real_aa_webhook(request, background, db)


# ── Linked accounts ────────────────────────────────────────────────────────────

@router.get("/aa/accounts/{session_id}", response_model=AAAccountsResponse)
async def aa_accounts(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AASession).filter(AASession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not session.bank_name:
        raise HTTPException(status_code=425, detail="Consent not yet approved — no linked accounts.")

    return AAAccountsResponse(session_id=session_id, accounts=[_row_to_account(session)])


# ── Step 3: Poll status ───────────────────────────────────────────────────────

@router.get("/aa/status/{session_id}", response_model=AAStatusResponse)
async def aa_status(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AASession).filter(AASession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    messages = {
        "pending":  "Waiting for user to approve consent.",
        "approved": "Consent approved. Fetching financial data…",
        "denied":   "User denied or revoked consent.",
        "fi_ready": "Financial data is ready.",
        "error":    "An error occurred while fetching data.",
    }
    return AAStatusResponse(
        session_id=session_id,
        status=session.status,
        message=messages.get(session.status, session.status),
    )


# ── Step 4: Fetch parsed FI data (feeds the eligibility form + ML pipeline) ──

@router.get("/aa/fetch/{session_id}", response_model=AAFetchResponse)
async def aa_fetch(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AASession).filter(AASession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.status != "fi_ready":
        raise HTTPException(status_code=425, detail=f"FI data not ready yet. Current status: {session.status}")

    return AAFetchResponse(**json.loads(session.fi_data))


# ── Rich FI-type detail (for the "data fetched" display card) ────────────────

@router.get("/aa/data/{session_id}", response_model=AADataResponse)
async def aa_data(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AASession).filter(AASession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    if session.status != "fi_ready":
        raise HTTPException(status_code=425, detail=f"FI data not ready yet. Current status: {session.status}")

    txns = json.loads(session.transactions)
    fi   = json.loads(session.fi_data)
    balances = [t["amount"] for t in txns]

    return AADataResponse(
        session_id=session_id,
        account=_row_to_account(session),
        current_balance=fi["savings_balance"],
        transactions=[AATransaction(**t) for t in txns],
        summary=AADataSummary(
            avg_balance=round(sum(balances) / len(balances), 2) if balances else 0.0,
            income_frequency="Irregular (multiple small UPI credits/month)",
            expense_ratio=round(fi["monthly_expenses"] / max(fi["annual_income"] / 12, 1), 3),
        ),
    )


# ════════════════════════════════════════════════════════════════════════════
# REAL SETU INTEGRATION (PRESERVED FOR PRODUCTION)
#
# Mocked due to Setu sandbox requiring registered business KYC, not available
# for individual/student accounts. Real integration code preserved below for
# future production use — set USE_MOCK_AA=false in .env once business KYC and
# valid SETU_CLIENT_ID / SETU_CLIENT_SECRET / SETU_FIU_ID are available and
# the routes above will call straight through to these functions.
# ════════════════════════════════════════════════════════════════════════════

async def _real_aa_initiate(req: AAInitiateRequest, db: Session) -> AAInitiateResponse:
    if not _is_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Account Aggregator is not configured. "
                "Set SETU_CLIENT_ID, SETU_CLIENT_SECRET, and SETU_FIU_ID in .env. "
                "Register at https://setu.co/products/data/account-aggregator"
            ),
        )

    cfg = _cfg()
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)

    consent_payload = {
        "vua":           req.customer_id,
        "redirectUrl":   f"{cfg['public']}/api/aa/callback/{session_id}",
        "fetchType":     "ONETIME",
        "consentDuration": {"unit": "MONTH", "value": 1},
        "dataRange": {
            "from": (now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "dataLife": {"unit": "MONTH", "value": 0},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cfg['base']}/v2/consents",
                headers=_headers(cfg),
                json=consent_payload,
            )
    except httpx.TimeoutException as exc:
        print(f"[AA] /aa/initiate timeout calling Setu: {exc}")
        raise HTTPException(
            status_code=504,
            detail=f"Setu API timed out after 30s. Check SETU_BASE_URL ({cfg['base']}) is reachable.",
        )
    except httpx.RequestError as exc:
        print(f"[AA] /aa/initiate connection error calling Setu: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Setu API at {cfg['base']}: {exc}",
        )

    print(f"[AA] /aa/initiate Setu response: status={resp.status_code} body={resp.text[:300]}")

    if resp.status_code not in (200, 201):
        print(f"[AA] /aa/initiate Setu error: status={resp.status_code} body={resp.text}")
        raise HTTPException(
            status_code=502,
            detail=f"Setu consent creation failed (HTTP {resp.status_code}): {resp.text[:300]}",
        )

    data = resp.json()
    consent_handle = data.get("id") or session_id
    redirect_url   = data.get("url") or f"{cfg['base']}/v2/consents/ui/{consent_handle}"

    db.add(AASession(
        session_id=session_id,
        consent_handle=consent_handle,
        mobile=req.customer_id,
        purpose=req.purpose,
        status="pending",
    ))
    db.commit()

    return AAInitiateResponse(
        session_id=session_id,
        consent_handle=consent_handle,
        redirect_url=redirect_url,
        status="PENDING",
        expires_at=expires_at.isoformat(),
        mock=False,
    )


async def _real_aa_webhook(request: Request, background: BackgroundTasks, db: Session) -> dict:
    """
    Setu calls this endpoint for two event types:
      - CONSENT_STATUS_UPDATE : user approved/denied the consent
      - SESSION_STATUS_UPDATE  : bank data fetch completed (sent by Setu when
                                 Auto-Fetch is enabled OR after we POST /sessions)
    Configure this URL in Setu Bridge as the Notification Endpoint.
    Public URL: {BACKEND_PUBLIC_URL}/api/aa/webhook
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    print(f"[AA Webhook] {json.dumps(body)[:600]}")

    event_type = body.get("type", "")
    consent_id = body.get("consentId", "") or body.get("ConsentHandle", "")

    session = db.query(AASession).filter(AASession.consent_handle == consent_id).first()

    if event_type == "CONSENT_STATUS_UPDATE" or not event_type:
        status = (
            body.get("data", {}).get("status", "")
            or body.get("status", "")
            or body.get("ConsentStatus", {}).get("status", "")
        )

        if not session:
            return {"ok": True}

        if status.upper() in ("ACTIVE", "APPROVED"):
            session.status = "approved"
            db.commit()
            if os.getenv("SETU_AUTO_FETCH", "true").lower() != "true":
                background.add_task(_create_data_session, session.session_id)
        elif status.upper() in ("REJECTED", "REVOKED", "FAILED", "EXPIRED"):
            session.status = "denied"
            db.commit()

    elif event_type == "SESSION_STATUS_UPDATE":
        data_status   = body.get("data", {}).get("status", "")
        fi_session_id = body.get("dataSessionId", "")

        if not session or not fi_session_id:
            return {"ok": True}

        if data_status.upper() in ("COMPLETED", "PARTIAL"):
            background.add_task(_fetch_fi_by_session_id, session.session_id, fi_session_id)
        elif data_status.upper() in ("FAILED", "EXPIRED"):
            session.status = "error"
            db.commit()

    return {"ok": True}


async def _create_data_session(session_id: str) -> None:
    """Used when Auto-Fetch is DISABLED. Creates a Setu data session after consent approval."""
    from models.database import SessionLocal

    cfg = _cfg()
    db  = SessionLocal()
    try:
        session = db.query(AASession).filter(AASession.session_id == session_id).first()
        if not session:
            return
        now = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                ds_resp = await client.post(
                    f"{cfg['base']}/v2/sessions",
                    headers=_headers(cfg),
                    json={
                        "consentId": session.consent_handle,
                        "dataRange": {
                            "from": (now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "to":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        },
                    },
                )
            if ds_resp.status_code not in (200, 201):
                print(f"[AA] POST /sessions failed for {session_id}: {ds_resp.text[:200]}")
                session.status = "error"
                db.commit()
                return
            print(f"[AA] Data session created for {session_id}")
        except Exception as exc:
            print(f"[AA] _create_data_session error for {session_id}: {exc}")
            session.status = "error"
            db.commit()
    finally:
        db.close()


async def _fetch_fi_by_session_id(session_id: str, fi_session_id: str) -> None:
    """Called when SESSION_STATUS_UPDATE arrives (COMPLETED/PARTIAL)."""
    from models.database import SessionLocal

    cfg = _cfg()
    db  = SessionLocal()
    try:
        session = db.query(AASession).filter(AASession.session_id == session_id).first()
        if not session:
            return
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                fi_resp = await client.get(
                    f"{cfg['base']}/v2/sessions/{fi_session_id}",
                    headers=_headers(cfg),
                )
            if fi_resp.status_code != 200:
                print(f"[AA] GET /sessions/{fi_session_id} failed: {fi_resp.text[:200]}")
                session.status = "error"
                db.commit()
                return
            fi_raw = fi_resp.json()
            print(f"[AA] FI data received for {session_id} (keys: {list(fi_raw.keys())})")
            session.fi_data = json.dumps(_parse_fi(fi_raw))
            session.status  = "fi_ready"
            db.commit()
        except Exception as exc:
            print(f"[AA] _fetch_fi_by_session_id error for {session_id}: {exc}")
            session.status = "error"
            db.commit()
    finally:
        db.close()


def _parse_fi(fi_raw: dict) -> dict:
    """Parse Setu FI response (ReBIT schema) into our summary fields."""
    credits: list[float] = []
    debits:  list[float] = []
    balances: list[float] = []
    upi_count = 0
    emi_amounts: list[float] = []

    accounts = fi_raw.get("FI", []) or fi_raw.get("fiObjects", [])
    for account in accounts:
        summary = account.get("Summary", {})
        if isinstance(summary, dict):
            bal = summary.get("currentBalance") or summary.get("closingBalance") or 0
            try:
                balances.append(float(bal))
            except (ValueError, TypeError):
                pass

        txns = account.get("Transactions", {}).get("Transaction", [])
        for txn in txns:
            try:
                amount = float(str(txn.get("amount", 0)).replace(",", ""))
            except (ValueError, TypeError):
                amount = 0.0

            if amount <= 0:
                continue

            txn_type  = str(txn.get("type", "")).upper()
            narration = str(txn.get("narration", "") or txn.get("description", ""))

            if "UPI" in narration.upper() or "IMPS" in narration.upper():
                upi_count += 1

            if txn_type == "CREDIT":
                credits.append(amount)
            elif txn_type == "DEBIT":
                debits.append(amount)
                if any(k in narration.upper() for k in ("EMI", "LOAN", "ECS", "NACH")):
                    if amount >= 500:
                        emi_amounts.append(amount)

    monthly_credit  = sum(credits) / 6 if credits else 0.0
    monthly_debit   = sum(debits) / 6 if debits else 0.0
    closing_balance = max(balances) if balances else 0.0

    emi_set: dict[int, float] = {}
    for amt in emi_amounts:
        bucket = int(round(amt / 500) * 500)
        emi_set[bucket] = max(emi_set.get(bucket, 0), amt)
    monthly_emi    = sum(emi_set.values())
    existing_loans = len(emi_set)

    return {
        "annual_income":    round(monthly_credit * 12, 2),
        "monthly_expenses": round(monthly_debit, 2),
        "savings_balance":  round(closing_balance, 2),
        "monthly_emi":      round(monthly_emi, 2),
        "existing_loans":   existing_loans,
        "upi_transactions": upi_count,
        "mobile_recharges": 0,
        "confidence":       0.95,
    }
