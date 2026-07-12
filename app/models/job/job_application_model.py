from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel
from app.models.enums import (
    CandidateRankingRecommendation,
    CandidateRankingStatus,
    JobApplicationStatus,
    enum_values,
)


class JobApplication(BaseModel):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_email", name="uq_job_applications_job_email"),
    )

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    candidate_name = Column(String, nullable=False)
    candidate_email = Column(String, nullable=False, index=True)
    candidate_phone = Column(String, nullable=True)
    candidate_location = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    portfolio_url = Column(String, nullable=True)
    summary = Column(Text, nullable=True)

    resume_text = Column(Text, nullable=True)
    resume_file_name = Column(String, nullable=True)
    resume_content_type = Column(String, nullable=True)
    parsed_resume = Column(JSONB, nullable=True)

    cover_letter = Column(Text, nullable=True)
    status = Column(
        SAEnum(JobApplicationStatus, values_callable=enum_values, name="job_application_status"),
        nullable=False,
        default=JobApplicationStatus.SUBMITTED,
        index=True,
    )
    ranking_score = Column(Integer, nullable=True)
    ranking_recommendation = Column(
        SAEnum(
            CandidateRankingRecommendation,
            values_callable=enum_values,
            name="candidate_ranking_recommendation",
        ),
        nullable=True,
    )
    ranking_rationale = Column(Text, nullable=True)
    ranking_strengths = Column(JSONB, nullable=True)
    ranking_gaps = Column(JSONB, nullable=True)
    ranking_status = Column(
        SAEnum(CandidateRankingStatus, values_callable=enum_values, name="candidate_ranking_status"),
        nullable=False,
        default=CandidateRankingStatus.PENDING,
        index=True,
    )
    ranking_error = Column(Text, nullable=True)
    ranked_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="applications")
    organization = relationship("Organization")
