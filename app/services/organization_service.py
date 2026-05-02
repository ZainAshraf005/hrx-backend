from sqlalchemy import select
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Organization
from app.schemas.organization_schema import OrganizationCreate, OrganizationUpdate

class OrganizationService:
    def __init__(self, db:AsyncSession):
        self.db = db

    async def create_organization(self, data: OrganizationCreate )->Organization:
        # Logic to create an organization in the database
        organization = Organization(
            name=data.name,
            description=data.description,
            email=data.email,
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
            org.email = data.email
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