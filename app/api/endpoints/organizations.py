from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.organization import get_orgs
from app.db.session import get_db
from app.schemas.organization import OrganizationApply
from app.services.organization_service import organization_apply_service, organization_approve_service

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("/apply")
async def apply_organization(
        data: OrganizationApply,
        db: AsyncSession = Depends(get_db)
):
    org = await organization_apply_service(db, data)

    return {
        "message": "Application Submitted",
        "success": True,
        "organization_id": org.id
    }


@router.put("/mark-approved")
async def mark_organization_approved(org_id: str, db: AsyncSession = Depends(get_db)):
    org = await organization_approve_service(db, org_id)
    return {
        "message": "Application Approved",
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
