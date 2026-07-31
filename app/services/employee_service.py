from datetime import timedelta
from typing import ClassVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import FRONTEND_URL
from app.core.security import create_signed_token, normalize_email
from app.models.employee.employee_model import Employee
from app.models.enums import UserRole
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate
from app.services.email_service import EmailService


class EmployeeService:
    ACTIVE_HR_CONSTRAINT = "uq_users_one_active_hr_per_organization"
    USER_EMAIL_CONSTRAINTS: ClassVar[set[str]] = {
        "ix_users_email",
        "users_email_key",
    }

    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

    async def create_employee(self, data: EmployeeCreate, current_user: User, frontend_url: str = FRONTEND_URL):
        organization_id = self._require_org_admin_organization(current_user)
        email = normalize_email(str(data.email))

        existing_user = await self._get_user_by_email(email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        if data.role == UserRole.HR_MANAGER:
            await self._ensure_no_other_active_hr(organization_id)

        user = User(
            email=email,
            password_hash=None,
            organization_id=organization_id,
            role=data.role,
            is_active=True,
            is_verified=False,
        )
        employee = Employee(
            user=user,
            organization_id=organization_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            designation=data.designation,
            is_active=True,
        )

        self.db.add(employee)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            self._raise_employee_integrity_error(exc)
        await self.db.refresh(employee)

        setup_token = self._create_employee_setup_token(user, employee)
        await self.email_service.send_employee_invite(email, data.first_name, setup_token, frontend_url)

        return await self.get_employee(employee.id, current_user)

    async def get_employees(self, current_user: User, include_inactive: bool = False):
        organization_id = self._require_org_admin_organization(current_user)
        query = (
            select(Employee)
            .options(selectinload(Employee.user))
            .where(Employee.organization_id == organization_id)
            .order_by(Employee.created_at.desc())
        )
        if not include_inactive:
            query = query.where(Employee.is_active.is_(True))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_employee(self, employee_id: UUID, current_user: User):
        organization_id = self._require_org_admin_organization(current_user)
        result = await self.db.execute(
            select(Employee)
            .options(selectinload(Employee.user))
            .where(Employee.id == employee_id, Employee.organization_id == organization_id)
        )
        employee = result.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        return employee

    async def update_employee(self, employee_id: UUID, data: EmployeeUpdate, current_user: User):
        employee = await self.get_employee(employee_id, current_user)
        final_role = data.role if data.role is not None else employee.user.role
        final_active = (
            data.is_active if data.is_active is not None else employee.user.is_active
        )
        if final_role == UserRole.HR_MANAGER and final_active:
            await self._ensure_no_other_active_hr(
                employee.organization_id,
                exclude_user_id=employee.user_id,
            )

        if data.first_name is not None:
            employee.first_name = data.first_name
        if data.last_name is not None:
            employee.last_name = data.last_name
        if "phone" in data.model_fields_set:
            employee.phone = data.phone
        if data.designation is not None:
            employee.designation = data.designation
        if data.role is not None:
            employee.user.role = data.role
        if data.is_active is not None:
            employee.is_active = data.is_active
            employee.user.is_active = data.is_active

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            self._raise_employee_integrity_error(exc)
        await self.db.refresh(employee)
        return await self.get_employee(employee.id, current_user)

    async def delete_employee(self, employee_id: UUID, current_user: User):
        employee = await self.get_employee(employee_id, current_user)
        employee.is_active = False
        employee.user.is_active = False

        await self.db.commit()
        await self.db.refresh(employee)
        return await self.get_employee(employee.id, current_user)

    async def _get_user_by_email(self, email: str):
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _ensure_no_other_active_hr(
        self,
        organization_id: UUID,
        exclude_user_id: UUID | None = None,
    ):
        query = select(User.id).where(
            User.organization_id == organization_id,
            User.role == UserRole.HR_MANAGER,
            User.is_active.is_(True),
        )
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)
        if await self.db.scalar(query):
            raise HTTPException(
                status_code=409,
                detail="An active HR manager already exists for this organization",
            )

    def _raise_employee_integrity_error(self, exc: IntegrityError):
        constraint_name = self._constraint_name(exc)
        if constraint_name == self.ACTIVE_HR_CONSTRAINT:
            raise HTTPException(
                status_code=409,
                detail="An active HR manager already exists for this organization",
            ) from exc
        if constraint_name in self.USER_EMAIL_CONSTRAINTS:
            raise HTTPException(
                status_code=400,
                detail="User already exists",
            ) from exc
        raise exc

    def _constraint_name(self, exc: IntegrityError) -> str | None:
        current = exc.orig
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            constraint_name = getattr(current, "constraint_name", None)
            if constraint_name:
                return constraint_name
            diagnostics = getattr(current, "diag", None)
            constraint_name = getattr(diagnostics, "constraint_name", None)
            if constraint_name:
                return constraint_name
            current = getattr(current, "__cause__", None) or getattr(
                current,
                "__context__",
                None,
            )

        error_text = str(exc)
        for constraint_name in {
            self.ACTIVE_HR_CONSTRAINT,
            *self.USER_EMAIL_CONSTRAINTS,
        }:
            if constraint_name in error_text:
                return constraint_name
        return None

    def _create_employee_setup_token(self, user: User, employee: Employee) -> str:
        return create_signed_token(
            {
                "purpose": "employee_setup",
                "user_id": str(user.id),
                "employee_id": str(employee.id),
                "email": user.email,
                "organization_id": str(user.organization_id),
            },
            timedelta(hours=24),
        )

    def _require_org_admin_organization(self, current_user: User) -> UUID:
        if current_user.role != UserRole.ORG_ADMIN or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id
