from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.auth import require_roles
from app.dependencies.services import get_job_application_service, get_job_service
from app.models.user.user_model import User
from app.schemas.job_application_schema import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationStatusUpdate,
    ResumeParseResponse,
)
from app.schemas.job_schema import JobCreate, JobResponse, JobStatus, JobUpdate
from app.services.job_application_service import JobApplicationService
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


@router.get("/{job_id}/applications", response_model=List[JobApplicationResponse])
async def list_job_applications(
    job_id: UUID,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.get_applications_for_job(job_id, current_user)


@router.post("/{job_id}/applications/parse-resume", response_model=ResumeParseResponse)
async def parse_resume_for_job_application(
    job_id: UUID,
    resume: UploadFile = File(...),
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.parse_resume(job_id, resume)


@router.post("/{job_id}/applications", response_model=JobApplicationResponse)
async def create_job_application(
    job_id: UUID,
    payload: JobApplicationCreate,
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.create_application(job_id, payload)


@router.get("/applications/{application_id}", response_model=JobApplicationResponse)
async def get_job_application(
    application_id: UUID,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.get_application(application_id, current_user)


@router.put("/applications/{application_id}/status", response_model=JobApplicationResponse)
async def update_job_application_status(
    application_id: UUID,
    payload: JobApplicationStatusUpdate,
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.update_application_status(application_id, payload, current_user)


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
