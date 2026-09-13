from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel
from app.models.enums import (
    JobEmploymentType,
    JobWorkplaceType,
    SalaryPeriod,
    enum_values,
)

if TYPE_CHECKING:
    from app.models.job.job_application_model import JobApplication
    from app.models.organization.organization import Organization


class Job(BaseModel):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_jobs_organization_slug"),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_type: Mapped[JobEmploymentType] = mapped_column(
        SAEnum(JobEmploymentType, values_callable=enum_values, name="job_employment_type"),
        nullable=False,
        default=JobEmploymentType.FULL_TIME,
    )
    workplace_type: Mapped[JobWorkplaceType] = mapped_column(
        SAEnum(JobWorkplaceType, values_callable=enum_values, name="job_workplace_type"),
        nullable=False,
        default=JobWorkplaceType.ONSITE,
    )
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        default="USD",
    )
    salary_period: Mapped[SalaryPeriod | None] = mapped_column(
        SAEnum(SalaryPeriod, values_callable=enum_values, name="salary_period"),
        nullable=True,
        default=SalaryPeriod.YEARLY,
    )

    experience_level: Mapped[str | None] = mapped_column(String, nullable=True)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsibilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="jobs",
    )
    applications: Mapped[list["JobApplication"]] = relationship(
        "JobApplication",
        back_populates="job",
        cascade="all, delete-orphan",
    )
