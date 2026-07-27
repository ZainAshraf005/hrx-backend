from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from uuid import UUID
from typing import Optional
from datetime import datetime

class OrganizationCreate(BaseModel):
    name: str
    email: EmailStr
    description: str | None = None
    website: str | None = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    description: Optional[str] = None
    website: Optional[str] = None
    timezone: Optional[str] = None

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
    email: EmailStr
    description: Optional[str] = None
    website: Optional[str] = None
    timezone: str
    updated_at: datetime
    created_at: datetime
