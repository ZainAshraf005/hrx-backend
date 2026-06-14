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
from app.models.employee.employee_model import Employee
from app.models.user.password_reset_otp import PasswordResetOtp
from app.models.user.user_model import User
from app.schemas.auth_schema import ProfileOrganizationUpdateRequest, ProfileUpdateRequest
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

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

        return {"message": "Password set successfully"}

    async def login(self, email: str, password: str):
        user = await self._get_user_by_email(normalize_email(email))
        if not user or not user.is_active or not user.is_verified or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return await self._create_access_token(user)

    async def request_forgot_password_otp(self, email: str):
        normalized_email = normalize_email(email)
        user = await self._get_user_by_email(normalized_email)
        self._validate_password_reset_user(user)

        active_resets = await self.db.execute(
            select(PasswordResetOtp).where(
                PasswordResetOtp.user_id == user.id,
                PasswordResetOtp.email == normalized_email,
                PasswordResetOtp.is_used.is_(False),
            )
        )
        for reset in active_resets.scalars().all():
            reset.is_used = True

        otp = generate_otp()
        reset = PasswordResetOtp(
            user_id=user.id,
            email=normalized_email,
            otp_hash=hash_otp(otp),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        self.db.add(reset)
        await self.db.commit()

        await self.email_service.send_password_reset_otp(normalized_email, otp)
        return {"message": "OTP sent"}

    async def reset_forgot_password(self, email: str, token: str, password: str):
        normalized_email = normalize_email(email)
        user = await self._get_user_by_email(normalized_email)
        self._validate_password_reset_user(user)

        reset = await self._get_latest_active_password_reset(normalized_email)
        if (
            not reset
            or reset.user_id != user.id
            or self._is_expired(reset.expires_at)
            or not verify_otp(token, reset.otp_hash)
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

        user.password_hash = hash_password(password)
        reset.is_used = True
        await self.db.commit()

        return {"message": "Password reset successfully"}

    async def set_employee_password(self, setup_token: str, password: str):
        payload = decode_signed_token(setup_token)
        if not payload or payload.get("purpose") != "employee_setup":
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        try:
            user_id = UUID(payload["user_id"])
            employee_id = UUID(payload["employee_id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        result = await self.db.execute(
            select(User)
            .options(selectinload(User.employee), selectinload(User.organization))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if (
            not user
            or not user.is_active
            or user.is_verified
            or user.email != payload.get("email")
            or str(user.organization_id) != payload.get("organization_id")
            or not user.employee
            or user.employee.id != employee_id
            or not user.employee.is_active
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired setup token")

        user.password_hash = hash_password(password)
        user.is_verified = True

        await self.db.commit()

        return {"message": "Password set successfully"}

    async def get_profile(self, current_user: User):
        user = await self._get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return self._serialize_user(user)

    async def update_profile(self, current_user: User, data: ProfileUpdateRequest):
        user = await self._get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "superadmin":
            raise HTTPException(status_code=403, detail="Profile update is not allowed for superadmin")

        if data.email is not None:
            email = normalize_email(str(data.email))
            if email != user.email:
                existing_user = await self._get_user_by_email(email)
                if existing_user and existing_user.id != user.id:
                    raise HTTPException(status_code=400, detail="Email already exists")
                user.email = email

        if data.organization is not None:
            if user.role != "org_admin":
                raise HTTPException(status_code=403, detail="Organization update is only allowed for org admin")
            if not user.organization:
                raise HTTPException(status_code=400, detail="Organization not found")
            await self._apply_organization_profile_update(user.organization, data.organization)

        employee_fields = {"first_name", "last_name", "phone"}
        if employee_fields.intersection(data.model_fields_set):
            if user.role not in {"employee", "hr_manager"}:
                raise HTTPException(status_code=403, detail="Employee profile update is only allowed for employees")
            if not user.employee:
                raise HTTPException(status_code=400, detail="Employee profile not found")
            if data.first_name is not None:
                user.employee.first_name = data.first_name
            if data.last_name is not None:
                user.employee.last_name = data.last_name
            if "phone" in data.model_fields_set:
                user.employee.phone = data.phone

        await self.db.commit()
        return await self.get_profile(user)

    async def _apply_organization_profile_update(
        self,
        organization: Organization,
        data: ProfileOrganizationUpdateRequest,
    ):
        if data.name is not None and data.name != organization.name:
            existing_organization = await self._get_organization_by_name(data.name)
            if existing_organization and existing_organization.id != organization.id:
                raise HTTPException(status_code=400, detail="Organization name already exists")
            organization.name = data.name

        if data.email is not None:
            email = normalize_email(str(data.email))
            if email != organization.email:
                existing_organization = await self._get_organization_by_email(email)
                if existing_organization and existing_organization.id != organization.id:
                    raise HTTPException(status_code=400, detail="Organization email already exists")
                organization.email = email

        if "website" in data.model_fields_set:
            organization.website = data.website
        if "description" in data.model_fields_set:
            organization.description = data.description

    async def _get_organization_by_email(self, email: str):
        result = await self.db.execute(select(Organization).where(Organization.email == email))
        return result.scalar_one_or_none()

    async def _get_organization_by_name(self, name: str):
        result = await self.db.execute(select(Organization).where(Organization.name == name))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: UUID):
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.organization), selectinload(User.employee))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str):
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.organization), selectinload(User.employee))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def _organization_has_admin(self, organization_id):
        result = await self.db.execute(
            select(User).where(User.organization_id == organization_id, User.role == "org_admin")
        )
        return result.scalar_one_or_none() is not None

    async def _get_latest_active_password_reset(self, email: str):
        result = await self.db.execute(
            select(PasswordResetOtp)
            .where(PasswordResetOtp.email == email, PasswordResetOtp.is_used.is_(False))
            .order_by(PasswordResetOtp.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    def _validate_password_reset_user(self, user: User | None):
        if not user or not user.is_active or not user.is_verified or not user.password_hash:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "superadmin":
            raise HTTPException(status_code=403, detail="Password reset is not allowed for superadmin")

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

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": self._serialize_user(user),
        }

    def _serialize_user(self, user: User):
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "organization_id": user.organization_id,
            "organization": self._serialize_organization(user.organization),
            "employee": self._serialize_employee(user.employee),
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

    def _serialize_employee(self, employee: Employee | None):
        if not employee:
            return None

        return {
            "id": employee.id,
            "organization_id": employee.organization_id,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "phone": employee.phone,
            "designation": employee.designation,
            "is_active": employee.is_active,
        }

    def _is_expired(self, value: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value <= datetime.now(timezone.utc)
