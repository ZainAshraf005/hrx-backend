from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import get_user_by_email, create_user


async def register_user(db: AsyncSession, name: str, email: str):
    existing = await get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    return await create_user(db, name, email)
