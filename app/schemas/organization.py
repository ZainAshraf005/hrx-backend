from pydantic import BaseModel, EmailStr

from app.schemas.user import UserCreate


class OrganizationApply(BaseModel):
    org_name: str
    owner: UserCreate
