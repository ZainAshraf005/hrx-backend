from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from app.models.organization import Organization
from app.schemas.organization import OrganizationApply
from app.core.security import hash_password


async def get_org_by_id(db: AsyncSession, org_id: str) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    return result.scalar_one_or_none()


async def create_organization_with_user(
        db: AsyncSession,
        data: OrganizationApply
):
    # create organization
    org = Organization(name=data.org_name)

    db.add(org)
    await db.flush()

    # create owner user
    user = User(
        name=data.owner.name,
        email=data.owner.email,
        password=hash_password(data.owner.password),
        role=UserRole.OWNER,
        organization_id=org.id
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


async def create_organization(db: AsyncSession, name: str, email: str) -> Organization:
    org = Organization(name=name)

    db.add(org)
    await db.commit()
    await db.refresh(org)

    return org


async def get_orgs(db: AsyncSession):
    result = await db.execute(select(Organization).order_by(Organization.name))
    return result.scalars().all()


async def mark_organization_approved(db: AsyncSession, org_id: str):
    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalars().first()

    org.is_approved = True
    await db.commit()
    await db.refresh(org)  # refresh to get updated values

    return org
