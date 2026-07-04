from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import JobApplicationStatus as JobApplicationStatusEnum

JobApplicationStatus = JobApplicationStatusEnum


class ResumeWorkExperience(BaseModel):
    company: str | None = None
    title: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class ResumeEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ResumeCertification(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issued_date: str | None = None


class ParsedResume(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    work_experience: list[ResumeWorkExperience] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)
    certifications: list[ResumeCertification] = Field(default_factory=list)
    total_experience_years: float | None = None


class ResumeParseResponse(BaseModel):
    job_id: UUID
    parsed_resume: ParsedResume


class JobApplicationCreate(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    candidate_phone: str | None = None
    candidate_location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    parsed_resume: ParsedResume | None = None
    cover_letter: str | None = None


class JobApplicationStatusUpdate(BaseModel):
    status: JobApplicationStatus


class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    organization_id: UUID
    candidate_name: str
    candidate_email: EmailStr
    candidate_phone: str | None = None
    candidate_location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    parsed_resume: ParsedResume | None = None
    cover_letter: str | None = None
    status: JobApplicationStatus
    created_at: datetime
    updated_at: datetime
