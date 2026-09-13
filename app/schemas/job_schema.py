from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    JobEmploymentType,
    JobWorkplaceType,
)
from app.models.enums import (
    JobStatus as JobStatusEnum,
)
from app.models.enums import (
    SalaryPeriod as SalaryPeriodEnum,
)

EmploymentType = JobEmploymentType
WorkplaceType = JobWorkplaceType
JobStatus = JobStatusEnum
SalaryPeriod = SalaryPeriodEnum


class JobBase(BaseModel):
    title: str
    description: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType = JobEmploymentType.FULL_TIME
    workplace_type: WorkplaceType = JobWorkplaceType.ONSITE
    status: JobStatus = JobStatusEnum.DRAFT
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = "USD"
    salary_period: SalaryPeriod | None = SalaryPeriodEnum.YEARLY
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType | None = None
    workplace_type: WorkplaceType | None = None
    status: JobStatus | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None
    is_active: bool | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    title: str
    slug: str
    description: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType
    workplace_type: WorkplaceType
    status: JobStatus
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None
    published_at: datetime | None = None
    closed_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PublicJobOrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    website: str | None = None


class PublicJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType
    workplace_type: WorkplaceType
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    organization: PublicJobOrganizationResponse
