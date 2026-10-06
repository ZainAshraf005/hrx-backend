from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AttendanceDayStatus


class AttendanceCheckoutCompletion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=1)


class AttendanceRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    employee_id: UUID
    work_date: date
    check_in_at: datetime
    check_out_at: datetime | None = None
    checkout_completed_by_user_id: UUID | None = None
    checkout_completion_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class AttendanceDayResponse(BaseModel):
    date: date
    status: AttendanceDayStatus
    attendance_id: UUID | None = None
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None


class AttendanceEmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    designation: str


class AttendanceRosterItem(AttendanceDayResponse):
    employee: AttendanceEmployeeSummary
