from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserRole
from app.models.organization import Organization
from app.schemas.organization import OrganizationApply


async def get_org_by_email(db: AsyncSession, email: str):
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def create_organization_with_user(
        db: AsyncSession,
        data: OrganizationApply
):
    # create organization
    org = Organization(name=data.org_name, is_approved=True)

    db.add(org)
    await db.flush()

    # create owner user
    user = User(
        name=data.owner.name,
        email=data.owner.email,
        password=data.owner.password,
        role=UserRole.OWNER,
        organization_id=org.id
    )

    db.add(user)

    await db.refresh(user)

    return user


async def create_organization(db: AsyncSession, name: str, email: str) -> Organization:
    org = Organization(name=name)

    db.add(org)
    await db.commit()
    await db.refresh(org)

    return org


async def get_orgs(db: AsyncSession):
    result = await db.execute(select(Organization).order_by(Organization.email))
    return result.scalars().all()
