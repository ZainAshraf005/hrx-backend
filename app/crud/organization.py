from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


async def get_org_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(Organization).where(Organization.email == email)
    )
    return result.scalar_one_or_none()


async def create_organization(db: AsyncSession, name: str, email: str) -> Organization:
    org = Organization(name=name, email=email)

    db.add(org)
    await db.commit()
    await db.refresh(org)

    return org


async def get_orgs(db: AsyncSession):
    result = await db.execute(select(Organization).order_by(Organization.email))
    return result.scalars().all()
