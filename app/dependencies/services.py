from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.services.ai.action_service import AIActionService
from app.services.ai.conversation_service import AIConversationService
from app.services.ai.provider import AIProvider, XkiroAIProvider
from app.services.ai.tool_service import AgentToolService
from app.services.attendance_service import AttendanceService
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.employee_service import EmployeeService
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService
from app.services.leave_service import LeaveService
from app.services.organization_service import OrganizationService
from app.services.resume_service import ResumeService
from app.services.xkiro_service import XkiroService


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


def get_attendance_service(db: AsyncSession = Depends(get_db)):
    return AttendanceService(db)


def get_leave_service(
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    return LeaveService(db, email_service)


def get_job_service(db: AsyncSession = Depends(get_db)):
    return JobService(db)


def get_resume_service():
    return ResumeService()


def get_xkiro_service():
    return XkiroService()


def get_job_application_service(
    db: AsyncSession = Depends(get_db),
    resume_service: ResumeService = Depends(get_resume_service),
    xkiro_service: XkiroService = Depends(get_xkiro_service),
    email_service: EmailService = Depends(get_email_service),
):
    return JobApplicationService(db, resume_service, xkiro_service, email_service)


def get_ai_provider():
    return XkiroAIProvider()


def get_ai_tool_service(
    db: AsyncSession = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    job_service: JobService = Depends(get_job_service),
    application_service: JobApplicationService = Depends(get_job_application_service),
    employee_service: EmployeeService = Depends(get_employee_service),
    organization_service: OrganizationService = Depends(get_organization_service),
):
    return AgentToolService(
        db,
        provider,
        job_service,
        application_service,
        employee_service,
        organization_service,
    )


def get_ai_conversation_service(
    db: AsyncSession = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    tool_service: AgentToolService = Depends(get_ai_tool_service),
):
    return AIConversationService(db, provider, tool_service)


def get_ai_action_service(
    db: AsyncSession = Depends(get_db),
    job_service: JobService = Depends(get_job_service),
    application_service: JobApplicationService = Depends(get_job_application_service),
    employee_service: EmployeeService = Depends(get_employee_service),
    organization_service: OrganizationService = Depends(get_organization_service),
):
    return AIActionService(
        db,
        job_service,
        application_service,
        employee_service,
        organization_service,
    )
