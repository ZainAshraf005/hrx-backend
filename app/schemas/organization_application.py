from pydantic import BaseModel, ConfigDict, EmailStr
from uuid import UUID
from app.models.organization.organization_application import Status


class OrganizationApplicationCreate(BaseModel):
    org_name: str
    email: EmailStr
    description: str | None = None
    website: str | None = None


class OrganizationApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_name: str
    email: EmailStr
    status: Status
    description: str | None = None
    website: str | None = None
