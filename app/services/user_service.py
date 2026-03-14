from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.crud.user import get_user_by_email, create_user, get_user_by_id, get_all_users, delete_user


async def register_user(db: AsyncSession, name: str, email: str):
    existing = await get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    return await create_user(db, name, email)


async def authenticate_user(db: AsyncSession, *, email: str, password: str):
    user = await get_user_by_email(db, email=email)
    if not user or not user.password or not verify_password(password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Credentials")

    return user


async def get_user_with_id(db: AsyncSession, user_id: str):
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    users = await get_all_users(db)
    return users


async def delete_user_service(db: AsyncSession, user_id: str):
    try:
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        await delete_user(db, user_id)
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Something went wrong")
