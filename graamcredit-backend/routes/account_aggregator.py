"""
Setu Account Aggregator (AA) integration — Phase 3.

Flow:
  1.  POST /api/aa/initiate   → create consent request with Setu, return redirect URL
  2.  User approves via Setu's consent manager UI (webview / redirect)
  3.  POST /api/aa/webhook    → Setu notifies us: consent approved / denied
  4.  GET  /api/aa/status/{session_id} → poll until FI data is ready
  5.  GET  /api/aa/fetch/{session_id}  → return parsed financial fields (same shape as /parse-statement)

Prerequisites:
  Register at https://setu.co/products/data/account-aggregator
  Set in .env:
    SETU_BASE_URL      https://fiu-uat.setu.co   (UAT sandbox)
    SETU_CLIENT_ID     from Setu dashboard
    SETU_CLIENT_SECRET from Setu dashboard
    SETU_FIU_ID        from Setu dashboard
    BACKEND_PUBLIC_URL https://your-ngrok-or-deployed-url.com
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

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


# ── In-memory session store (replace with DB for production) ──────────────────
# Maps session_id → {status, consent_handle, fi_data, created_at}
_sessions: dict[str, dict] = {}


# ── Request / response models ─────────────────────────────────────────────────

class AAInitiateRequest(BaseModel):
    customer_id: str    # Mobile number or AA VUA (e.g. "9999999999@onemoney")
    purpose: str = "Loan underwriting"


class AAInitiateResponse(BaseModel):
    session_id: str
    redirect_url: str
    expires_at: str


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


# ── Step 1: Initiate consent ──────────────────────────────────────────────────

@router.post("/aa/initiate", response_model=AAInitiateResponse)
async def aa_initiate(req: AAInitiateRequest):
    """
    Create a Setu consent request.
    Returns a redirect_url — the frontend should open it in a new tab/webview.
    """
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

    # Setu AA FIU API v2 — confirmed working payload shape
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

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{cfg['base']}/v2/consents",
            headers=_headers(cfg),
            json=consent_payload,
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Setu consent creation failed: {resp.text[:200]}",
        )

    data = resp.json()
    consent_handle = data.get("id") or session_id
    redirect_url   = data.get("url") or f"{cfg['base']}/v2/consents/ui/{consent_handle}"

    _sessions[session_id] = {
        "status":         "pending",
        "consent_handle": consent_handle,
        "fi_data":        None,
        "created_at":     now.isoformat(),
    }

    return AAInitiateResponse(
        session_id=session_id,
        redirect_url=redirect_url,
        expires_at=expires_at.isoformat(),
    )


# ── Step 1b: Browser callback after Setu consent UI ──────────────────────────

@router.get("/aa/callback/{session_id}")
async def aa_callback(session_id: str):
    """
    Setu redirects the user's browser here after they approve/deny consent.
    We bounce them back to the frontend form with the session_id so it can poll status.
    """
    frontend_url = os.getenv("CORS_ORIGINS", "http://localhost:5500").split(",")[0].strip()
    return RedirectResponse(url=f"{frontend_url}/form.html?aa_session={session_id}", status_code=302)


# ── Step 2: Setu webhook (consent + session notifications) ────────────────────

@router.post("/aa/webhook")
async def aa_webhook(request: Request, background: BackgroundTasks):
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

    event_type  = body.get("type", "")
    consent_id  = body.get("consentId", "") or body.get("ConsentHandle", "")

    # Locate matching session
    session_id = next(
        (sid for sid, s in _sessions.items() if s["consent_handle"] == consent_id),
        None,
    )

    # ── CONSENT_STATUS_UPDATE ────────────────────────────────────────────────
    if event_type == "CONSENT_STATUS_UPDATE" or not event_type:
        # Setu v2: status lives at body.data.status (not body.status)
        status = (
            body.get("data", {}).get("status", "")
            or body.get("status", "")
            or body.get("ConsentStatus", {}).get("status", "")
        )

        if not session_id:
            return {"ok": True}

        if status.upper() in ("ACTIVE", "APPROVED"):
            _sessions[session_id]["status"] = "approved"
            # If Auto-Fetch is disabled, manually create a data session now.
            # With Auto-Fetch enabled, Setu handles this and we wait for
            # SESSION_STATUS_UPDATE before fetching.
            if os.getenv("SETU_AUTO_FETCH", "true").lower() != "true":
                background.add_task(_create_data_session, session_id)
        elif status.upper() in ("REJECTED", "REVOKED", "FAILED", "EXPIRED"):
            _sessions[session_id]["status"] = "denied"

    # ── SESSION_STATUS_UPDATE ────────────────────────────────────────────────
    elif event_type == "SESSION_STATUS_UPDATE":
        data_status    = body.get("data", {}).get("status", "")
        fi_session_id  = body.get("dataSessionId", "")

        if not session_id or not fi_session_id:
            return {"ok": True}

        if data_status.upper() in ("COMPLETED", "PARTIAL"):
            background.add_task(_fetch_fi_by_session_id, session_id, fi_session_id)
        elif data_status.upper() in ("FAILED", "EXPIRED"):
            _sessions[session_id]["status"] = "error"

    return {"ok": True}


# ── Step 3: Poll status ───────────────────────────────────────────────────────

@router.get("/aa/status/{session_id}", response_model=AAStatusResponse)
async def aa_status(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    s = _sessions[session_id]
    messages = {
        "pending":  "Waiting for user to approve consent.",
        "approved": "Consent approved. Fetching financial data…",
        "denied":   "User denied or revoked consent.",
        "fi_ready": "Financial data is ready.",
        "error":    "An error occurred while fetching data.",
    }
    return AAStatusResponse(
        session_id=session_id,
        status=s["status"],
        message=messages.get(s["status"], s["status"]),
    )


# ── Step 4: Fetch parsed FI data ──────────────────────────────────────────────

@router.get("/aa/fetch/{session_id}", response_model=AAFetchResponse)
async def aa_fetch(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    s = _sessions[session_id]
    if s["status"] != "fi_ready":
        raise HTTPException(
            status_code=425,
            detail=f"FI data not ready yet. Current status: {s['status']}",
        )

    return AAFetchResponse(**s["fi_data"])


# ── Background helpers ────────────────────────────────────────────────────────

async def _create_data_session(session_id: str) -> None:
    """
    Used when Auto-Fetch is DISABLED.
    Creates a Setu data session after consent approval.
    Setu will then send SESSION_STATUS_UPDATE when the bank responds.
    """
    cfg    = _cfg()
    handle = _sessions[session_id]["consent_handle"]
    now    = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            ds_resp = await client.post(
                f"{cfg['base']}/v2/sessions",
                headers=_headers(cfg),
                json={
                    "consentId": handle,
                    "dataRange": {
                        "from": (now - timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "to":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                },
            )
        if ds_resp.status_code not in (200, 201):
            print(f"[AA] POST /sessions failed for {session_id}: {ds_resp.text[:200]}")
            _sessions[session_id]["status"] = "error"
            return
        fi_session_id = (ds_resp.json().get("id") or ds_resp.json().get("sessionId", ""))
        _sessions[session_id]["fi_session_id"] = fi_session_id
        print(f"[AA] Data session created: {fi_session_id} for {session_id}")
    except Exception as exc:
        print(f"[AA] _create_data_session error for {session_id}: {exc}")
        _sessions[session_id]["status"] = "error"


async def _fetch_fi_by_session_id(session_id: str, fi_session_id: str) -> None:
    """
    Called when SESSION_STATUS_UPDATE arrives (COMPLETED/PARTIAL).
    Fetches the actual financial data from Setu using the data-session ID.
    Works regardless of whether Auto-Fetch is enabled or disabled.
    """
    cfg = _cfg()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            fi_resp = await client.get(
                f"{cfg['base']}/v2/sessions/{fi_session_id}",
                headers=_headers(cfg),
            )
        if fi_resp.status_code != 200:
            print(f"[AA] GET /sessions/{fi_session_id} failed: {fi_resp.text[:200]}")
            _sessions[session_id]["status"] = "error"
            return
        fi_raw = fi_resp.json()
        print(f"[AA] FI data received for {session_id} (keys: {list(fi_raw.keys())})")
        _sessions[session_id]["fi_data"] = _parse_fi(fi_raw)
        _sessions[session_id]["status"]  = "fi_ready"
    except Exception as exc:
        print(f"[AA] _fetch_fi_by_session_id error for {session_id}: {exc}")
        _sessions[session_id]["status"] = "error"


def _parse_fi(fi_raw: dict) -> dict:
    """
    Parse Setu FI response (ReBIT schema) into our summary fields.
    FI data is returned as a list of FI objects per account.
    """
    credits: list[float] = []
    debits:  list[float] = []
    balances: list[float] = []
    upi_count = 0
    emi_amounts: list[float] = []

    accounts = fi_raw.get("FI", []) or fi_raw.get("fiObjects", [])
    for account in accounts:
        # Profile — closing balance
        profile = account.get("Profile", {})
        balance = profile.get("Holders", {})
        # Balance from Summary
        summary = account.get("Summary", {})
        if isinstance(summary, dict):
            bal = summary.get("currentBalance") or summary.get("closingBalance") or 0
            try:
                balances.append(float(bal))
            except (ValueError, TypeError):
                pass

        # Transactions
        txns = account.get("Transactions", {}).get("Transaction", [])
        for txn in txns:
            amount = 0.0
            try:
                amount = float(str(txn.get("amount", 0)).replace(",", ""))
            except (ValueError, TypeError):
                pass

            if amount <= 0:
                continue

            txn_type = str(txn.get("type", "")).upper()
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

    monthly_credit  = sum(credits)  / 6 if credits  else 0.0
    monthly_debit   = sum(debits)   / 6 if debits   else 0.0
    closing_balance = max(balances) if balances else 0.0

    # Deduplicate EMI amounts by rounding to nearest 500
    emi_set: dict[int, float] = {}
    for amt in emi_amounts:
        bucket = int(round(amt / 500) * 500)
        emi_set[bucket] = max(emi_set.get(bucket, 0), amt)
    monthly_emi   = sum(emi_set.values())
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
