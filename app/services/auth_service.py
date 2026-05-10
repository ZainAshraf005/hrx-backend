from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_signed_token,
    decode_signed_token,
    generate_otp,
    hash_otp,
    hash_password,
    normalize_email,
    verify_otp,
    verify_password,
)
from app.models.organization.organization import Organization
from app.models.organization.organization_invite import OrganizationInvite
from app.models.user.user_model import User
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

    async def request_org_admin_otp(self, email: str):
        normalized_email = normalize_email(email)
        organization = await self._get_organization_by_email(normalized_email)
        if not organization:
            raise HTTPException(status_code=404, detail="No approved organization found for this email")

        if await self._organization_has_admin(organization.id):
            raise HTTPException(status_code=400, detail="Organization admin already exists")

        active_invites = await self.db.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.email == normalized_email,
                OrganizationInvite.organization_id == organization.id,
                OrganizationInvite.is_used.is_(False),
            )
        )
        for invite in active_invites.scalars().all():
            invite.is_used = True

        otp = generate_otp()
        invite = OrganizationInvite(
            email=normalized_email,
            organization_id=organization.id,
            otp_hash=hash_otp(otp),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            role="org_admin",
        )
        self.db.add(invite)
        await self.db.commit()

        await self.email_service.send_otp(normalized_email, otp)
        return {"message": "OTP sent"}

    async def verify_org_admin_otp(self, email: str, otp: str):
        normalized_email = normalize_email(email)
        invite = await self._get_latest_active_invite(normalized_email)
        if not invite or self._is_expired(invite.expires_at) or not verify_otp(otp, invite.otp_hash):
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        setup_token = create_signed_token(
            {
                "purpose": "org_admin_setup",
                "invite_id": str(invite.id),
                "email": normalized_email,
                "organization_id": str(invite.organization_id),
            },
            timedelta(minutes=15),
        )
        return {"setup_token": setup_token}

    async def set_org_admin_password(self, setup_token: str, password: str):
        payload = decode_signed_token(setup_token)
        if not payload or payload.get("purpose") != "org_admin_setup":
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        try:
            invite_id = UUID(payload["invite_id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        invite = await self.db.get(OrganizationInvite, invite_id)
        if (
            not invite
            or invite.is_used
            or self._is_expired(invite.expires_at)
            or invite.email != payload.get("email")
            or str(invite.organization_id) != payload.get("organization_id")
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        if await self._organization_has_admin(invite.organization_id):
            raise HTTPException(status_code=400, detail="Organization admin already exists")

        existing_user = await self._get_user_by_email(invite.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

        user = User(
            email=invite.email,
            password_hash=hash_password(password),
            organization_id=invite.organization_id,
            role="org_admin",
            is_active=True,
            is_verified=True,
        )
        invite.is_used = True
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return await self._create_access_token(user)

    async def login(self, email: str, password: str):
        user = await self._get_user_by_email(normalize_email(email))
        if not user or not user.is_active or not user.is_verified or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return await self._create_access_token(user)

    async def _get_organization_by_email(self, email: str):
        result = await self.db.execute(select(Organization).where(Organization.email == email))
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str):
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.organization))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def _organization_has_admin(self, organization_id):
        result = await self.db.execute(
            select(User).where(User.organization_id == organization_id, User.role == "org_admin")
        )
        return result.scalar_one_or_none() is not None

    async def _get_latest_active_invite(self, email: str):
        result = await self.db.execute(
            select(OrganizationInvite)
            .where(OrganizationInvite.email == email, OrganizationInvite.is_used.is_(False))
            .order_by(OrganizationInvite.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def _create_access_token(self, user: User):
        token = create_signed_token(
            {
                "purpose": "access",
                "sub": str(user.id),
                "email": user.email,
                "organization_id": str(user.organization_id) if user.organization_id else None,
                "role": user.role,
            },
            timedelta(hours=12),
        )
        organization = await self.db.get(Organization, user.organization_id) if user.organization_id else None

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "organization_id": user.organization_id,
                "organization": self._serialize_organization(organization),
            },
        }

    def _serialize_organization(self, organization: Organization | None):
        if not organization:
            return None

        return {
            "id": organization.id,
            "name": organization.name,
            "email": organization.email,
            "website": organization.website,
            "description": organization.description,
        }

    def _is_expired(self, value: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc)
