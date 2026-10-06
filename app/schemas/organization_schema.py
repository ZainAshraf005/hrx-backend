from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class OrganizationCreate(BaseModel):
    name: str
    email: EmailStr
    description: str | None = None
    website: str | None = None

class OrganizationUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    description: str | None = None
    website: str | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None):
        if value is None:
            return value
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    email: EmailStr
    description: str | None = None
    website: str | None = None
    timezone: str
    updated_at: datetime
    created_at: datetime
