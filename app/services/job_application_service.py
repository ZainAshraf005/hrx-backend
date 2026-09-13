import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, UploadFile
from sqlalchemy import case, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.core.security import normalize_email
from app.models.ai.agent_models import AIIndexTask, AIKnowledgeChunk
from app.models.enums import (
    AIKnowledgeSourceType,
    CandidateRankingStatus,
    JobApplicationStatus,
    UserRole,
)
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.organization.organization import Organization
from app.models.user.user_model import User
from app.schemas.job_application_schema import (
    JobApplicationCreate,
    JobApplicationStatusUpdate,
    ParsedResume,
    ResumeParseResponse,
)
from app.services.ai.indexing_service import enqueue_index_task
from app.services.email_service import EmailService
from app.services.resume_service import ResumeService
from app.services.xkiro_service import XkiroService

logger = logging.getLogger(__name__)


class JobApplicationService:
    def __init__(
        self,
        db: AsyncSession,
        resume_service: ResumeService,
        xkiro_service: XkiroService,
        email_service: EmailService | None = None,
    ):
        self.db = db
        self.resume_service = resume_service
        self.xkiro_service = xkiro_service
        self.email_service = email_service

    async def parse_resume(
        self, job_id: UUID, resume: UploadFile
    ) -> ResumeParseResponse:
        job = await self._get_public_job(job_id)
        return await self._parse_resume(job, resume)

    async def parse_resume_by_slug(
        self,
        organization_slug: str,
        job_slug: str,
        resume: UploadFile,
    ) -> ResumeParseResponse:
        job = await self._get_public_job_by_slug(organization_slug, job_slug)
        return await self._parse_resume(job, resume)

    async def _parse_resume(
        self,
        job: Job,
        resume: UploadFile,
    ) -> ResumeParseResponse:
        resume_text = await self.resume_service.extract_text(resume)
        parsed_resume = await self.xkiro_service.extract_resume_details(resume_text)
        parsed_resume = self.resume_service.normalize_parsed_resume(parsed_resume)

        return ResumeParseResponse(
            job_id=job.id,
            resume_text=resume_text,
            parsed_resume=parsed_resume,
        )

    async def create_application(self, job_id: UUID, data: JobApplicationCreate):
        job = await self._get_public_job(job_id)
        return await self._create_application(job, data)

    async def create_application_by_slug(
        self,
        organization_slug: str,
        job_slug: str,
        data: JobApplicationCreate,
    ):
        job = await self._get_public_job_by_slug(organization_slug, job_slug)
        return await self._create_application(job, data)

    async def _create_application(self, job: Job, data: JobApplicationCreate):
        candidate_email = normalize_email(str(data.candidate_email))
        parsed_resume = (
            self.resume_service.normalize_parsed_resume(data.parsed_resume)
            if data.parsed_resume
            else None
        )

        existing_application = await self._get_application_by_job_email(
            job.id,
            candidate_email,
        )
        if existing_application:
            raise HTTPException(
                status_code=400, detail="Candidate has already applied for this job"
            )

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
            resume_text=data.resume_text,
            parsed_resume=(
                parsed_resume.model_dump(mode="json") if parsed_resume else None
            ),
            cover_letter=data.cover_letter,
            status=JobApplicationStatus.SUBMITTED,
        )
        await self._rank_application(job, application)

        self.db.add(application)
        await self.db.flush()
        await enqueue_index_task(
            self.db,
            job.organization_id,
            AIKnowledgeSourceType.APPLICATION,
            application.id,
        )
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(
                status_code=400, detail="Candidate has already applied for this job"
            ) from exc

        await self.db.refresh(application)
        return application

    async def get_applications_for_job(
        self, job_id: UUID, current_user: User, sort: str = "rank"
    ):
        organization_id = self._require_org_admin_or_hr_manager_organization(
            current_user
        )
        await self._get_organization_job(job_id, organization_id)

        if sort not in ("rank", "created_at"):
            raise HTTPException(
                status_code=400, detail="sort must be either 'rank' or 'created_at'"
            )

        query = select(JobApplication).where(
            JobApplication.job_id == job_id,
            JobApplication.organization_id == organization_id,
        )
        if sort == "rank":
            query = query.order_by(
                case(
                    (
                        JobApplication.ranking_status
                        == CandidateRankingStatus.COMPLETED,
                        0,
                    ),
                    else_=1,
                ),
                JobApplication.ranking_score.desc().nullslast(),
                JobApplication.created_at.desc(),
            )
        else:
            query = query.order_by(JobApplication.created_at.desc())

        result = await self.db.execute(query)
        return result.scalars().all()

    async def rerank_applications_for_job(self, job_id: UUID):
        result = await self.db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return []

        return await self._rerank_applications(job)

    async def rerank_applications_for_job_as_manager(
        self,
        job_id: UUID,
        current_user: User,
    ):
        organization_id = self._require_org_admin_or_hr_manager_organization(
            current_user
        )
        job = await self._get_organization_job(job_id, organization_id)
        return await self._rerank_applications(job)

    async def _rerank_applications(self, job: Job):
        result = await self.db.execute(
            select(JobApplication)
            .where(JobApplication.job_id == job.id)
            .order_by(JobApplication.created_at.asc())
        )
        applications = result.scalars().all()
        for application in applications:
            await self._rank_application(job, application)
            await self.db.commit()
            await self.db.refresh(application)
        return applications

    async def get_application(self, application_id: UUID, current_user: User):
        organization_id = self._require_org_admin_or_hr_manager_organization(
            current_user
        )
        result = await self.db.execute(
            select(JobApplication)
            .options(
                selectinload(JobApplication.job).selectinload(Job.organization),
            )
            .where(
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
        previous_status = application.status
        should_notify = (
            self.email_service is not None
            and previous_status != data.status
            and data.status
            in (JobApplicationStatus.SHORTLISTED, JobApplicationStatus.REJECTED)
        )
        notification_context = (
            (
                application.candidate_email,
                application.candidate_name,
                application.job.title,
                application.job.organization.name,
            )
            if should_notify
            else None
        )
        application.status = data.status

        await self.db.commit()
        await self.db.refresh(application)

        if self.email_service and notification_context:
            candidate_email, candidate_name, job_title, organization_name = (
                notification_context
            )
            try:
                await self.email_service.send_job_application_status_email(
                    email=candidate_email,
                    candidate_name=candidate_name,
                    job_title=job_title,
                    organization_name=organization_name,
                    status=data.status,
                )
            # The decision is already committed; an SMTP outage must not make
            # the status update appear to have failed or invite duplicate action.
            except Exception:
                logger.exception("Failed to send job application status email")
        return application

    async def delete_application(
        self,
        application_id: UUID,
        current_user: User,
    ) -> None:
        application = await self.get_application(application_id, current_user)
        await self.db.execute(
            delete(AIKnowledgeChunk).where(
                AIKnowledgeChunk.source_type == AIKnowledgeSourceType.APPLICATION,
                AIKnowledgeChunk.source_id == application.id,
            )
        )
        await self.db.execute(
            delete(AIIndexTask).where(
                AIIndexTask.source_type == AIKnowledgeSourceType.APPLICATION,
                AIIndexTask.source_id == application.id,
            )
        )
        await self.db.delete(application)
        await self.db.commit()

    async def _rank_application(self, job: Job, application: JobApplication):
        application.ranking_status = CandidateRankingStatus.PENDING
        application.ranking_error = None

        if application.parsed_resume:
            try:
                parsed_resume = ParsedResume.model_validate(application.parsed_resume)
                application.parsed_resume = self.resume_service.normalize_parsed_resume(
                    parsed_resume
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                # Preserve legacy/malformed parsed data so ranking can still use
                # the original resume text instead of blocking the application.
                pass

        try:
            ranking = await self.xkiro_service.rank_candidate_for_job(job, application)
        except HTTPException as exc:
            application.ranking_score = None
            application.ranking_recommendation = None
            application.ranking_rationale = None
            application.ranking_strengths = None
            application.ranking_gaps = None
            application.ranking_status = CandidateRankingStatus.FAILED
            application.ranking_error = str(exc.detail)
            application.ranked_at = datetime.now(UTC)
            return
        # Ranking is a non-critical side effect. Persist any provider failure
        # on the application while keeping the submitted application usable.
        except Exception as exc:  # noqa: BLE001
            application.ranking_score = None
            application.ranking_recommendation = None
            application.ranking_rationale = None
            application.ranking_strengths = None
            application.ranking_gaps = None
            application.ranking_status = CandidateRankingStatus.FAILED
            application.ranking_error = str(exc)
            application.ranked_at = datetime.now(UTC)
            return

        application.ranking_score = ranking.score
        application.ranking_recommendation = ranking.recommendation
        application.ranking_rationale = ranking.rationale
        application.ranking_strengths = ranking.strengths
        application.ranking_gaps = ranking.gaps
        application.ranking_status = CandidateRankingStatus.COMPLETED
        application.ranking_error = None
        application.ranked_at = datetime.now(UTC)

    async def _get_public_job(self, job_id: UUID) -> Job:
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.is_active.is_(True))
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Active job not found")
        return job

    async def _get_public_job_by_slug(
        self,
        organization_slug: str,
        job_slug: str,
    ) -> Job:
        result = await self.db.execute(
            select(Job)
            .join(Organization)
            .where(
                Organization.slug == organization_slug,
                Job.slug == job_slug,
                Job.is_active.is_(True),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Active job not found")
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
        if (
            current_user.role not in (UserRole.ORG_ADMIN, UserRole.HR_MANAGER)
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id


async def rerank_job_applications_for_job(job_id: UUID):
    async with AsyncSessionLocal() as db:
        service = JobApplicationService(db, ResumeService(), XkiroService())
        await service.rerank_applications_for_job(job_id)
