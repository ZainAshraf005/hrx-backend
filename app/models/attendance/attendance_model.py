from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.employee.employee_model import Employee
    from app.models.organization.organization import Organization
    from app.models.user.user_model import User


class AttendanceRecord(BaseModel):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "work_date",
            name="uq_attendance_employee_work_date",
        ),
        CheckConstraint(
            "check_out_at IS NULL OR check_out_at > check_in_at",
            name="ck_attendance_checkout_after_checkin",
        ),
        Index(
            "uq_attendance_employee_open",
            "employee_id",
            unique=True,
            postgresql_where=text("check_out_at IS NULL"),
        ),
        Index(
            "ix_attendance_organization_work_date",
            "organization_id",
            "work_date",
        ),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checkout_completed_by_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    checkout_completion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped[Organization] = relationship("Organization")
    employee: Mapped[Employee] = relationship("Employee")
    checkout_completed_by: Mapped[User | None] = relationship("User")
