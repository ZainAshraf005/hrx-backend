from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


EmployeeRole = Literal["employee", "hr_manager"]


class EmployeeCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str
    role: EmployeeRole = "employee"


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
    role: str
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
