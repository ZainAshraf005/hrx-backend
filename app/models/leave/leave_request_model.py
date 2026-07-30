from sqlalchemy import CheckConstraint, Column, Date, DateTime, Enum as SAEnum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel
from app.models.enums import LeaveStatus, LeaveType, enum_values


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

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type = Column(
        SAEnum(LeaveType, values_callable=enum_values, name="leave_type"),
        nullable=False,
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        SAEnum(LeaveStatus, values_callable=enum_values, name="leave_status"),
        nullable=False,
        default=LeaveStatus.PENDING,
        index=True,
    )
    status_changed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    status_reason = Column(Text, nullable=True)

    organization = relationship("Organization")
    employee = relationship("Employee")
    status_changed_by = relationship("User")
