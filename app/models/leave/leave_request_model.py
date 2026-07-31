from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID as PyUUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel
from app.models.enums import LeaveStatus, LeaveType, enum_values

if TYPE_CHECKING:
    from app.models.employee.employee_model import Employee
    from app.models.organization.organization import Organization
    from app.models.user.user_model import User


class LeaveRequest(BaseModel):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="ck_leave_end_on_or_after_start",
        ),
        Index(
            "ix_leave_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_leave_employee_dates",
            "employee_id",
            "start_date",
            "end_date",
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
    leave_type: Mapped[LeaveType] = mapped_column(
        SAEnum(LeaveType, values_callable=enum_values, name="leave_type"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, values_callable=enum_values, name="leave_status"),
        nullable=False,
        default=LeaveStatus.PENDING,
        index=True,
    )
    status_changed_by_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization")
    employee: Mapped["Employee"] = relationship("Employee")
    status_changed_by: Mapped["User | None"] = relationship("User")
