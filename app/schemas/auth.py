from pydantic import BaseModel, EmailStr

from app.schemas.organization import OrganizationOut
from app.schemas.user import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    user: UserOut
    organization: OrganizationOut | None = None
