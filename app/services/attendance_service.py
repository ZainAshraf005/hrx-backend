from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance.attendance_model import AttendanceRecord
from app.models.employee.employee_model import Employee
from app.models.enums import AttendanceDayStatus, LeaveStatus, UserRole
from app.models.leave.leave_request_model import LeaveRequest
from app.models.organization.organization import Organization
from app.models.user.user_model import User


class AttendanceService:
    SELF_CHECKOUT_WINDOW = timedelta(hours=24)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_in(self, current_user: User) -> AttendanceRecord:
        employee = await self._current_employee(current_user, for_update=True)
        now = self._now()
        zone = await self._organization_zone(employee.organization_id)
        work_date = now.astimezone(zone).date()

        open_record = await self._open_record(employee.id, for_update=True)
        if open_record:
            raise HTTPException(
                status_code=409,
                detail="Complete the previous attendance checkout before checking in again",
            )

        existing = await self.db.scalar(
            select(AttendanceRecord.id).where(
                AttendanceRecord.employee_id == employee.id,
                AttendanceRecord.work_date == work_date,
            )
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Attendance has already been recorded for today",
            )

        approved_leave = await self.db.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= work_date,
                LeaveRequest.end_date >= work_date,
            )
        )
        if approved_leave:
            raise HTTPException(
                status_code=409,
                detail="Cannot check in on an approved leave date",
            )

        record = AttendanceRecord(
            organization_id=employee.organization_id,
            employee_id=employee.id,
            work_date=work_date,
            check_in_at=now,
        )
        self.db.add(record)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Attendance check-in conflicts with an existing record",
            ) from exc
        await self.db.refresh(record)
        return record

    async def check_out(self, current_user: User) -> AttendanceRecord:
        employee = await self._current_employee(current_user)
        record = await self._open_record(employee.id, for_update=True)
        if not record:
            raise HTTPException(
                status_code=409,
                detail="No open attendance record found",
            )

        now = self._now()
        check_in_at = self._aware_utc(record.check_in_at)
        if now - check_in_at > self.SELF_CHECKOUT_WINDOW:
            raise HTTPException(
                status_code=409,
                detail="The self-checkout window has expired; HR must complete checkout",
            )

        record.check_out_at = now
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def complete_checkout(
        self,
        attendance_id: UUID,
        reason: str,
        current_user: User,
    ) -> AttendanceRecord:
        organization_id = self._require_hr_organization(current_user)
        query = (
            select(AttendanceRecord)
            .where(
                AttendanceRecord.id == attendance_id,
                AttendanceRecord.organization_id == organization_id,
            )
            .with_for_update()
        )
        if current_user.role == UserRole.HR_MANAGER:
            query = query.where(
                AttendanceRecord.employee.has(
                    Employee.user.has(User.role == UserRole.EMPLOYEE)
                )
            )

        result = await self.db.execute(query)
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        if record.check_out_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Attendance checkout is already complete",
            )

        record.check_out_at = self._now()
        record.checkout_completed_by_user_id = current_user.id
        record.checkout_completion_reason = reason.strip()
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_my_history(
        self,
        current_user: User,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        employee = await self._current_employee(current_user)
        zone = await self._organization_zone(employee.organization_id)
        today = self._now().astimezone(zone).date()
        end = end_date or today
        start = start_date or today.replace(day=1)
        self._validate_history_range(start, end, today)

        employee_start = self._aware_utc(employee.created_at).astimezone(zone).date()
        start = max(start, employee_start)
        if start > end:
            return []

        records_result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee.id,
                AttendanceRecord.work_date >= start,
                AttendanceRecord.work_date <= end,
            )
        )
        records = {
            item.work_date: item for item in records_result.scalars().all()
        }
        leave_result = await self.db.execute(
            select(LeaveRequest).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= end,
                LeaveRequest.end_date >= start,
            )
        )
        approved_leaves = leave_result.scalars().all()

        return [
            self._day_payload(
                day,
                records.get(day),
                self._is_on_leave(day, approved_leaves),
            )
            for day in self._dates(start, end)
        ]

    async def get_daily_roster(
        self,
        current_user: User,
        work_date: date | None = None,
    ) -> list[dict]:
        organization_id = self._require_hr_organization(current_user)
        zone = await self._organization_zone(organization_id)
        today = self._now().astimezone(zone).date()
        requested_date = work_date or today
        if requested_date > today:
            raise HTTPException(
                status_code=422,
                detail="Attendance cannot be queried for a future date",
            )

        employee_query = (
            select(Employee)
            .where(
                Employee.organization_id == organization_id,
                Employee.is_active.is_(True),
            )
            .order_by(Employee.first_name, Employee.last_name)
        )
        if current_user.role == UserRole.HR_MANAGER:
            employee_query = employee_query.where(
                Employee.user.has(User.role == UserRole.EMPLOYEE)
            )

        employee_result = await self.db.execute(employee_query)
        employees = [
            employee
            for employee in employee_result.scalars().all()
            if self._aware_utc(employee.created_at).astimezone(zone).date()
            <= requested_date
        ]
        employee_ids = [employee.id for employee in employees]
        if not employee_ids:
            return []

        attendance_result = await self.db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id.in_(employee_ids),
                AttendanceRecord.work_date == requested_date,
            )
        )
        records = {
            item.employee_id: item
            for item in attendance_result.scalars().all()
        }
        leave_result = await self.db.execute(
            select(LeaveRequest).where(
                LeaveRequest.employee_id.in_(employee_ids),
                LeaveRequest.status == LeaveStatus.APPROVED,
                LeaveRequest.start_date <= requested_date,
                LeaveRequest.end_date >= requested_date,
            )
        )
        employees_on_leave = {
            item.employee_id for item in leave_result.scalars().all()
        }

        roster = []
        for employee in employees:
            day = self._day_payload(
                requested_date,
                records.get(employee.id),
                employee.id in employees_on_leave,
            )
            day["employee"] = employee
            roster.append(day)
        return roster

    async def _current_employee(
        self,
        current_user: User,
        for_update: bool = False,
    ) -> Employee:
        if (
            current_user.role not in {UserRole.EMPLOYEE, UserRole.HR_MANAGER}
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        query = select(Employee).where(
            Employee.user_id == current_user.id,
            Employee.organization_id == current_user.organization_id,
            Employee.is_active.is_(True),
        )
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        employee = result.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=403, detail="Active employee profile required")
        return employee

    async def _open_record(
        self,
        employee_id: UUID,
        for_update: bool = False,
    ) -> AttendanceRecord | None:
        query = select(AttendanceRecord).where(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.check_out_at.is_(None),
        )
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _organization_zone(self, organization_id: UUID) -> ZoneInfo:
        timezone_name = await self.db.scalar(
            select(Organization.timezone).where(Organization.id == organization_id)
        )
        if not timezone_name:
            raise HTTPException(status_code=404, detail="Organization not found")
        return ZoneInfo(timezone_name)

    def _require_hr_organization(self, current_user: User) -> UUID:
        if (
            current_user.role not in {UserRole.HR_MANAGER, UserRole.ORG_ADMIN}
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id

    def _validate_history_range(
        self,
        start_date: date,
        end_date: date,
        today: date,
    ):
        if end_date < start_date:
            raise HTTPException(
                status_code=422,
                detail="end_date must be on or after start_date",
            )
        if end_date > today:
            raise HTTPException(
                status_code=422,
                detail="Attendance cannot be queried for future dates",
            )

    @staticmethod
    def _day_payload(
        work_date: date,
        record: AttendanceRecord | None,
        on_leave: bool,
    ) -> dict:
        if record:
            status = (
                AttendanceDayStatus.PRESENT
                if record.check_out_at is not None
                else AttendanceDayStatus.CHECKED_IN
            )
        elif on_leave:
            status = AttendanceDayStatus.ON_LEAVE
        elif work_date.weekday() < 5:
            status = AttendanceDayStatus.ABSENT
        else:
            status = AttendanceDayStatus.NON_WORKING

        return {
            "date": work_date,
            "status": status,
            "attendance_id": record.id if record else None,
            "check_in_at": record.check_in_at if record else None,
            "check_out_at": record.check_out_at if record else None,
        }

    @staticmethod
    def _is_on_leave(work_date: date, leaves: Sequence[LeaveRequest]) -> bool:
        return any(
            leave.start_date <= work_date <= leave.end_date for leave in leaves
        )

    @staticmethod
    def _dates(start_date: date, end_date: date):
        current = start_date
        while current <= end_date:
            yield current
            current += timedelta(days=1)

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _now(self) -> datetime:
        return datetime.now(UTC)
