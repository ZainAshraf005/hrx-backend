from fastapi import APIRouter
from app.services.email_service import EmailService

router = APIRouter(prefix="/email", tags=["email"])
email_service = EmailService()


@router.get("/{sending_email}/test-email")
async def test_email(sending_email: str):
    await email_service.send_approval_email(sending_email, "Lala Company")
    return {"message": "sent"}
