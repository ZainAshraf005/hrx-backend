from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.organization import get_orgs
from app.db.session import get_db
from app.schemas.organization import OrganizationApply
from app.services.organization_service import apply_for_organization

router = APIRouter(prefix="/organizations")


@router.post("/apply")
async def apply_organization(
        data: OrganizationApply,
        db: AsyncSession = Depends(get_db)
):
    org = await apply_for_organization(db, data)

    return {
        "message": "Application Submitted",
        "success": True,
        "organization_id": org.id
    }


@router.get("/organizations")
async def get_organizations(db: AsyncSession = Depends(get_db)):
    organizations = await get_orgs(db)
    return {
        "message": "Organization List",
        "success": True,
        "organizations": organizations
    }
