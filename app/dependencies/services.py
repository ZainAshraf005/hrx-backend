from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.dependencies.db import get_db
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.organization_service import OrganizationService


def get_email_service():
    return EmailService()


def get_organization_service(db: AsyncSession = Depends(get_db),
                             email_service: EmailService = Depends(get_email_service)):
    return OrganizationService(db, email_service)


def get_auth_service(db: AsyncSession = Depends(get_db),
                     email_service: EmailService = Depends(get_email_service)):
    return AuthService(db, email_service)
