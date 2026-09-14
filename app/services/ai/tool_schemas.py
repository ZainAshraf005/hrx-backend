from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import AI_AGENT_MAX_BULK_TARGETS
from app.models.enums import (
    JobApplicationStatus,
    JobEmploymentType,
    JobWorkplaceType,
    SalaryPeriod,
    UserRole,
)


class ToolParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyParams(ToolParams):
    pass


class SearchJobsParams(ToolParams):
    title: str | None = None
    department: str | None = None
    is_active: bool | None = None
    created_from: date | None = None
    created_to: date | None = None
    limit: int = Field(default=20, ge=1, le=50)


class JobIdParams(ToolParams):
    job_id: UUID


class JobIdsParams(ToolParams):
    job_ids: list[UUID] = Field(min_length=1, max_length=AI_AGENT_MAX_BULK_TARGETS)


class SetJobsActiveParams(JobIdsParams):
    is_active: bool


class ApplicationQueryParams(ToolParams):
    job_id: UUID | None = None
    status: JobApplicationStatus | None = None
    created_from: date | None = None
    created_to: date | None = None
    limit: int = Field(default=20, ge=1, le=50)


class ApplicationListParams(ApplicationQueryParams):
    sort: str = Field(default="rank", pattern="^(rank|created_at)$")


class TopApplicantsParams(ToolParams):
    job_id: UUID
    limit: int = Field(default=5, ge=1, le=20)


class ApplicationIdParams(ToolParams):
    application_id: UUID


class SemanticSearchParams(ToolParams):
    query: str = Field(min_length=2, max_length=2000)
    source_type: str | None = Field(default=None, pattern="^(job|application)$")
    limit: int = Field(default=8, ge=1, le=20)


class EmployeeQueryParams(ToolParams):
    role: UserRole | None = None
    include_inactive: bool = False
    limit: int = Field(default=20, ge=1, le=50)


class EmployeeIdParams(ToolParams):
    employee_id: UUID


class CreateJobDraftParams(ToolParams):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(min_length=1)
    department: str | None = None
    location: str | None = None
    employment_type: JobEmploymentType = JobEmploymentType.FULL_TIME
    workplace_type: JobWorkplaceType = JobWorkplaceType.ONSITE
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = "USD"
    salary_period: SalaryPeriod | None = SalaryPeriod.YEARLY
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None


class UpdateJobParams(ToolParams):
    job_id: UUID
    title: str | None = None
    description: str | None = None
    department: str | None = None
    location: str | None = None
    employment_type: JobEmploymentType | None = None
    workplace_type: JobWorkplaceType | None = None
    is_active: bool | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None
    experience_level: str | None = None
    requirements: str | None = None
    responsibilities: str | None = None
    benefits: str | None = None


class ChangeApplicationStatusParams(ToolParams):
    application_id: UUID
    status: JobApplicationStatus


class InviteEmployeeParams(ToolParams):
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str
    role: Literal[UserRole.EMPLOYEE, UserRole.HR_MANAGER] = UserRole.EMPLOYEE


class UpdateEmployeeParams(ToolParams):
    employee_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    designation: str | None = None
    role: Literal[UserRole.EMPLOYEE, UserRole.HR_MANAGER] | None = None
    is_active: bool | None = None


class UpdateOrganizationParams(ToolParams):
    name: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    description: str | None = None
    timezone: str | None = None


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_unset=True)
    return value
