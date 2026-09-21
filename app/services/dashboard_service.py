from datetime import UTC, date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance.attendance_model import AttendanceRecord
from app.models.employee.employee_model import Employee
from app.models.enums import JobApplicationStatus, LeaveStatus, UserRole
from app.models.job.job_application_model import JobApplication
from app.models.job.job_model import Job
from app.models.leave.leave_request_model import LeaveRequest
from app.models.organization.organization import Organization
from app.models.user.user_model import User


class DashboardService:
    PIPELINE_STATUSES = (
        JobApplicationStatus.SUBMITTED,
        JobApplicationStatus.REVIEWING,
        JobApplicationStatus.SHORTLISTED,
        JobApplicationStatus.HIRED,
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_organization_dashboard(self, current_user: User) -> dict:
        organization_id = self._require_organization_manager(current_user)
        timezone_name = await self.db.scalar(
            select(Organization.timezone).where(Organization.id == organization_id)
        )
        if not timezone_name:
            raise HTTPException(status_code=404, detail="Organization not found")

        now = datetime.now(UTC)
        zone = ZoneInfo(timezone_name)
        local_today = now.astimezone(zone).date()
        month_start = datetime.combine(
            local_today.replace(day=1), time.min, tzinfo=zone
        ).astimezone(UTC)
        employee_ids = self._employee_ids_query(current_user)

        total_employees = (
            await self.db.scalar(
                select(func.count()).select_from(employee_ids.subquery())
            )
            or 0
        )
        present_today = (
            await self.db.scalar(
                select(func.count(AttendanceRecord.id)).where(
                    AttendanceRecord.employee_id.in_(employee_ids),
                    AttendanceRecord.work_date == local_today,
                )
            )
            or 0
        )
        on_leave_today = (
            await self.db.scalar(
                select(func.count(LeaveRequest.id)).where(
                    LeaveRequest.employee_id.in_(employee_ids),
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    LeaveRequest.start_date <= local_today,
                    LeaveRequest.end_date >= local_today,
                )
            )
            or 0
        )
        new_hires = (
            await self.db.scalar(
                select(func.count(Employee.id)).where(
                    Employee.id.in_(employee_ids),
                    Employee.created_at >= month_start,
                )
            )
            or 0
        )
        open_roles = (
            await self.db.scalar(
                select(func.count(Job.id)).where(
                    Job.organization_id == organization_id,
                    Job.is_active.is_(True),
                )
            )
            or 0
        )

        monthly_applications = await self._monthly_applications(
            organization_id, local_today
        )
        pipeline = await self._application_pipeline(organization_id)
        designations = await self._designation_distribution(employee_ids)
        recent_activity = await self._recent_activity(employee_ids)
        pending_leaves = await self._pending_leaves(employee_ids)

        return {
            "stats": {
                "total_employees": total_employees,
                "present_today": present_today,
                "attendance_rate": round(present_today / total_employees * 100, 1)
                if total_employees
                else 0.0,
                "on_leave_today": on_leave_today,
                "new_hires_this_month": new_hires,
            },
            "monthly_applications": monthly_applications,
            "application_pipeline": pipeline,
            "open_roles": open_roles,
            "designation_distribution": designations,
            "recent_activity": recent_activity,
            "pending_leaves": pending_leaves,
        }

    def _employee_ids_query(self, current_user: User):
        organization_id = self._require_organization_manager(current_user)
        query = select(Employee.id).where(
            Employee.organization_id == organization_id,
            Employee.is_active.is_(True),
        )
        if current_user.role == UserRole.HR_MANAGER:
            query = query.where(Employee.user.has(User.role == UserRole.EMPLOYEE))
        return query

    async def _monthly_applications(
        self,
        organization_id: UUID,
        local_today: date,
    ) -> list[dict]:
        months = self._last_twelve_months(local_today)
        first_month = datetime(months[0][0], months[0][1], 1, tzinfo=UTC)
        result = await self.db.execute(
            select(
                func.date_trunc("month", JobApplication.created_at).label("month"),
                func.count(JobApplication.id),
            )
            .where(
                JobApplication.organization_id == organization_id,
                JobApplication.created_at >= first_month,
            )
            .group_by("month")
            .order_by("month")
        )
        counts = {(month.year, month.month): count for month, count in result.all()}
        return [
            {
                "month": date(year, month, 1).strftime("%b"),
                "count": counts.get((year, month), 0),
            }
            for year, month in months
        ]

    async def _application_pipeline(self, organization_id: UUID) -> list[dict]:
        result = await self.db.execute(
            select(JobApplication.status, func.count(JobApplication.id))
            .where(
                JobApplication.organization_id == organization_id,
                JobApplication.status.in_(self.PIPELINE_STATUSES),
            )
            .group_by(JobApplication.status)
        )
        counts: dict[JobApplicationStatus, int] = {
            status: count for status, count in result.all()
        }
        return [
            {"status": status, "count": counts.get(status, 0)}
            for status in self.PIPELINE_STATUSES
        ]

    async def _designation_distribution(self, employee_ids) -> list[dict]:
        result = await self.db.execute(
            select(Employee.designation, func.count(Employee.id).label("count"))
            .where(Employee.id.in_(employee_ids))
            .group_by(Employee.designation)
            .order_by(func.count(Employee.id).desc(), Employee.designation)
            .limit(5)
        )
        return [
            {"designation": designation, "count": count}
            for designation, count in result.all()
        ]

    async def _recent_activity(self, employee_ids) -> list[dict]:
        employee_result = await self.db.execute(
            select(Employee)
            .where(Employee.id.in_(employee_ids))
            .order_by(Employee.created_at.desc())
            .limit(5)
        )
        leave_result = await self.db.execute(
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.employee))
            .where(LeaveRequest.employee_id.in_(employee_ids))
            .order_by(LeaveRequest.created_at.desc())
            .limit(5)
        )
        attendance_result = await self.db.execute(
            select(AttendanceRecord)
            .options(selectinload(AttendanceRecord.employee))
            .where(AttendanceRecord.employee_id.in_(employee_ids))
            .order_by(AttendanceRecord.check_in_at.desc())
            .limit(5)
        )

        activities = [
            {
                "id": f"employee:{employee.id}",
                "user": self._employee_name(employee),
                "action": f"joined as {employee.designation}",
                "occurred_at": employee.created_at,
            }
            for employee in employee_result.scalars().all()
        ]
        activities.extend(
            {
                "id": f"leave:{request.id}",
                "user": self._employee_name(request.employee),
                "action": f"submitted a {request.leave_type.value} leave request",
                "occurred_at": request.created_at,
            }
            for request in leave_result.scalars().all()
        )
        activities.extend(
            {
                "id": f"attendance:{record.id}",
                "user": self._employee_name(record.employee),
                "action": "checked in",
                "occurred_at": record.check_in_at,
            }
            for record in attendance_result.scalars().all()
        )
        return sorted(
            activities,
            key=lambda activity: activity["occurred_at"],
            reverse=True,
        )[:5]

    async def _pending_leaves(self, employee_ids) -> list[dict]:
        result = await self.db.execute(
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.employee))
            .where(
                LeaveRequest.employee_id.in_(employee_ids),
                LeaveRequest.status == LeaveStatus.PENDING,
            )
            .order_by(LeaveRequest.created_at.desc())
            .limit(3)
        )
        return [
            {
                "id": request.id,
                "employee": self._employee_name(request.employee),
                "designation": request.employee.designation,
                "leave_type": request.leave_type,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "status": request.status,
            }
            for request in result.scalars().all()
        ]

    @staticmethod
    def _last_twelve_months(today: date) -> list[tuple[int, int]]:
        month_index = today.year * 12 + today.month - 12
        return [
            ((month_index + offset) // 12, (month_index + offset) % 12 + 1)
            for offset in range(12)
        ]

    @staticmethod
    def _employee_name(employee: Employee) -> str:
        return f"{employee.first_name} {employee.last_name}".strip()

    @staticmethod
    def _require_organization_manager(current_user: User) -> UUID:
        if (
            current_user.role not in {UserRole.ORG_ADMIN, UserRole.HR_MANAGER}
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id
