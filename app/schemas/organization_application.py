from pydantic import BaseModel
from uuid import UUID
from app.models.organization.organization_application import Status


class OrganizationApplicationCreate(BaseModel):
    org_name: str
    email: str
    description: str | None = None
    website: str | None = None


class OrganizationApplicationResponse(BaseModel):
    id: UUID
    org_name: str
    email: str
    status: Status
    description: str | None = None
    website: str | None = None
