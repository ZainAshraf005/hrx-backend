from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user import HrManager, UserOut, UsersResponse, UserResponse
from app.services.user_service import get_user_with_id, get_users, delete_user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/create")
async def create_user(data: HrManager, db: AsyncSession = Depends(get_db)):
    pass


@router.put("/update/{user_id}")
async def update_user(user_id: str, db: AsyncSession = Depends(get_db)):
    pass


@router.delete("/delete/{user_id}")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    await delete_user_service(db, user_id)
    return {
        "success": True,
        "user": user_id
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    user = await get_user_with_id(db, user_id)
    return UserResponse(
        success=True,
        user=user
    )


@router.get("/", response_model=UsersResponse)
async def get_all_users(db: AsyncSession = Depends(get_db)):
    users = await get_users(db)
    return UsersResponse(
        success=True,
        users=users
    )
