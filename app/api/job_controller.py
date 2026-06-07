from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.dependencies.services import get_job_service
from app.models.user.user_model import User
from app.schemas.job_schema import JobCreate, JobResponse, JobStatus, JobUpdate
from app.services.job_service import JobService


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse)
async def create_job(
    payload: JobCreate,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobService = Depends(get_job_service),
):
    return await service.create_job(payload, current_user)


@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    status: JobStatus | None = None,
    service: JobService = Depends(get_job_service),
):
    return await service.get_jobs(status)


@router.get("/organization/{organization_id}", response_model=List[JobResponse])
async def list_jobs_by_organization(
    organization_id: UUID,
    status: JobStatus | None = None,
    service: JobService = Depends(get_job_service),
):
    return await service.get_jobs_by_organization(organization_id, status)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
):
    return await service.get_job(job_id)


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    payload: JobUpdate,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobService = Depends(get_job_service),
):
    return await service.update_job(job_id, payload, current_user)


@router.delete("/{job_id}", response_model=JobResponse)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobService = Depends(get_job_service),
):
    return await service.delete_job(job_id, current_user)
