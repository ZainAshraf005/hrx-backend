from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies.services import get_job_application_service, get_job_service
from app.schemas.job_application_schema import (
    JobApplicationCreate,
    PublicJobApplicationResponse,
    PublicResumeParseResponse,
)
from app.schemas.job_schema import PublicJobResponse
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService

router = APIRouter(prefix="/public", tags=["public jobs"])


@router.get("/jobs", response_model=list[PublicJobResponse])
async def list_public_jobs(
    service: JobService = Depends(get_job_service),
):
    return await service.get_public_jobs()


@router.get(
    "/organizations/{organization_slug}/jobs",
    response_model=list[PublicJobResponse],
)
async def list_public_organization_jobs(
    organization_slug: str,
    service: JobService = Depends(get_job_service),
):
    return await service.get_public_jobs(organization_slug)


@router.get(
    "/organizations/{organization_slug}/jobs/{job_slug}",
    response_model=PublicJobResponse,
)
async def get_public_job(
    organization_slug: str,
    job_slug: str,
    service: JobService = Depends(get_job_service),
):
    return await service.get_public_job_by_slug(organization_slug, job_slug)


@router.post(
    "/organizations/{organization_slug}/jobs/{job_slug}/applications/parse-resume",
    response_model=PublicResumeParseResponse,
)
async def parse_public_job_application_resume(
    organization_slug: str,
    job_slug: str,
    resume: UploadFile = File(...),
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.parse_resume_by_slug(
        organization_slug,
        job_slug,
        resume,
    )


@router.post(
    "/organizations/{organization_slug}/jobs/{job_slug}/applications",
    response_model=PublicJobApplicationResponse,
)
async def create_public_job_application(
    organization_slug: str,
    job_slug: str,
    payload: JobApplicationCreate,
    service: JobApplicationService = Depends(get_job_application_service),
):
    return await service.create_application_by_slug(
        organization_slug,
        job_slug,
        payload,
    )
