from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import FRONTEND_URL
from app.models import Organization
from app.models.organization.organization_invite import OrganizationInvite
from app.models.user.user_model import User
from app.schemas.organization_application import OrganizationApplicationCreate
from app.schemas.organization_schema import OrganizationCreate, OrganizationUpdate
from app.models.organization.organization_application import OrganizationApplication, Status
from app.services.email_service import EmailService
from app.core.security import create_signed_token, normalize_email


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
        # Logic to update an organization's details in the database
        org = await self.get_organization(organization_id)

        if not org:
            return None

        if data.name is not None:
            org.name = data.name
        if data.email is not None:
            org.email = normalize_email(str(data.email))
        if data.description is not None:
            org.description = data.description
        if data.website is not None:
            org.website = data.website

        await self.db.commit()
        await self.db.refresh(org)

        return org

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

    async def update_application_status(self, application_id: UUID, status: Status):
        result = await self.db.execute(
            select(OrganizationApplication).where(OrganizationApplication.id == application_id))
        application: Optional[OrganizationApplication] = result.scalar_one_or_none()

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
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                role="org_admin",
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
            await self.email_service.send_approval_email(application.email, application.org_name, setup_token,
                                                         FRONTEND_URL)
        return application
