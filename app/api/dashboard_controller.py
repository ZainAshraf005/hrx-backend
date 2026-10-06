from fastapi import APIRouter, Depends

from app.dependencies.auth import require_roles
from app.dependencies.services import get_dashboard_service
from app.models.user.user_model import User
from app.schemas.dashboard_schema import OrganizationDashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/organization", response_model=OrganizationDashboardResponse)
async def get_organization_dashboard(
    current_user: User = Depends(require_roles("org_admin", "hr_manager")),
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.get_organization_dashboard(current_user)
