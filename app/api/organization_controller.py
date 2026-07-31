from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.frontend_url import get_frontend_url_from_request
from app.dependencies.auth import require_roles, require_superadmin_or_own_organization
from app.dependencies.services import get_organization_service
from app.models.organization.organization_application import Status
from app.models.user.user_model import User
from app.schemas.organization_application import (
    OrganizationApplicationCreate,
    OrganizationApplicationResponse,
)
from app.schemas.organization_schema import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/applications", response_model=list[OrganizationApplicationResponse])
async def list_applications(
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    return await service.get_all_applications()


@router.post("/applications", response_model=OrganizationApplicationResponse)
async def create_application(application: OrganizationApplicationCreate,
                             service: OrganizationService = Depends(get_organization_service)):
    return await service.create_application(application)


@router.get("/", response_model=list[OrganizationResponse])
async def list_organizations(
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    return await service.get_all_organizations()


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
        organization_id: UUID,
        current_user: User = Depends(require_superadmin_or_own_organization),
        service: OrganizationService = Depends(get_organization_service)):
    org = await service.get_organization(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post("/", response_model=OrganizationResponse)
async def create_organization(organization: OrganizationCreate,
                              current_user: User = Depends(require_roles("superadmin")),
                              service: OrganizationService = Depends(get_organization_service)):
    return await service.create_organization(organization)


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(organization_id: UUID, organization: OrganizationUpdate,
                              current_user: User = Depends(require_superadmin_or_own_organization),
                              service: OrganizationService = Depends(get_organization_service)):
    updated_org = await service.update_organization(organization_id, organization)
    if not updated_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return updated_org


@router.delete("/{organization_id}", response_model=OrganizationResponse)
async def delete_organization(
        organization_id: UUID,
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    deleted_org = await service.delete_organization(organization_id)
    if not deleted_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return deleted_org


@router.get("/applications/{application_id}", response_model=OrganizationApplicationResponse)
async def get_application(
        application_id: UUID,
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    application = await service.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.put("/applications/{application_id}/approve", response_model=OrganizationApplicationResponse)
async def approve_application(
        application_id: UUID,
        request: Request,
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    frontend_url = get_frontend_url_from_request(request)
    return await service.update_application_status(application_id, Status.APPROVED, frontend_url)


@router.put("/applications/{application_id}/discard", response_model=OrganizationApplicationResponse)
async def discard_application(
        application_id: UUID,
        current_user: User = Depends(require_roles("superadmin")),
        service: OrganizationService = Depends(get_organization_service)):
    return await service.update_application_status(application_id, Status.DENIED)
