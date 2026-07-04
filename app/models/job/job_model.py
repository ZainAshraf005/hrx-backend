from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel
from app.models.enums import (
    JobEmploymentType,
    JobStatus,
    JobWorkplaceType,
    SalaryPeriod,
    enum_values,
)


class Job(BaseModel):
    __tablename__ = "jobs"

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    department = Column(String, nullable=True)
    location = Column(String, nullable=True)
    employment_type = Column(
        SAEnum(JobEmploymentType, values_callable=enum_values, name="job_employment_type"),
        nullable=False,
        default=JobEmploymentType.FULL_TIME,
    )
    workplace_type = Column(
        SAEnum(JobWorkplaceType, values_callable=enum_values, name="job_workplace_type"),
        nullable=False,
        default=JobWorkplaceType.ONSITE,
    )
    status = Column(
        SAEnum(JobStatus, values_callable=enum_values, name="job_status"),
        nullable=False,
        default=JobStatus.DRAFT,
        index=True,
    )

    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String, nullable=True, default="USD")
    salary_period = Column(
        SAEnum(SalaryPeriod, values_callable=enum_values, name="salary_period"),
        nullable=True,
        default=SalaryPeriod.YEARLY,
    )

    experience_level = Column(String, nullable=True)
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)

    published_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    organization = relationship("Organization", back_populates="jobs")
    applications = relationship("JobApplication", back_populates="job", cascade="all, delete-orphan")
