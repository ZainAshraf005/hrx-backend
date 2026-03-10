from fastapi import APIRouter
from app.api.endpoints import organizations

api_router = APIRouter()

api_router.include_router(
    organizations.router,
    tags=["Organizations"]
)
