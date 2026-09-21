from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models.enums import UserRole
from app.models.user.user_model import User
from app.services.attendance_service import AttendanceService
from app.services.leave_service import LeaveService


def user(role: UserRole) -> User:
    return cast(
        User,
        SimpleNamespace(id=uuid4(), role=role, organization_id=uuid4()),
    )


class FakeResult:
    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return []

    def scalar_one_or_none(self):
        return None


class FakeSession:
    def __init__(self):
        self.queries = []

    async def execute(self, query):
        self.queries.append(query)
        return FakeResult()


def query_parameters(session: FakeSession, index: int = -1) -> list[Any]:
    return list(session.queries[index].compile().params.values())


async def utc_zone(_organization_id):
    return ZoneInfo("UTC")


@pytest.mark.asyncio
async def test_attendance_roster_scopes_hr_manager_to_employees(monkeypatch):
    session = FakeSession()
    service = AttendanceService(cast(Any, session))
    monkeypatch.setattr(service, "_organization_zone", utc_zone)

    today = datetime.now(UTC).date()

    assert await service.get_daily_roster(user(UserRole.HR_MANAGER), today) == []

    assert UserRole.EMPLOYEE in query_parameters(session)


@pytest.mark.asyncio
async def test_attendance_roster_keeps_hr_visible_to_organization_admin(monkeypatch):
    session = FakeSession()
    service = AttendanceService(cast(Any, session))
    monkeypatch.setattr(service, "_organization_zone", utc_zone)

    today = datetime.now(UTC).date()

    assert await service.get_daily_roster(user(UserRole.ORG_ADMIN), today) == []

    assert UserRole.EMPLOYEE not in query_parameters(session)


@pytest.mark.asyncio
async def test_hr_manager_cannot_complete_hr_attendance_checkout():
    session = FakeSession()
    service = AttendanceService(cast(Any, session))

    with pytest.raises(HTTPException) as error:
        await service.complete_checkout(
            uuid4(), "Missed checkout", user(UserRole.HR_MANAGER)
        )

    assert error.value.status_code == 404
    assert UserRole.EMPLOYEE in query_parameters(session)


@pytest.mark.asyncio
async def test_organization_leaves_scope_hr_manager_to_employees():
    session = FakeSession()
    service = LeaveService(cast(Any, session), cast(Any, object()))

    assert await service.get_organization_leaves(user(UserRole.HR_MANAGER)) == []

    assert UserRole.EMPLOYEE in query_parameters(session)


@pytest.mark.asyncio
async def test_organization_leaves_keep_hr_visible_to_organization_admin():
    session = FakeSession()
    service = LeaveService(cast(Any, session), cast(Any, object()))

    assert await service.get_organization_leaves(user(UserRole.ORG_ADMIN)) == []

    assert UserRole.EMPLOYEE not in query_parameters(session)


@pytest.mark.asyncio
async def test_hr_manager_cannot_change_hr_leave_status():
    session = FakeSession()
    service = LeaveService(cast(Any, session), cast(Any, object()))

    with pytest.raises(HTTPException) as error:
        await service.change_status(
            uuid4(),
            cast(Any, object()),
            user(UserRole.HR_MANAGER),
        )

    assert error.value.status_code == 404
    assert UserRole.EMPLOYEE in query_parameters(session)
