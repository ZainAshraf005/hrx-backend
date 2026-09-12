from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.models.user.user_model import User
from app.services.employee_service import EmployeeService


def user(role: UserRole, organization_id: Any = None) -> User:
    return cast(
        User,
        SimpleNamespace(
            role=role,
            organization_id=organization_id if organization_id is not None else uuid4(),
        ),
    )


class FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []


class FakeSession:
    async def execute(self, _query):
        return FakeResult()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ORG_ADMIN, UserRole.HR_MANAGER])
async def test_get_employees_allows_organization_admin_and_hr_manager(role: UserRole):
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))

    assert await service.get_employees(user(role)) == []


@pytest.mark.asyncio
async def test_get_employees_rejects_employee_role():
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))

    with pytest.raises(HTTPException) as error:
        await service.get_employees(user(UserRole.EMPLOYEE))

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_employee_rejects_hr_manager():
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))

    with pytest.raises(HTTPException) as error:
        await service.delete_employee(uuid4(), user(UserRole.HR_MANAGER))

    assert error.value.status_code == 403
