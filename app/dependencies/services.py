from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.dependencies.db import get_db
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.employee_service import EmployeeService
from app.services.gemini_service import GeminiService
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService
from app.services.organization_service import OrganizationService
from app.services.resume_service import ResumeService


def get_email_service():
    return EmailService()


def get_organization_service(db: AsyncSession = Depends(get_db),
                             email_service: EmailService = Depends(get_email_service)):
    return OrganizationService(db, email_service)


def get_auth_service(db: AsyncSession = Depends(get_db),
                     email_service: EmailService = Depends(get_email_service)):
    return AuthService(db, email_service)


def get_employee_service(db: AsyncSession = Depends(get_db),
                         email_service: EmailService = Depends(get_email_service)):
    return EmployeeService(db, email_service)


def get_job_service(db: AsyncSession = Depends(get_db)):
    return JobService(db)


def get_resume_service():
    return ResumeService()


def get_gemini_service():
    return GeminiService()


def get_job_application_service(
    db: AsyncSession = Depends(get_db),
    resume_service: ResumeService = Depends(get_resume_service),
    gemini_service: GeminiService = Depends(get_gemini_service),
):
    return JobApplicationService(db, resume_service, gemini_service)
