from http.client import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.organization import get_org_by_email, create_organization
from app.models.organization import Organization


async def apply_for_organization(db: AsyncSession, name: str, email: str) -> Organization:
    existing = await get_org_by_email(db, email)
    if existing:
        raise HTTPException({"message": "email already exists"}, 409)

    return await create_organization(db, name, email)
