from fastapi import APIRouter, Request
from app.core.frontend_url import get_frontend_url_from_request
from app.services.email_service import EmailService

router = APIRouter(prefix="/email", tags=["email"])
email_service = EmailService()


@router.get("/{sending_email}/test-email")
async def test_email(sending_email: str, request: Request):
    frontend_url = get_frontend_url_from_request(request)
    await email_service.send_approval_email(sending_email, "Lala Company", "test-token", frontend_url)
    return {"message": "sent"}
