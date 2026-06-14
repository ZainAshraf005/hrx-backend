from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SetPasswordRequest(BaseModel):
    setup_token: str
    password: str = Field(min_length=8)


class EmployeeSetPasswordRequest(BaseModel):
    setup_token: str
    password: str = Field(min_length=8)


class ForgotPasswordOtpRequest(BaseModel):
    email: EmailStr


class ForgotPasswordOtpResponse(BaseModel):
    message: str


class MessageResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileOrganizationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    description: str | None = None


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    organization: ProfileOrganizationUpdateRequest | None = None


class AuthOrganizationResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr | None = None
    website: str | None = None
    description: str | None = None


class AuthEmployeeResponse(BaseModel):
    id: UUID
    organization_id: UUID
    first_name: str
    last_name: str
    phone: str | None = None
    designation: str
    is_active: bool


class AuthUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    organization_id: UUID | None = None
    organization: AuthOrganizationResponse | None = None
    employee: AuthEmployeeResponse | None = None


class AuthSessionResponse(BaseModel):
    user: AuthUserResponse
