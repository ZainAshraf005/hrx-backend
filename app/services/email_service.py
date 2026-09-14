import os
from html import escape
from typing import Any

import httpx

from app.models.enums import JobApplicationStatus


class EmailService:
    api_url = "https://api.brevo.com/v3/smtp/email"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        sender_email: str | None = None,
        sender_name: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.api_key = api_key or os.getenv("BREVO_API_KEY")
        # GMAIL_EMAIL remains a temporary fallback so existing deployments can
        # switch transports before renaming their sender configuration.
        self.sender_email = (
            sender_email
            or os.getenv("BREVO_SENDER_EMAIL")
            or os.getenv("GMAIL_EMAIL")
        )
        self.sender_name = sender_name or os.getenv("BREVO_SENDER_NAME", "HRX")
        self.http_client = http_client

    def _payload(self, to: str, subject: str, html: str) -> dict[str, Any]:
        if not self.sender_email:
            raise RuntimeError("BREVO_SENDER_EMAIL environment variable is required")

        return {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email,
            },
            "to": [{"email": to}],
            "subject": subject,
            "htmlContent": html,
        }

    async def send_email(self, to: str, subject: str, html: str) -> None:
        if not self.api_key:
            raise RuntimeError("BREVO_API_KEY environment variable is required")

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json",
        }
        payload = self._payload(to, subject, html)

        if self.http_client is not None:
            response = await self.http_client.post(
                self.api_url,
                headers=headers,
                json=payload,
            )
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                )

        response.raise_for_status()

    async def send_otp(self, email: str, otp: str):
        html = f"""
        <h2>OTP Verification</h2>
        <h1>{otp}</h1>
        <p>This OTP will expire in 10 minutes.</p>
        """
        await self.send_email(email, "Your OTP Code", html)

    async def send_password_reset_otp(self, email: str, otp: str):
        html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>Password Reset</h2>

            <p>Use the OTP below to reset your password.</p>

            <h1>{otp}</h1>

            <p>This OTP will expire in 10 minutes.</p>

            <hr/>

            <p style="color: gray; font-size: 12px;">
                If you didn't request this, you can ignore this email.
            </p>
        </div>
        """
        await self.send_email(email, "Reset your password", html)

    async def send_approval_email(self, email: str, org_name: str, setup_token: str, frontend_url: str):
        setup_url = f"{frontend_url.rstrip('/')}/org-admin/set-password?token={setup_token}"
        html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>Organization Approved</h2>

            <p>Good news — your organization <b>{org_name}</b> has been approved.</p>

            <p>Use the link below to set your admin password.</p>

            <p><a href="{setup_url}">Set your password</a></p>

            <p>This link will expire in 7 days.</p>

            <hr/>

            <p style="color: gray; font-size: 12px;">
                If you didn’t request this, you can ignore this email.
            </p>
        </div>
        """

        await self.send_email(
            to=email,
            subject="Your Organization Has Been Approved",
            html=html
        )

    async def send_employee_invite(self, email: str, first_name: str, setup_token: str, frontend_url: str):
        setup_url = f"{frontend_url.rstrip('/')}/employee/set-password?token={setup_token}"
        html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>Employee Account Setup</h2>

            <p>Hello {first_name},</p>
            <p>Your employee account has been created. Use the link below to set your password.</p>

            <p><a href="{setup_url}">Set your password</a></p>

            <p>This link will expire in 24 hours.</p>
        </div>
        """

        await self.send_email(
            to=email,
            subject="Set up your employee account",
            html=html
        )

    async def send_leave_status_email(
        self,
        email: str,
        first_name: str,
        leave_type: str,
        start_date,
        end_date,
        status: str,
        reason: str | None = None,
    ):
        reason_html = (
            f"<p><b>Comment:</b> {escape(reason)}</p>" if reason else ""
        )
        html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h2>Leave Request Updated</h2>
            <p>Hello {escape(first_name)},</p>
            <p>
                Your {escape(leave_type)} leave request from
                <b>{start_date.isoformat()}</b> to <b>{end_date.isoformat()}</b>
                is now <b>{escape(status)}</b>.
            </p>
            {reason_html}
        </div>
        """
        await self.send_email(
            to=email,
            subject=f"Leave request {status}",
            html=html,
        )

    async def send_job_application_status_email(
        self,
        *,
        email: str,
        candidate_name: str,
        job_title: str,
        organization_name: str,
        status: JobApplicationStatus,
    ):
        safe_name = escape(candidate_name)
        safe_job_title = escape(job_title)
        safe_organization_name = escape(organization_name)
        subject_job_title = " ".join(job_title.splitlines())

        if status == JobApplicationStatus.SHORTLISTED:
            subject = f"An update on your {subject_job_title} application"
            update_html = f"""
            <p>
                We’re pleased to let you know that your application has been
                shortlisted. The {safe_organization_name} team may contact you
                with the next steps.
            </p>
            """
        elif status == JobApplicationStatus.REJECTED:
            subject = f"An update on your {subject_job_title} application"
            update_html = """
            <p>
                After careful consideration, we won’t be moving forward with
                your application at this time.
            </p>
            <p>
                We appreciate the time and effort you put into applying and
                wish you every success in your job search.
            </p>
            """
        else:
            return

        html = f"""
        <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <p>Hello {safe_name},</p>
            <p>
                Thank you for your interest in the <b>{safe_job_title}</b>
                position at <b>{safe_organization_name}</b>.
            </p>
            {update_html}
            <p>Kind regards,<br/>{safe_organization_name}</p>
        </div>
        """
        await self.send_email(to=email, subject=subject, html=html)
