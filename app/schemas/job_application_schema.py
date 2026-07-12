from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    CandidateRankingRecommendation as CandidateRankingRecommendationEnum,
    CandidateRankingStatus as CandidateRankingStatusEnum,
    JobApplicationStatus as JobApplicationStatusEnum,
)

JobApplicationStatus = JobApplicationStatusEnum
CandidateRankingRecommendation = CandidateRankingRecommendationEnum
CandidateRankingStatus = CandidateRankingStatusEnum


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
    resume_text: str
    parsed_resume: ParsedResume


class CandidateRankingResult(BaseModel):
    score: int = Field(ge=0, le=100)
    recommendation: CandidateRankingRecommendation
    rationale: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class JobApplicationCreate(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    candidate_phone: str | None = None
    candidate_location: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None
    resume_text: str | None = None
    parsed_resume: ParsedResume | None = None
    cover_letter: str | None = None


class JobApplicationStatusUpdate(BaseModel):
    status: JobApplicationStatus


class JobApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    organization_id: UUID
    parsed_resume: ParsedResume | None = None
    cover_letter: str | None = None
    status: JobApplicationStatus
    ranking_score: int | None = None
    ranking_recommendation: CandidateRankingRecommendation | None = None
    ranking_rationale: str | None = None
    ranking_strengths: list[str] | None = None
    ranking_gaps: list[str] | None = None
    ranking_status: CandidateRankingStatus
    ranking_error: str | None = None
    ranked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
