import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from utils.pdf_parser import parse_bank_statement

router = APIRouter()

MAX_PDF_BYTES = 5 * 1024 * 1024  # 5 MB


class ParsedStatementResponse(BaseModel):
    annual_income: float
    monthly_expenses: float
    savings_balance: float
    monthly_emi: float
    existing_loans: int
    upi_transactions: int
    mobile_recharges: int
    confidence: float


@router.post("/parse-statement", response_model=ParsedStatementResponse)
async def parse_statement(file: UploadFile = File(...)):
    """
    Accept a bank statement PDF, parse financial fields, delete the file
    immediately — nothing is persisted to disk beyond this request.
    """
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    contents = await file.read()
    if len(contents) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 5 MB.")

    # Write to a temp file, parse, then delete immediately
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        result = parse_bank_statement(tmp_path)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse the PDF. Make sure it is a valid bank statement. ({exc})",
        )
    finally:
        # Privacy requirement: delete immediately after parsing
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return ParsedStatementResponse(**result)
