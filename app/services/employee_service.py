from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import FRONTEND_URL
from app.core.security import create_signed_token, normalize_email
from app.models.employee.employee_model import Employee
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate
from app.services.email_service import EmailService


class EmployeeService:
    def __init__(self, db: AsyncSession, email_service: EmailService):
        self.db = db
        self.email_service = email_service

    async def create_employee(self, data: EmployeeCreate, current_user: User):
        organization_id = self._require_org_admin_organization(current_user)
        email = normalize_email(str(data.email))

        existing_user = await self._get_user_by_email(email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

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
        await self.db.commit()
        await self.db.refresh(employee)

        setup_token = self._create_employee_setup_token(user, employee)
        await self.email_service.send_employee_invite(email, data.first_name, setup_token, FRONTEND_URL)

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

        await self.db.commit()
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
        if current_user.role != "org_admin" or not current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not Authorized")
        return current_user.organization_id
