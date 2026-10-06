from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.slug import allocate_unique_slug
from app.models.ai.agent_models import AIIndexTask, AIKnowledgeChunk
from app.models.enums import AIKnowledgeSourceType, UserRole
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.user.user_model import User
from app.schemas.job_schema import JobCreate, JobUpdate
from app.services.ai.indexing_service import enqueue_index_task


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, data: JobCreate, current_user: User):
        organization_id = self._require_org_admin_organization(current_user)
        self._validate_salary_range(data.salary_min, data.salary_max)

        job = Job(
            organization_id=organization_id,
            title=data.title,
            slug=await allocate_unique_slug(
                self.db,
                Job,
                data.title,
                Job.organization_id == organization_id,
            ),
            description=data.description,
            department=data.department,
            location=data.location,
            employment_type=data.employment_type,
            workplace_type=data.workplace_type,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            salary_currency=data.salary_currency,
            salary_period=data.salary_period,
            experience_level=data.experience_level,
            requirements=data.requirements,
            responsibilities=data.responsibilities,
            benefits=data.benefits,
            is_active=data.is_active,
        )
        self._apply_active_timestamps(job, data.is_active)

        self.db.add(job)
        await self.db.flush()
        await enqueue_index_task(
            self.db,
            job.organization_id,
            AIKnowledgeSourceType.JOB,
            job.id,
        )
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_jobs(
        self,
        current_user: User,
        is_active: bool | None = None,
    ):
        organization_id = self._require_org_admin_organization(current_user)
        query = self._organization_jobs_query(organization_id, is_active)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_jobs_by_organization(
        self,
        organization_id: UUID,
        current_user: User,
        is_active: bool | None = None,
    ):
        current_organization_id = self._require_org_admin_organization(current_user)
        if organization_id != current_organization_id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        query = self._organization_jobs_query(organization_id, is_active)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_job(self, job_id: UUID, current_user: User):
        return await self.get_organization_job(job_id, current_user)

    async def get_public_jobs(self, organization_slug: str | None = None):
        query = self._public_jobs_query().options(selectinload(Job.organization))
        if organization_slug is not None:
            query = query.where(Job.organization.has(slug=organization_slug))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_public_job_by_slug(
        self,
        organization_slug: str,
        job_slug: str,
    ):
        result = await self.db.execute(
            self._public_jobs_query()
            .options(selectinload(Job.organization))
            .where(
                Job.slug == job_slug,
                Job.organization.has(slug=organization_slug),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Active job not found")
        return job

    async def get_organization_job(self, job_id: UUID, current_user: User):
        organization_id = self._require_org_admin_organization(current_user)
        result = await self.db.execute(
            select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def update_job(self, job_id: UUID, data: JobUpdate, current_user: User):
        job = await self.get_organization_job(job_id, current_user)
        salary_min = (
            data.salary_min if "salary_min" in data.model_fields_set else job.salary_min
        )
        salary_max = (
            data.salary_max if "salary_max" in data.model_fields_set else job.salary_max
        )
        self._validate_salary_range(salary_min, salary_max)
        was_active = job.is_active

        for field in (
            "title",
            "description",
            "department",
            "location",
            "employment_type",
            "workplace_type",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_period",
            "experience_level",
            "requirements",
            "responsibilities",
            "benefits",
            "is_active",
        ):
            if field in data.model_fields_set:
                setattr(job, field, getattr(data, field))

        if "is_active" in data.model_fields_set and job.is_active != was_active:
            self._apply_active_timestamps(job, job.is_active)

        await enqueue_index_task(
            self.db,
            job.organization_id,
            AIKnowledgeSourceType.JOB,
            job.id,
        )
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def delete_job(self, job_id: UUID, current_user: User):
        job = await self.get_organization_job(job_id, current_user)
        await self._delete_job_index_data(job.id)
        await self.db.delete(job)
        await self.db.commit()

    def _public_jobs_query(self):
        return (
            select(Job).where(Job.is_active.is_(True)).order_by(Job.created_at.desc())
        )

    def _organization_jobs_query(
        self,
        organization_id: UUID,
        is_active: bool | None,
    ):
        query = select(Job).where(Job.organization_id == organization_id)
        if is_active is not None:
            query = query.where(Job.is_active.is_(is_active))
        return query.order_by(Job.created_at.desc())

    def _apply_active_timestamps(self, job: Job, is_active: bool):
        now = datetime.now(UTC)
        if is_active and job.published_at is None:
            job.published_at = now
        if is_active:
            job.closed_at = None
        elif job.published_at is not None and job.closed_at is None:
            job.closed_at = now

    async def _delete_job_index_data(self, job_id: UUID) -> None:
        application_ids = select(JobApplication.id).where(
            JobApplication.job_id == job_id
        )
        source_filter = or_(
            and_(
                AIKnowledgeChunk.source_type == AIKnowledgeSourceType.JOB,
                AIKnowledgeChunk.source_id == job_id,
            ),
            and_(
                AIKnowledgeChunk.source_type == AIKnowledgeSourceType.APPLICATION,
                AIKnowledgeChunk.source_id.in_(application_ids),
            ),
        )
        await self.db.execute(delete(AIKnowledgeChunk).where(source_filter))

        task_source_filter = or_(
            and_(
                AIIndexTask.source_type == AIKnowledgeSourceType.JOB,
                AIIndexTask.source_id == job_id,
            ),
            and_(
                AIIndexTask.source_type == AIKnowledgeSourceType.APPLICATION,
                AIIndexTask.source_id.in_(application_ids),
            ),
        )
        await self.db.execute(delete(AIIndexTask).where(task_source_filter))

    def _validate_salary_range(self, salary_min: int | None, salary_max: int | None):
        if (
            salary_min is not None
            and salary_max is not None
            and salary_min > salary_max
        ):
            raise HTTPException(
                status_code=400,
                detail="salary_min must be less than or equal to salary_max",
            )

    def _require_org_admin_organization(self, current_user: User) -> UUID:
        if (
            current_user.role not in (UserRole.ORG_ADMIN, UserRole.HR_MANAGER)
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user.organization_id
