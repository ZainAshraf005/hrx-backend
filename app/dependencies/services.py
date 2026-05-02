from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.dependencies.db import get_db
from app.services.organization_service import OrganizationService


def get_organization_service(db: AsyncSession = Depends(get_db)):
    return OrganizationService(db)