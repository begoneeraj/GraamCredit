from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db
from models.schemas import ContactRequest, ContactResponse
from models.tables import ContactMessage
from utils.email import send_contact_notification

router = APIRouter()


@router.post("/contact", response_model=ContactResponse)
def submit_contact(req: ContactRequest, db: Session = Depends(get_db)):
    record = ContactMessage(
        name=req.name,
        email=req.email,
        subject=req.subject,
        message=req.message,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()

    send_contact_notification(
        name=req.name,
        email=req.email,
        subject=req.subject,
        message=req.message,
    )

    return ContactResponse(
        success=True,
        message="Your message has been received. We'll respond within 24 hours.",
    )
