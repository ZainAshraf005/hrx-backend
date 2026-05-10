from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.dependencies.services import get_employee_service
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.services.employee_service import EmployeeService


router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("/", response_model=EmployeeResponse)
async def create_employee(
    payload: EmployeeCreate,
    current_user: User = Depends(require_roles("org_admin")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.create_employee(payload, current_user)


@router.get("/", response_model=List[EmployeeResponse])
async def list_employees(
    include_inactive: bool = False,
    current_user: User = Depends(require_roles("org_admin")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.get_employees(current_user, include_inactive)


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: UUID,
    current_user: User = Depends(require_roles("org_admin")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.get_employee(employee_id, current_user)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    current_user: User = Depends(require_roles("org_admin")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.update_employee(employee_id, payload, current_user)


@router.delete("/{employee_id}", response_model=EmployeeResponse)
async def delete_employee(
    employee_id: UUID,
    current_user: User = Depends(require_roles("org_admin")),
    service: EmployeeService = Depends(get_employee_service),
):
    return await service.delete_employee(employee_id, current_user)
