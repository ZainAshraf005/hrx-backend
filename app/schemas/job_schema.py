from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


EmploymentType = Literal["full_time", "part_time", "contract", "internship", "temporary"]
WorkplaceType = Literal["onsite", "remote", "hybrid"]
JobStatus = Literal["draft", "open", "closed"]
SalaryPeriod = Literal["hourly", "monthly", "yearly"]


class JobBase(BaseModel):
    title: str
    description: str
    department: str | None = None
    location: str | None = None
    employment_type: EmploymentType = "full_time"
    workplace_type: WorkplaceType = "onsite"
    status: JobStatus = "draft"
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = "USD"
    salary_period: SalaryPeriod | None = "yearly"
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
    description: str
    department: str | None = None
    location: str | None = None
    employment_type: str
    workplace_type: str
    status: str
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None
    published_at: datetime | None = None
    closed_at: datetime | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
