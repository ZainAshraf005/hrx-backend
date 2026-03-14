from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, name: str):
    user = User(email=email, name=name)
    db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    return user


async def get_all_users(db: AsyncSession) -> Sequence[User]:
    result = await db.execute(select(User).order_by(User.name))
    users = result.scalars().all()
    return users


async def update_user(db: AsyncSession, user_id: int, ):
    pass


async def delete_user(db: AsyncSession, user_id: str):
    user = await get_user_by_id(db, user_id)
    await db.delete(user)
    await db.commit()
