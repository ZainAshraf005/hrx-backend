from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import JobApplicationStatus, LeaveStatus, LeaveType


class DashboardStats(BaseModel):
    total_employees: int
    present_today: int
    attendance_rate: float
    on_leave_today: int
    new_hires_this_month: int


class DashboardMonthlyApplications(BaseModel):
    month: str
    count: int


class DashboardPipelineItem(BaseModel):
    status: JobApplicationStatus
    count: int


class DashboardDesignationItem(BaseModel):
    designation: str
    count: int


class DashboardActivityItem(BaseModel):
    id: str
    user: str
    action: str
    occurred_at: datetime


class DashboardPendingLeave(BaseModel):
    id: UUID
    employee: str
    designation: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    status: LeaveStatus


class OrganizationDashboardResponse(BaseModel):
    stats: DashboardStats
    monthly_applications: list[DashboardMonthlyApplications]
    application_pipeline: list[DashboardPipelineItem]
    open_roles: int
    designation_distribution: list[DashboardDesignationItem]
    recent_activity: list[DashboardActivityItem]
    pending_leaves: list[DashboardPendingLeave]
