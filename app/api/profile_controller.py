from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service
from app.models.user.user_model import User
from app.schemas.auth_schema import AuthUserResponse, ProfileUpdateRequest
from app.services.auth_service import AuthService


router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=AuthUserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return await service.get_profile(current_user)


@router.put("", response_model=AuthUserResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    return await service.update_profile(current_user, payload)
