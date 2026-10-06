from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app.api.job_controller import router as job_router
from app.models.enums import UserRole
from app.models.job.job_model import Job
from app.schemas.job_schema import JobCreate, JobResponse, JobUpdate
from app.services.job_application_service import JobApplicationService
from app.services.job_service import JobService


def test_job_lifecycle_has_one_source_of_truth():
    assert "status" not in Job.__table__.columns
    assert "status" not in JobCreate.model_fields
    assert "status" not in JobUpdate.model_fields
    assert "status" not in JobResponse.model_fields
    assert "is_active" in JobCreate.model_fields


def test_public_job_listing_only_uses_active_state():
    service = JobService(cast(Any, SimpleNamespace()))

    public_filter = str(service._public_jobs_query().whereclause)

    assert "jobs.is_active IS true" in public_filter
    assert "jobs.status" not in public_filter


@pytest.mark.asyncio
async def test_hr_job_listing_can_include_all_or_filter_by_active_state():
    query_result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=list),
    )
    database = SimpleNamespace(execute=AsyncMock(return_value=query_result))
    service = JobService(cast(Any, database))
    organization_id = uuid4()

    current_user = SimpleNamespace(
        organization_id=organization_id,
        role=UserRole.HR_MANAGER,
    )

    await service.get_jobs_by_organization(
        organization_id,
        cast(Any, current_user),
        is_active=None,
    )
    all_jobs_query = str(database.execute.await_args.args[0].whereclause)
    assert "jobs.organization_id" in all_jobs_query
    assert "jobs.is_active" not in all_jobs_query
    assert "jobs.status" not in all_jobs_query

    await service.get_jobs_by_organization(
        organization_id,
        cast(Any, current_user),
        is_active=False,
    )
    inactive_jobs_query = str(database.execute.await_args.args[0].whereclause)
    assert "jobs.is_active IS false" in inactive_jobs_query


def test_manager_routes_support_permanent_application_deletion():
    routes = {
        (route.path, method)
        for route in job_router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    assert ("/jobs/applications/{application_id}", "DELETE") in routes


@pytest.mark.asyncio
async def test_job_deletion_removes_the_database_record():
    database = SimpleNamespace(
        execute=AsyncMock(),
        delete=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    job = SimpleNamespace(id=uuid4(), organization_id=uuid4(), is_active=True)
    service = JobService(cast(Any, database))
    service.get_organization_job = AsyncMock(return_value=job)

    await service.delete_job(job.id, cast(Any, SimpleNamespace()))

    database.delete.assert_awaited_once_with(job)
    database.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_application_deletion_removes_the_database_record():
    database = SimpleNamespace(
        execute=AsyncMock(),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    application = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
    )
    service = JobApplicationService(
        cast(Any, database),
        cast(Any, SimpleNamespace()),
        cast(Any, SimpleNamespace()),
    )
    service.get_application = AsyncMock(return_value=application)

    await service.delete_application(
        application.id,
        cast(Any, SimpleNamespace()),
    )

    database.delete.assert_awaited_once_with(application)
    database.commit.assert_awaited_once()
