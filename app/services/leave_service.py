import logging
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.attendance.attendance_model import AttendanceRecord
from app.models.employee.employee_model import Employee
from app.models.enums import LeaveStatus, UserRole
from app.models.leave.leave_request_model import LeaveRequest
from app.models.organization.organization import Organization
from app.models.user.user_model import User
from app.schemas.leave_schema import LeaveRequestCreate, LeaveStatusUpdate
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class LeaveService:
    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

    async def create_leave(
        self,
        data: LeaveRequestCreate,
        current_user: User,
    ) -> LeaveRequest:
        employee = await self._current_employee(current_user, for_update=True)
        today = await self._local_today(employee.organization_id)
        if data.start_date < today:
            raise HTTPException(
                status_code=422,
                detail="Leave cannot start before the organization-local current date",
            )

        overlap = await self.db.scalar(
            select(LeaveRequest.id).where(
                LeaveRequest.employee_id == employee.id,
                LeaveRequest.status.in_(
                    [LeaveStatus.PENDING, LeaveStatus.APPROVED]
                ),
                LeaveRequest.start_date <= data.end_date,
                LeaveRequest.end_date >= data.start_date,
            )
        )
        if overlap:
            raise HTTPException(
                status_code=409,
                detail="Leave dates overlap an existing pending or approved request",
            )

        request = LeaveRequest(
            organization_id=employee.organization_id,
            employee_id=employee.id,
            employee=employee,
            leave_type=data.leave_type,
            start_date=data.start_date,
            end_date=data.end_date,
            reason=data.reason.strip(),
            status=LeaveStatus.PENDING,
        )
        self.db.add(request)
        await self.db.commit()
        return await self._leave_with_employee(request.id)

    async def get_my_leaves(
        self,
        current_user: User,
        status: LeaveStatus | None = None,
    ) -> list[LeaveRequest]:
        employee = await self._current_employee(current_user)
        query = (
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.employee))
            .where(LeaveRequest.employee_id == employee.id)
            .order_by(LeaveRequest.created_at.desc())
        )
        if status is not None:
            query = query.where(LeaveRequest.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_organization_leaves(
        self,
        current_user: User,
        status: LeaveStatus | None = None,
        employee_id: UUID | None = None,
    ) -> list[LeaveRequest]:
        organization_id = self._require_leave_staff(current_user)
        query = (
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.employee).selectinload(Employee.user)
            )
            .where(LeaveRequest.organization_id == organization_id)
            .order_by(LeaveRequest.created_at.desc())
        )
        if employee_id is not None:
            query = query.where(LeaveRequest.employee_id == employee_id)
        if status is not None:
            query = query.where(LeaveRequest.status == status)

        result = await self.db.execute(query)
        return list(result.scalars().unique().all())

    async def withdraw_own(
        self,
        leave_id: UUID,
        current_user: User,
    ) -> LeaveRequest:
        employee = await self._current_employee(current_user)
        result = await self.db.execute(
            select(LeaveRequest)
            .options(selectinload(LeaveRequest.employee))
            .where(
                LeaveRequest.id == leave_id,
                LeaveRequest.employee_id == employee.id,
            )
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if not request:
            raise HTTPException(status_code=404, detail="Leave request not found")
        if request.status != LeaveStatus.PENDING:
            raise HTTPException(
                status_code=409,
                detail="Only a pending leave request can be withdrawn by its employee",
            )

        request.status = LeaveStatus.WITHDRAWN
        request.status_changed_by_user_id = current_user.id
        request.status_changed_at = self._now()
        request.status_reason = None
        await self.db.commit()
        return await self._leave_with_employee(request.id)

    async def change_status(
        self,
        leave_id: UUID,
        data: LeaveStatusUpdate,
        current_user: User,
    ) -> LeaveRequest:
        organization_id = self._require_leave_staff(current_user)
        result = await self.db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.employee).selectinload(Employee.user)
            )
            .where(
                LeaveRequest.id == leave_id,
                LeaveRequest.organization_id == organization_id,
            )
            .with_for_update()
        )
        request = result.scalar_one_or_none()
        if not request:
            raise HTTPException(status_code=404, detail="Leave request not found")

        self._authorize_status_actor(request, current_user)
        self._validate_transition(request.status, data.status)
        await self.db.execute(
            select(Employee.id)
            .where(Employee.id == request.employee_id)
            .with_for_update()
        )
        reason = data.reason.strip() if data.reason is not None else None
        if data.status in {LeaveStatus.REJECTED, LeaveStatus.WITHDRAWN} and not reason:
            raise HTTPException(
                status_code=422,
                detail=f"A reason is required when leave is {data.status.value}",
            )

        if data.status == LeaveStatus.APPROVED:
            attendance = await self.db.scalar(
                select(AttendanceRecord.id).where(
                    AttendanceRecord.employee_id == request.employee_id,
                    AttendanceRecord.work_date >= request.start_date,
                    AttendanceRecord.work_date <= request.end_date,
                )
            )
            if attendance:
                raise HTTPException(
                    status_code=409,
                    detail="Leave cannot be approved because attendance exists for a covered date",
                )

        request.status = data.status
        request.status_changed_by_user_id = current_user.id
        request.status_changed_at = self._now()
        request.status_reason = reason
        await self.db.commit()
        request = await self._leave_with_employee(request.id)

        try:
            await self.email_service.send_leave_status_email(
                email=request.employee.user.email,
                first_name=request.employee.first_name,
                leave_type=request.leave_type.value,
                start_date=request.start_date,
                end_date=request.end_date,
                status=request.status.value,
                reason=request.status_reason,
            )
        # The leave status is already committed; an email outage must not
        # roll it back, but the failed notification still needs visibility.
        except Exception:
            logger.exception("Failed to send leave status email")

        return request

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

    async def _leave_with_employee(self, leave_id: UUID) -> LeaveRequest:
        result = await self.db.execute(
            select(LeaveRequest)
            .options(
                selectinload(LeaveRequest.employee).selectinload(Employee.user)
            )
            .where(LeaveRequest.id == leave_id)
        )
        return result.scalar_one()

    def _require_leave_staff(self, current_user: User) -> UUID:
        if (
            current_user.role not in {UserRole.HR_MANAGER, UserRole.ORG_ADMIN}
            or not current_user.organization_id
        ):
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id

    def _authorize_status_actor(
        self,
        request: LeaveRequest,
        current_user: User,
    ):
        if current_user.role == UserRole.ORG_ADMIN:
            return
        if current_user.role == UserRole.HR_MANAGER:
            if request.employee.user.id == current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="HR manager cannot decide their own leave request",
                )
            return
        raise HTTPException(status_code=403, detail="Not Authorized")

    @staticmethod
    def _validate_transition(current: LeaveStatus, target: LeaveStatus):
        allowed = {
            LeaveStatus.PENDING: {
                LeaveStatus.APPROVED,
                LeaveStatus.REJECTED,
                LeaveStatus.WITHDRAWN,
            },
            LeaveStatus.APPROVED: {
                LeaveStatus.REJECTED,
                LeaveStatus.WITHDRAWN,
            },
            LeaveStatus.REJECTED: {
                LeaveStatus.APPROVED,
                LeaveStatus.WITHDRAWN,
            },
            LeaveStatus.WITHDRAWN: set(),
        }
        if target not in allowed[current]:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot change leave status from {current.value} to {target.value}",
            )

    async def _local_today(self, organization_id: UUID):
        timezone_name = await self.db.scalar(
            select(Organization.timezone).where(Organization.id == organization_id)
        )
        if not timezone_name:
            raise HTTPException(status_code=404, detail="Organization not found")
        return self._now().astimezone(ZoneInfo(timezone_name)).date()

    def _now(self) -> datetime:
        return datetime.now(UTC)
