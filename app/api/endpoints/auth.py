from fastapi import HTTPException

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.user_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, email=data.email, password=data.password)

    if user.organization_id:
        await db.refresh(user, attribute_names=["organization"])

    if not user.organization.is_approved:
        raise HTTPException(status_code=409, detail={"message": "user inactive"})

    token = create_access_token({"sub": str(user.id)})

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=user,
        organization=user.organization
    )
