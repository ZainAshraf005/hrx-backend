from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID as PyUUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel
from app.models.enums import (
    CandidateRankingRecommendation,
    CandidateRankingStatus,
    JobApplicationStatus,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.job.job_model import Job
    from app.models.organization.organization import Organization


class JobApplication(BaseModel):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_email", name="uq_job_applications_job_email"),
    )

    job_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    candidate_name: Mapped[str] = mapped_column(String, nullable=False)
    candidate_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    candidate_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    candidate_location: Mapped[str | None] = mapped_column(String, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    resume_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resume_file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    resume_content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    parsed_resume: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[JobApplicationStatus] = mapped_column(
        SAEnum(JobApplicationStatus, values_callable=enum_values, name="job_application_status"),
        nullable=False,
        default=JobApplicationStatus.SUBMITTED,
        index=True,
    )
    ranking_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ranking_recommendation: Mapped[CandidateRankingRecommendation | None] = mapped_column(
        SAEnum(
            CandidateRankingRecommendation,
            values_callable=enum_values,
            name="candidate_ranking_recommendation",
        ),
        nullable=True,
    )
    ranking_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    ranking_strengths: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ranking_gaps: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    ranking_status: Mapped[CandidateRankingStatus] = mapped_column(
        SAEnum(CandidateRankingStatus, values_callable=enum_values, name="candidate_ranking_status"),
        nullable=False,
        default=CandidateRankingStatus.PENDING,
        index=True,
    )
    ranking_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ranked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    organization: Mapped["Organization"] = relationship("Organization")
