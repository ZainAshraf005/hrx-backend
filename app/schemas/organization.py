from uuid import UUID

from pydantic import BaseModel

from app.schemas.user import UserCreate


class OrganizationApply(BaseModel):
    org_name: str
    owner: UserCreate


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    industry: str | None = None
    company_size: str | None = None
    is_approved: bool

    class Config:
        from_attributes = True
