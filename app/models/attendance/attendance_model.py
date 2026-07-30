from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


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
    work_date = Column(Date, nullable=False, index=True)
    check_in_at = Column(DateTime(timezone=True), nullable=False)
    check_out_at = Column(DateTime(timezone=True), nullable=True)
    checkout_completed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    checkout_completion_reason = Column(Text, nullable=True)

    organization = relationship("Organization")
    employee = relationship("Employee")
    checkout_completed_by = relationship("User")
