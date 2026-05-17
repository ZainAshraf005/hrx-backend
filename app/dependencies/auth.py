from typing import Callable
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AUTH_COOKIE_NAME
from app.core.security import decode_signed_token
from app.dependencies.db import get_db
from app.models.user.user_model import User


async def get_current_user(
    access_token: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

    if not access_token:
        raise credentials_exception

    payload = decode_signed_token(access_token)
    if not payload or payload.get("purpose") != "access":
        raise credentials_exception

    try:
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if not user or not user.is_active or not user.is_verified:
        raise credentials_exception

    return user


def require_roles(*roles: str) -> Callable:
    async def role_guard(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return role_guard


async def require_superadmin_or_own_organization(
    organization_id: UUID,
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role == "superadmin":
        return current_user

    if current_user.role == "org_admin" and current_user.organization_id == organization_id:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not enough permissions",
    )
