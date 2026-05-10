from pydantic import BaseModel, ConfigDict, EmailStr
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

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    description: Optional[str] = None
    website: Optional[str] = None
    updated_at: datetime
    created_at: datetime
