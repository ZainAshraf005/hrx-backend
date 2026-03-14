from fastapi import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.organization import create_organization_with_user, get_org_by_id, mark_organization_approved
from app.crud.user import get_user_by_email
from app.models import Organization
from app.schemas.organization import OrganizationApply


async def organization_apply_service(db: AsyncSession, data: OrganizationApply) -> Organization:
    existing = await get_user_by_email(db, email=data.owner.email)
    if existing:
        raise HTTPException(409, "email already exists")

    return await create_organization_with_user(db, data)


async def organization_approve_service(db: AsyncSession, org_id: str):
    existing = await get_org_by_id(db, org_id)
    if not existing:
        raise HTTPException(404, "org not found")
    elif existing.is_approved:
        raise HTTPException(409, "org already approved")
    return await mark_organization_approved(db, existing.id)
