from fastapi import APIRouter, Depends

from app.dependencies.services import get_auth_service
from app.schemas.auth_schema import (
    ForgotPasswordOtpRequest,
    ForgotPasswordOtpResponse,
    LoginRequest,
    EmployeeSetPasswordRequest,
    ResetPasswordRequest,
    SetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/org-admin/set-password", response_model=TokenResponse)
async def set_org_admin_password(payload: SetPasswordRequest, service: AuthService = Depends(get_auth_service)):
    return await service.set_org_admin_password(payload.setup_token, payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(payload.email, payload.password)


@router.post("/forgot-password/request-otp", response_model=ForgotPasswordOtpResponse)
async def request_forgot_password_otp(
    payload: ForgotPasswordOtpRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.request_forgot_password_otp(payload.email)


@router.post("/forgot-password/reset", response_model=TokenResponse)
async def reset_forgot_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.reset_forgot_password(payload.email, payload.otp, payload.password)


@router.post("/employee/set-password", response_model=TokenResponse)
async def set_employee_password(payload: EmployeeSetPasswordRequest, service: AuthService = Depends(get_auth_service)):
    return await service.set_employee_password(payload.setup_token, payload.password)
