from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import LeaveStatus, LeaveType


class LeaveRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    status: Literal[
        LeaveStatus.APPROVED,
        LeaveStatus.REJECTED,
        LeaveStatus.WITHDRAWN,
    ]
    reason: str | None = Field(default=None, min_length=1)


class LeaveEmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    designation: str


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str
    status: LeaveStatus
    status_changed_by_user_id: UUID | None = None
    status_changed_at: datetime | None = None
    status_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    employee: LeaveEmployeeSummary
