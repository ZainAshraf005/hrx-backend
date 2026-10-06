from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.models.user.user_model import User
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate
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

    def scalar_one_or_none(self):
        return None


class FakeSession:
    def __init__(self):
        self.query = None

    async def execute(self, _query):
        self.query = _query
        return FakeResult()


def query_parameters(session: FakeSession) -> list[Any]:
    assert session.query is not None
    return list(session.query.compile().params.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ORG_ADMIN, UserRole.HR_MANAGER])
async def test_get_employees_allows_organization_admin_and_hr_manager(role: UserRole):
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))

    assert await service.get_employees(user(role)) == []


@pytest.mark.asyncio
async def test_get_employees_scopes_hr_manager_to_employee_role():
    session = FakeSession()
    service = EmployeeService(cast(Any, session), cast(Any, object()))

    await service.get_employees(user(UserRole.HR_MANAGER))

    assert UserRole.EMPLOYEE in query_parameters(session)


@pytest.mark.asyncio
async def test_get_employees_does_not_scope_organization_admin_by_role():
    session = FakeSession()
    service = EmployeeService(cast(Any, session), cast(Any, object()))

    await service.get_employees(user(UserRole.ORG_ADMIN))

    assert UserRole.EMPLOYEE not in query_parameters(session)


@pytest.mark.asyncio
async def test_get_employee_scopes_hr_manager_to_employee_role():
    session = FakeSession()
    service = EmployeeService(cast(Any, session), cast(Any, object()))

    with pytest.raises(HTTPException) as error:
        await service.get_employee(uuid4(), user(UserRole.HR_MANAGER))

    assert error.value.status_code == 404
    assert UserRole.EMPLOYEE in query_parameters(session)


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


@pytest.mark.asyncio
async def test_create_employee_rejects_hr_role_for_hr_manager():
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))
    payload = EmployeeCreate(
        email="new-hr@example.com",
        first_name="New",
        last_name="HR",
        designation="HR Manager",
        role=UserRole.HR_MANAGER,
    )

    with pytest.raises(HTTPException) as error:
        await service.create_employee(payload, user(UserRole.HR_MANAGER))

    assert error.value.status_code == 403
    assert error.value.detail == "HR managers can only manage employees"


@pytest.mark.asyncio
async def test_update_employee_rejects_hr_role_for_hr_manager(monkeypatch):
    service = EmployeeService(cast(Any, FakeSession()), cast(Any, object()))

    async def existing_employee(*_args):
        return SimpleNamespace(user=SimpleNamespace(role=UserRole.EMPLOYEE))

    monkeypatch.setattr(service, "get_employee", existing_employee)

    with pytest.raises(HTTPException) as error:
        await service.update_employee(
            uuid4(),
            EmployeeUpdate(role=UserRole.HR_MANAGER),
            user(UserRole.HR_MANAGER),
        )

    assert error.value.status_code == 403
    assert error.value.detail == "HR managers can only manage employees"
