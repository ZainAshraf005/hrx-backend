from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job.job_model import Job
from app.models.user.user_model import User
from app.schemas.job_schema import JobCreate, JobUpdate


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, data: JobCreate, current_user: User):
        organization_id = self._require_org_admin_organization(current_user)
        self._validate_salary_range(data.salary_min, data.salary_max)

        job = Job(
            organization_id=organization_id,
            title=data.title,
            description=data.description,
            department=data.department,
            location=data.location,
            employment_type=data.employment_type,
            workplace_type=data.workplace_type,
            status=data.status,
            salary_min=data.salary_min,
            salary_max=data.salary_max,
            salary_currency=data.salary_currency,
            salary_period=data.salary_period,
            experience_level=data.experience_level,
            requirements=data.requirements,
            responsibilities=data.responsibilities,
            benefits=data.benefits,
            is_active=True,
        )
        self._apply_status_timestamps(job, data.status)

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_jobs(
        self,
        status: str | None = None,
    ):
        query = self._public_jobs_query()
        if status is not None:
            query = query.where(Job.status == status)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_jobs_by_organization(self, organization_id: UUID, status: str | None = None):
        query = self._public_jobs_query().where(Job.organization_id == organization_id)
        if status is not None:
            query = query.where(Job.status == status)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_job(self, job_id: UUID):
        result = await self.db.execute(
            self._public_jobs_query().where(Job.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
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
        salary_min = data.salary_min if "salary_min" in data.model_fields_set else job.salary_min
        salary_max = data.salary_max if "salary_max" in data.model_fields_set else job.salary_max
        self._validate_salary_range(salary_min, salary_max)

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

        if data.status is not None:
            job.status = data.status
            self._apply_status_timestamps(job, data.status)

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def delete_job(self, job_id: UUID, current_user: User):
        job = await self.get_organization_job(job_id, current_user)
        job.is_active = False

        await self.db.commit()
        await self.db.refresh(job)
        return job

    def _public_jobs_query(self):
        return (
            select(Job)
            .where(Job.is_active.is_(True), Job.status == "open")
            .order_by(Job.created_at.desc())
        )

    def _apply_status_timestamps(self, job: Job, status: str):
        now = datetime.now(timezone.utc)
        if status == "open" and job.published_at is None:
            job.published_at = now
        if status == "closed" and job.closed_at is None:
            job.closed_at = now

    def _validate_salary_range(self, salary_min: int | None, salary_max: int | None):
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise HTTPException(
                status_code=400,
                detail="salary_min must be less than or equal to salary_max",
            )

    def _require_org_admin_organization(self, current_user: User) -> UUID:
        if current_user.role not in ("org_admin", "hr_manager") or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user.organization_id
