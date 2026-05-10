from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RequestOtpRequest(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    message: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class VerifyOtpResponse(BaseModel):
    setup_token: str


class SetPasswordRequest(BaseModel):
    setup_token: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthOrganizationResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr | None = None
    website: str | None = None
    description: str | None = None


class AuthUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    organization_id: UUID | None = None
    organization: AuthOrganizationResponse | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse
