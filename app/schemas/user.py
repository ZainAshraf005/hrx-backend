from typing import List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.utlis import Response


class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class HrManager(UserCreate):
    is_hr_manager: bool


class UsersResponse(Response):
    users: List[UserOut]


class UserResponse(Response):
    user: UserOut
