from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.dependencies.services import get_leave_service
from app.models.enums import LeaveStatus
from app.models.user.user_model import User
from app.schemas.leave_schema import (
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveStatusUpdate,
)
from app.services.leave_service import LeaveService


router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.post("", response_model=LeaveRequestResponse)
async def create_leave(
    payload: LeaveRequestCreate,
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: LeaveService = Depends(get_leave_service),
):
    return await service.create_leave(payload, current_user)


@router.get("/me", response_model=List[LeaveRequestResponse])
async def get_my_leaves(
    status: LeaveStatus | None = None,
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: LeaveService = Depends(get_leave_service),
):
    return await service.get_my_leaves(current_user, status)


@router.post("/{leave_id}/withdraw", response_model=LeaveRequestResponse)
async def withdraw_own_leave(
    leave_id: UUID,
    current_user: User = Depends(require_roles("employee", "hr_manager")),
    service: LeaveService = Depends(get_leave_service),
):
    return await service.withdraw_own(leave_id, current_user)


@router.patch("/{leave_id}/status", response_model=LeaveRequestResponse)
async def change_leave_status(
    leave_id: UUID,
    payload: LeaveStatusUpdate,
    current_user: User = Depends(require_roles("hr_manager", "org_admin")),
    service: LeaveService = Depends(get_leave_service),
):
    return await service.change_status(leave_id, payload, current_user)


@router.get("", response_model=List[LeaveRequestResponse])
async def get_organization_leaves(
    status: LeaveStatus | None = None,
    employee_id: UUID | None = None,
    current_user: User = Depends(require_roles("hr_manager", "org_admin")),
    service: LeaveService = Depends(get_leave_service),
):
    return await service.get_organization_leaves(
        current_user,
        status,
        employee_id,
    )
