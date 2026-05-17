from fastapi import APIRouter, Depends, Response

from app.core.cookies import clear_auth_cookie, set_auth_cookie
from app.dependencies.services import get_auth_service
from app.schemas.auth_schema import (
    AuthSessionResponse,
    ForgotPasswordOtpRequest,
    ForgotPasswordOtpResponse,
    LoginRequest,
    EmployeeSetPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    SetPasswordRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/org-admin/set-password", response_model=MessageResponse)
async def set_org_admin_password(
    payload: SetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.set_org_admin_password(payload.setup_token, payload.password)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    result = await service.login(payload.email, payload.password)
    set_auth_cookie(response, result["access_token"])
    return result


@router.post("/forgot-password/request-otp", response_model=ForgotPasswordOtpResponse)
async def request_forgot_password_otp(
    payload: ForgotPasswordOtpRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.request_forgot_password_otp(payload.email)


@router.post("/forgot-password/reset", response_model=MessageResponse)
async def reset_forgot_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.reset_forgot_password(payload.email, payload.otp, payload.password)


@router.post("/employee/set-password", response_model=MessageResponse)
async def set_employee_password(
    payload: EmployeeSetPasswordRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.set_employee_password(payload.setup_token, payload.password)


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}
