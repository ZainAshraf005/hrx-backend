from uuid import UUID

from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    name: str
    email: str

    class Config:
        from_attributes = True
