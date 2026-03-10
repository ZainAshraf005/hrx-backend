from pydantic import BaseModel, EmailStr


class OrganizationApply(BaseModel):
    name: str
    email: EmailStr
