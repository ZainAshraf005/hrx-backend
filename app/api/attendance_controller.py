from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.dependencies.services import get_attendance_service
from app.models.user.user_model import User
from app.schemas.attendance_schema import (
    AttendanceCheckoutCompletion,
    AttendanceDayResponse,
    AttendanceRecordResponse,
    AttendanceRosterItem,
)
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/check-in", response_model=AttendanceRecordResponse)
async def check_in(
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.check_in(current_user)


@router.post("/check-out", response_model=AttendanceRecordResponse)
async def check_out(
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.check_out(current_user)


@router.get("/me", response_model=list[AttendanceDayResponse])
async def get_my_attendance(
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_my_history(current_user, start_date, end_date)


@router.patch(
    "/{attendance_id}/complete-checkout",
    response_model=AttendanceRecordResponse,
)
async def complete_checkout(
    attendance_id: UUID,
    payload: AttendanceCheckoutCompletion,
    current_user: User = Depends(require_roles("hr_manager")),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.complete_checkout(
        attendance_id,
        payload.reason,
        current_user,
    )


@router.get("", response_model=list[AttendanceRosterItem])
async def get_daily_attendance(
    date: date | None = None,
    current_user: User = Depends(require_roles("hr_manager")),
    service: AttendanceService = Depends(get_attendance_service),
):
    return await service.get_daily_roster(current_user, date)
