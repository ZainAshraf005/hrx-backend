from pydantic import BaseModel

from app.models.organization_application import Status


class OrganizationApplicationCreate(BaseModel):
    name: str
    email: str
    description: str | None = None
    website: str | None = None


class OrganizationApplicationResponse(BaseModel):
    id: int
    name: str
    email: str
    status: Status
    description: str | None = None
