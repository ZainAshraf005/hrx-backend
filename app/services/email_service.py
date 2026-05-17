import os
import aiosmtplib
from email.message import EmailMessage


class EmailService:
    def __init__(self):
        self.email = os.getenv("GMAIL_EMAIL")
        self.password = os.getenv("GMAIL_APP_PASSWORD")

        self.smtp_host = "smtp.gmail.com"
        self.smtp_port = 587

    async def send_email(self, to: str, subject: str, html: str):
        message = EmailMessage()
        message["From"] = self.email
        message["To"] = to
        message["Subject"] = subject

        message.set_content("This email requires HTML support.")
        message.add_alternative(html, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            start_tls=True,
            username=self.email,
            password=self.password,
        )

    async def send_otp(self, email: str, otp: str):
        html = f"""
        <h2>OTP Verification</h2>
        <h1>{otp}</h1>
        <p>This OTP will expire in 10 minutes.</p>
        """
        await self.send_email(email, "Your OTP Code", html)

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
