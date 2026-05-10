from fastapi import APIRouter, Depends

from app.dependencies.services import get_auth_service
from app.schemas.auth_schema import (
    LoginRequest,
    EmployeeSetPasswordRequest,
    RequestOtpRequest,
    RequestOtpResponse,
    SetPasswordRequest,
    TokenResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/org-admin/request-otp", response_model=RequestOtpResponse)
async def request_org_admin_otp(payload: RequestOtpRequest, service: AuthService = Depends(get_auth_service)):
    return await service.request_org_admin_otp(payload.email)


@router.post("/org-admin/verify-otp", response_model=VerifyOtpResponse)
async def verify_org_admin_otp(payload: VerifyOtpRequest, service: AuthService = Depends(get_auth_service)):
    return await service.verify_org_admin_otp(payload.email, payload.otp)


@router.post("/org-admin/set-password", response_model=TokenResponse)
async def set_org_admin_password(payload: SetPasswordRequest, service: AuthService = Depends(get_auth_service)):
    return await service.set_org_admin_password(payload.setup_token, payload.password)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, service: AuthService = Depends(get_auth_service)):
    return await service.login(payload.email, payload.password)


@router.post("/employee/set-password", response_model=TokenResponse)
async def set_employee_password(payload: EmployeeSetPasswordRequest, service: AuthService = Depends(get_auth_service)):
    return await service.set_employee_password(payload.setup_token, payload.password)
