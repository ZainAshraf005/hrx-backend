from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

import main
from app.models.enums import UserRole
from app.models.user.user_model import User
from app.schemas.auth_schema import ProfileUpdateRequest
from app.services.auth_service import AuthService


def profile_user(name: str = "") -> User:
    return cast(
        User,
        SimpleNamespace(
            id=uuid4(),
            name=name,
            email="person@example.com",
            role=UserRole.EMPLOYEE,
            organization_id=uuid4(),
            organization=None,
            employee=None,
        ),
    )


def test_name_is_only_exposed_by_profile_responses():
    schemas = main.app.openapi()["components"]["schemas"]

    assert "name" in schemas["ProfileResponse"]["properties"]
    assert "name" not in schemas["AuthUserResponse"]["properties"]


def test_profile_update_does_not_accept_employee_name_fields():
    properties = ProfileUpdateRequest.model_json_schema()["properties"]

    assert "first_name" not in properties
    assert "last_name" not in properties


def test_user_name_column_defaults_to_empty_string():
    column = User.__table__.c.name

    assert column.nullable is False
    assert column.default.arg == ""
    assert column.server_default.arg == ""


@pytest.mark.asyncio
async def test_profile_update_saves_and_returns_name():
    user = profile_user()

    class FakeSession:
        async def commit(self):
            return None

    service = AuthService(cast(Any, FakeSession()), cast(Any, object()))

    async def get_user(_user_id):
        return user

    service._get_user_by_id = get_user  # type: ignore[method-assign]

    result = await service.update_profile(
        user,
        ProfileUpdateRequest(name="Taylor Example"),
    )

    assert user.name == "Taylor Example"
    assert result["name"] == "Taylor Example"
