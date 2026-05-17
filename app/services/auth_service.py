from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_signed_token,
    decode_signed_token,
    hash_password,
    normalize_email,
    verify_password,
)
from app.models.organization.organization import Organization
from app.models.organization.organization_invite import OrganizationInvite
from app.models.employee.employee_model import Employee
from app.models.user.user_model import User
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

        return await self._create_access_token(user)

    async def login(self, email: str, password: str):
        user = await self._get_user_by_email(normalize_email(email))
        if not user or not user.is_active or not user.is_verified or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return await self._create_access_token(user)

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
        await self.db.refresh(user)

        return await self._create_access_token(user)

    async def _get_organization_by_email(self, email: str):
        result = await self.db.execute(select(Organization).where(Organization.email == email))
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
        employee = await self._get_employee_by_user_id(user.id) if user.role in {"employee", "hr_manager"} else None

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "organization_id": user.organization_id,
                "organization": self._serialize_organization(organization),
                "employee": self._serialize_employee(employee),
            },
        }

    async def _get_employee_by_user_id(self, user_id: UUID):
        result = await self.db.execute(select(Employee).where(Employee.user_id == user_id))
        return result.scalar_one_or_none()

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
