from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime

class OrganizationCreate(BaseModel):
    name: str
    email: str
    description: str | None = None
    website: str | None = None

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None

class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    email: str
    description: Optional[str] = None
    website: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True