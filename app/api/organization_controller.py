from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from app.dependencies.services import get_organization_service
from app.services.organization_service import OrganizationService
from app.schemas.organization_schema import OrganizationResponse, OrganizationCreate, OrganizationUpdate

router = APIRouter(prefix="/organizations", tags=["organizations"])

@router.get("/", response_model=List[OrganizationResponse])
async def list_organizations(service: OrganizationService = Depends(get_organization_service)):
    return await service.get_all_organizations()

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(organization_id: UUID, service: OrganizationService = Depends(get_organization_service)):
    org = await service.get_organization(organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org
  
@router.post("/", response_model=OrganizationResponse)
async def create_organization(organization: OrganizationCreate, service: OrganizationService = Depends(get_organization_service)):
    return await service.create_organization(organization)

@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(organization_id: UUID, organization: OrganizationUpdate, service: OrganizationService = Depends(get_organization_service)):
    updated_org = await service.update_organization(organization_id, organization)
    if not updated_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return updated_org

@router.delete("/{organization_id}", response_model=OrganizationResponse)
async def delete_organization(organization_id: UUID, service: OrganizationService = Depends(get_organization_service)):
    deleted_org = await service.delete_organization(organization_id)
    if not deleted_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return deleted_org
  
