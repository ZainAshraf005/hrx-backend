import json

import httpx
import pytest

from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_send_email_uses_brevo_transactional_api():
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            status_code=201,
            json={"messageId": "<message-id@brevo>"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = EmailService(
            api_key="test-api-key",
            sender_email="notifications@example.com",
            sender_name="HRX Notifications",
            http_client=client,
        )

        await service.send_email(
            to="candidate@example.com",
            subject="Application update",
            html="<p>Your application was shortlisted.</p>",
        )

    assert captured_request is not None
    assert captured_request.method == "POST"
    assert str(captured_request.url) == "https://api.brevo.com/v3/smtp/email"
    assert captured_request.headers["api-key"] == "test-api-key"
    assert json.loads(captured_request.content) == {
        "sender": {
            "name": "HRX Notifications",
            "email": "notifications@example.com",
        },
        "to": [{"email": "candidate@example.com"}],
        "subject": "Application update",
        "htmlContent": "<p>Your application was shortlisted.</p>",
    }


@pytest.mark.asyncio
async def test_send_email_requires_brevo_api_key(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    service = EmailService(sender_email="notifications@example.com")

    with pytest.raises(
        RuntimeError,
        match="BREVO_API_KEY environment variable is required",
    ):
        await service.send_email(
            to="candidate@example.com",
            subject="Application update",
            html="<p>Update</p>",
        )


@pytest.mark.asyncio
async def test_send_email_propagates_brevo_api_errors():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=401,
            request=request,
            json={"code": "unauthorized", "message": "Key not found"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = EmailService(
            api_key="invalid-api-key",
            sender_email="notifications@example.com",
            http_client=client,
        )

        with pytest.raises(httpx.HTTPStatusError):
            await service.send_email(
                to="candidate@example.com",
                subject="Application update",
                html="<p>Update</p>",
            )
