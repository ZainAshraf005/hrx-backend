from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import FRONTEND_URL
from app.core.security import create_signed_token, normalize_email
from app.models import Organization
from app.models.enums import UserRole
from app.models.organization.organization_application import (
    OrganizationApplication,
    Status,
)
from app.models.organization.organization_invite import OrganizationInvite
from app.models.user.user_model import User
from app.schemas.organization_application import OrganizationApplicationCreate
from app.schemas.organization_schema import OrganizationCreate, OrganizationUpdate
from app.services.email_service import EmailService


class OrganizationService:
    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

    async def create_organization(self, data: OrganizationCreate) -> Organization:
        existing = await self.db.execute(select(Organization).where(Organization.email == data.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Organization already exists")
        # Logic to create an organization in the database
        organization = Organization(
            name=data.name,
            description=data.description,
            email=normalize_email(str(data.email)),
            website=data.website
        )

        self.db.add(organization)
        await self.db.commit()
        await self.db.refresh(organization)
        return organization

    async def get_all_organizations(self):
        # Logic to retrieve all organizations from the database
        result = await self.db.execute(select(Organization))
        return result.scalars().all()

    async def get_organization(self, organization_id: UUID):
        # Logic to retrieve an organization from the database
        result = await self.db.execute(select(Organization).where(Organization.id == organization_id))
        return result.scalar_one_or_none()

    async def update_organization(self, organization_id: UUID, data: OrganizationUpdate):
        org = await self.get_organization(organization_id)

        if not org:
            return None

        if data.name is not None and data.name != org.name:
            existing_name = await self.db.scalar(
                select(Organization.id).where(
                    Organization.name == data.name,
                    Organization.id != organization_id,
                )
            )
            if existing_name:
                raise HTTPException(
                    status_code=400,
                    detail="Organization name already exists",
                )
            org.name = data.name
        if data.email is not None:
            email = normalize_email(str(data.email))
            if email != org.email:
                existing_email = await self.db.scalar(
                    select(Organization.id).where(
                        Organization.email == email,
                        Organization.id != organization_id,
                    )
                )
                if existing_email:
                    raise HTTPException(
                        status_code=400,
                        detail="Organization email already exists",
                    )
                org.email = email
        if "description" in data.model_fields_set:
            org.description = data.description
        if "website" in data.model_fields_set:
            org.website = data.website
        if data.timezone is not None:
            org.timezone = data.timezone

        await self.db.commit()
        await self.db.refresh(org)

        return org

    async def get_own_organization(self, current_user: User) -> Organization:
        organization_id = self._require_org_admin_organization(current_user)
        organization = await self.get_organization(organization_id)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        return organization

    async def update_own_organization(
        self,
        data: OrganizationUpdate,
        current_user: User,
    ) -> Organization:
        organization_id = self._require_org_admin_organization(current_user)
        organization = await self.update_organization(organization_id, data)
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        return organization

    def _require_org_admin_organization(self, current_user: User) -> UUID:
        if current_user.role != UserRole.ORG_ADMIN or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id

    async def delete_organization(self, organization_id: UUID):
        # Logic to delete an organization from the database
        org = await self.get_organization(organization_id)

        if not org:
            return None
        await self.db.delete(org)
        await self.db.commit()
        return org

    async def get_all_applications(self):
        result = await self.db.execute(select(OrganizationApplication))
        return result.scalars().all()

    async def get_application(self, application_id: UUID):
        result = await self.db.execute(
            select(OrganizationApplication).where(OrganizationApplication.id == application_id))
        return result.scalar_one_or_none()

    async def create_application(self, data: OrganizationApplicationCreate):
        existing_user = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="User with this email already exists")
        existing = await self.db.execute(
            select(OrganizationApplication).where(OrganizationApplication.email == data.email))
        existing_organization = await self.db.execute(select(Organization).where(Organization.email == data.email))
        if existing.scalar_one_or_none() or existing_organization.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Application already exists")
        application = OrganizationApplication(
            org_name=data.org_name,
            email=normalize_email(str(data.email)),
            website=data.website,
            description=data.description,
        )
        self.db.add(application)
        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def update_application_status(self, application_id: UUID, status: Status, frontend_url: str = FRONTEND_URL):
        result = await self.db.execute(
            select(OrganizationApplication).where(OrganizationApplication.id == application_id))
        application: OrganizationApplication | None = result.scalar_one_or_none()

        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        if application.status != Status.PENDING:
            raise HTTPException(400, "Application already processed")
        application.status = status
        should_send_approval_email = False
        setup_token = None
        if application.status == Status.APPROVED:
            organization = Organization(
                email=normalize_email(application.email),
                name=application.org_name,
                description=application.description,
                website=application.website
            )
            self.db.add(organization)
            await self.db.flush()

            invite = OrganizationInvite(
                email=normalize_email(application.email),
                organization_id=organization.id,
                expires_at=datetime.now(UTC) + timedelta(days=7),
                role=UserRole.ORG_ADMIN,
            )
            self.db.add(invite)
            await self.db.flush()

            setup_token = create_signed_token(
                {
                    "purpose": "org_admin_setup",
                    "invite_id": str(invite.id),
                    "email": invite.email,
                    "organization_id": str(invite.organization_id),
                },
                timedelta(days=7),
            )
            should_send_approval_email = True
            await self.db.delete(application)

        await self.db.commit()
        if not should_send_approval_email:
            await self.db.refresh(application)
        if should_send_approval_email:
            assert setup_token is not None
            await self.email_service.send_approval_email(application.email, application.org_name, setup_token,
                                                         frontend_url)
        return application
