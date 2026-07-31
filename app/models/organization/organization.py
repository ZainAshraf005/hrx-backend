from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.job.job_model import Job


class Organization(BaseModel):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="Asia/Karachi",
        server_default="Asia/Karachi",
    )

    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
