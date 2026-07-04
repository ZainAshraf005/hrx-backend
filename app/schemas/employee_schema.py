from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole

EmployeeRole = Literal[UserRole.EMPLOYEE, UserRole.HR_MANAGER]


class EmployeeCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str
    role: EmployeeRole = UserRole.EMPLOYEE


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    designation: str | None = None
    role: EmployeeRole | None = None
    is_active: bool | None = None


class EmployeeUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: EmployeeRole
    is_active: bool
    is_verified: bool


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    user: EmployeeUserResponse
