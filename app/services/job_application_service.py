from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import normalize_email
from app.models.enums import JobApplicationStatus, JobStatus, UserRole
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.user.user_model import User
from app.schemas.job_application_schema import (
    JobApplicationCreate,
    JobApplicationStatusUpdate,
    ResumeParseResponse,
)
from app.services.gemini_service import GeminiService
from app.services.resume_service import ResumeService


class JobApplicationService:
    def __init__(
        self,
        db: AsyncSession,
        resume_service: ResumeService,
        gemini_service: GeminiService,
    ):
        self.db = db
        self.resume_service = resume_service
        self.gemini_service = gemini_service

    async def parse_resume(self, job_id: UUID, resume: UploadFile) -> ResumeParseResponse:
        await self._get_public_job(job_id)
        resume_text = await self.resume_service.extract_text(resume)
        parsed_resume = await self.gemini_service.extract_resume_details(resume_text)

        return ResumeParseResponse(
            job_id=job_id,
            parsed_resume=parsed_resume,
        )

    async def create_application(self, job_id: UUID, data: JobApplicationCreate):
        job = await self._get_public_job(job_id)
        candidate_email = normalize_email(str(data.candidate_email))

        existing_application = await self._get_application_by_job_email(job_id, candidate_email)
        if existing_application:
            raise HTTPException(status_code=400, detail="Candidate has already applied for this job")

        application = JobApplication(
            job_id=job.id,
            organization_id=job.organization_id,
            candidate_name=data.candidate_name,
            candidate_email=candidate_email,
            candidate_phone=data.candidate_phone,
            candidate_location=data.candidate_location,
            linkedin_url=data.linkedin_url,
            portfolio_url=data.portfolio_url,
            summary=data.summary,
            parsed_resume=data.parsed_resume.model_dump(mode="json") if data.parsed_resume else None,
            cover_letter=data.cover_letter,
            status=JobApplicationStatus.SUBMITTED,
        )

        self.db.add(application)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(status_code=400, detail="Candidate has already applied for this job") from exc

        await self.db.refresh(application)
        return application

    async def get_applications_for_job(self, job_id: UUID, current_user: User):
        organization_id = self._require_org_admin_or_hr_manager_organization(current_user)
        await self._get_organization_job(job_id, organization_id)

        result = await self.db.execute(
            select(JobApplication)
            .where(JobApplication.job_id == job_id, JobApplication.organization_id == organization_id)
            .order_by(JobApplication.created_at.desc())
        )
        return result.scalars().all()

    async def get_application(self, application_id: UUID, current_user: User):
        organization_id = self._require_org_admin_or_hr_manager_organization(current_user)
        result = await self.db.execute(
            select(JobApplication).where(
                JobApplication.id == application_id,
                JobApplication.organization_id == organization_id,
            )
        )
        application = result.scalar_one_or_none()
        if not application:
            raise HTTPException(status_code=404, detail="Job application not found")
        return application

    async def update_application_status(
        self,
        application_id: UUID,
        data: JobApplicationStatusUpdate,
        current_user: User,
    ):
        application = await self.get_application(application_id, current_user)
        application.status = data.status

        await self.db.commit()
        await self.db.refresh(application)
        return application

    async def _get_public_job(self, job_id: UUID) -> Job:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.is_active.is_(True), Job.status == JobStatus.OPEN)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Open job not found")
        return job

    async def _get_organization_job(self, job_id: UUID, organization_id: UUID) -> Job:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def _get_application_by_job_email(self, job_id: UUID, candidate_email: str):
        result = await self.db.execute(
            select(JobApplication).where(
                JobApplication.job_id == job_id,
                JobApplication.candidate_email == candidate_email,
            )
        )
        return result.scalar_one_or_none()

    def _require_org_admin_or_hr_manager_organization(self, current_user: User) -> UUID:
        if current_user.role not in (UserRole.ORG_ADMIN, UserRole.HR_MANAGER) or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id
