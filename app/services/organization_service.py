from http.client import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.organization import create_organization_with_user
from app.crud.user import get_user_by_email
from app.schemas.organization import OrganizationApply


async def apply_for_organization(db: AsyncSession, data:OrganizationApply):
    existing = await get_user_by_email(db, email=data.owner.email)
    if existing:
        raise HTTPException({"message": "email already exists"}, 409)

    return await create_organization_with_user(db, data)
