"""
Parse Indian bank statement PDFs to extract financial summary fields.

Supports common formats: SBI, HDFC, Axis, Canara, PNB, ICICI, UCO.
Returns best-effort estimates — not a substitute for AA-verified data.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pdfplumber


# Amount pattern for Indian number formatting (e.g. 1,23,456.78 or 12345.67)
_AMOUNT_RE = re.compile(r'\b[\d,]+\.\d{2}\b')
_UPI_RE    = re.compile(r'\b(UPI|IMPS|PhonePe|GPay|Paytm|BHIM)\b', re.I)
_EMI_RE    = re.compile(r'\b(EMI|LOAN|ECS|NACH|AUTO.?DEBIT|MANDATE)\b', re.I)
_CREDIT_RE = re.compile(r'\b(CR|CREDIT|Cr\.?)\b', re.I)
_DEBIT_RE  = re.compile(r'\b(DR|DEBIT|Dr\.?)\b', re.I)
_BALANCE_RE = re.compile(
    r'(?:closing|available|current|end)\s*balance[:\s]*'
    r'([\d,]+\.?\d*)',
    re.I,
)


def _parse_amount(text: str) -> Optional[float]:
    """Return first valid Indian-format amount from a string, else None."""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(0).replace(',', ''))
    except ValueError:
        return None


def _amounts_from_row(row: list) -> list[float]:
    amounts = []
    for cell in row:
        if not cell:
            continue
        for m in _AMOUNT_RE.finditer(str(cell)):
            try:
                amounts.append(float(m.group(0).replace(',', '')))
            except ValueError:
                pass
    return amounts


def parse_bank_statement(pdf_path: str) -> dict:
    """
    Returns a dict with keys:
      annual_income, monthly_expenses, savings_balance,
      monthly_emi, existing_loans, upi_transactions,
      mobile_recharges, confidence (0–1 float)

    Confidence is low (0.4) for text-only fallback, higher (0.7) when
    tables are found, and 0.9 when a closing balance is detected.
    """
    credits: list[float] = []
    debits:  list[float] = []
    upi_count     = 0
    emi_amounts:  list[float] = []
    closing_balance: Optional[float] = None
    full_text = ''
    tables_found = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ''
            full_text += page_text + '\n'

            tables = page.extract_tables()
            if tables:
                tables_found = True

            for table in tables:
                for row in table:
                    if not row:
                        continue
                    row_str = ' '.join(str(c or '') for c in row)
                    amounts  = _amounts_from_row(row)

                    # Skip header rows and zero-amount rows
                    if not amounts or any(k in row_str.lower() for k in ('date', 'narration', 'description', 'particulars')):
                        continue

                    is_upi  = bool(_UPI_RE.search(row_str))
                    is_emi  = bool(_EMI_RE.search(row_str))
                    is_cr   = bool(_CREDIT_RE.search(row_str))
                    is_dr   = bool(_DEBIT_RE.search(row_str))

                    if is_upi:
                        upi_count += 1

                    # Most statement tables: [date, narration, debit, credit, balance]
                    # or [date, narration, amount, Dr/Cr flag, balance]
                    if len(amounts) >= 3:
                        # Assume last amount is balance, second-to-last is credit, third-to-last is debit
                        closing_balance = amounts[-1]
                        if amounts[-2] and amounts[-2] > 0:
                            credits.append(amounts[-2])
                        if amounts[-3] and amounts[-3] > 0 and not is_cr:
                            debits.append(amounts[-3])
                            if is_emi and amounts[-3] >= 500:
                                emi_amounts.append(amounts[-3])
                    elif len(amounts) == 2:
                        if is_cr:
                            credits.append(amounts[0])
                        elif is_dr:
                            debits.append(amounts[0])
                            if is_emi and amounts[0] >= 500:
                                emi_amounts.append(amounts[0])
                        closing_balance = amounts[-1]
                    elif len(amounts) == 1:
                        if is_cr:
                            credits.append(amounts[0])
                        elif is_dr:
                            debits.append(amounts[0])

    # ── Text-only fallback when no tables were found ──────────────────────────
    if not tables_found:
        for line in full_text.splitlines():
            line = line.strip()
            if not line:
                continue
            is_upi = bool(_UPI_RE.search(line))
            is_emi = bool(_EMI_RE.search(line))
            is_cr  = bool(_CREDIT_RE.search(line))
            is_dr  = bool(_DEBIT_RE.search(line))
            amt    = _parse_amount(line)

            if is_upi:
                upi_count += 1
            if amt is None:
                continue
            if is_cr:
                credits.append(amt)
            elif is_dr:
                debits.append(amt)
                if is_emi and amt >= 500:
                    emi_amounts.append(amt)

    # ── Closing balance from text ─────────────────────────────────────────────
    if closing_balance is None:
        m = _BALANCE_RE.search(full_text)
        if m:
            try:
                closing_balance = float(m.group(1).replace(',', ''))
            except ValueError:
                pass

    # ── Derive summary fields ─────────────────────────────────────────────────
    # Assume statement covers ~3 months; scale to annual income
    months_covered = max(1, len(credits) // 3) if credits else 3

    # Filter outliers (top 5% of credits are likely transfers, not income)
    if credits:
        credits_sorted = sorted(credits)
        p95_idx = max(0, int(len(credits_sorted) * 0.95) - 1)
        income_credits = [c for c in credits_sorted if c <= credits_sorted[p95_idx]]
        monthly_credit = sum(income_credits) / max(months_covered, 1)
    else:
        monthly_credit = 0.0

    monthly_debit = sum(debits) / max(months_covered, 1) if debits else 0.0

    # Detect recurring EMI amounts (appear ≥2 times at roughly same value)
    emi_buckets: dict[int, int] = defaultdict(int)
    for amt in emi_amounts:
        bucket = int(round(amt / 500) * 500)
        emi_buckets[bucket] += 1
    recurring_emis = [bucket for bucket, count in emi_buckets.items() if count >= 2]
    monthly_emi_total = sum(recurring_emis)
    existing_loans   = len(recurring_emis)

    # Confidence heuristic
    confidence = 0.4
    if tables_found:
        confidence = 0.7
    if closing_balance is not None:
        confidence = 0.9

    return {
        'annual_income':    round(monthly_credit * 12, 2),
        'monthly_expenses': round(monthly_debit, 2),
        'savings_balance':  round(closing_balance, 2) if closing_balance else 0.0,
        'monthly_emi':      round(monthly_emi_total, 2),
        'existing_loans':   existing_loans,
        'upi_transactions': upi_count,
        'mobile_recharges': 0,   # not in bank statements; keep at 0
        'confidence':       confidence,
    }
