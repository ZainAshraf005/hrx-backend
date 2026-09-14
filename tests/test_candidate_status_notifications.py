from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.enums import JobApplicationStatus
from app.schemas.job_application_schema import JobApplicationStatusUpdate
from app.services.email_service import EmailService
from app.services.job_application_service import JobApplicationService
from app.services.resume_service import ResumeService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_copy"),
    [
        (JobApplicationStatus.SHORTLISTED, "shortlisted"),
        (JobApplicationStatus.REJECTED, "After careful consideration"),
    ],
)
async def test_candidate_decision_email_uses_soft_copy_and_escapes_names(
    status,
    expected_copy,
):
    email_service = EmailService()
    send_email = AsyncMock()
    email_service.send_email = cast(Any, send_email)  # type: ignore[method-assign]

    await email_service.send_job_application_status_email(
        email="candidate@example.com",
        candidate_name="Zain <Candidate>",
        job_title="Senior Engineer",
        organization_name="Zain & Mania",
        status=status,
    )

    awaited_call = send_email.await_args
    assert awaited_call is not None
    html = awaited_call.kwargs["html"]
    assert expected_copy in html
    assert "Zain &lt;Candidate&gt;" in html
    assert "Zain &amp; Mania" in html


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [JobApplicationStatus.SHORTLISTED, JobApplicationStatus.REJECTED],
)
async def test_candidate_receives_email_when_decision_status_changes(status):
    database = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    email_service = SimpleNamespace(send_job_application_status_email=AsyncMock())
    application = SimpleNamespace(
        status=JobApplicationStatus.SUBMITTED,
        candidate_email="candidate@example.com",
        candidate_name="Candidate Name",
        job=SimpleNamespace(
            title="Senior Software Engineer",
            organization=SimpleNamespace(name="Zain Mania"),
        ),
    )
    service = JobApplicationService(
        db=cast(Any, database),
        resume_service=ResumeService(),
        xkiro_service=cast(Any, SimpleNamespace()),
        email_service=cast(Any, email_service),
    )
    service.get_application = AsyncMock(return_value=application)

    await service.update_application_status(
        uuid4(),
        JobApplicationStatusUpdate(status=status),
        cast(Any, SimpleNamespace()),
    )

    email_service.send_job_application_status_email.assert_awaited_once_with(
        email="candidate@example.com",
        candidate_name="Candidate Name",
        job_title="Senior Software Engineer",
        organization_name="Zain Mania",
        status=status,
    )


@pytest.mark.asyncio
async def test_unchanged_decision_status_does_not_send_duplicate_email():
    database = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    email_service = SimpleNamespace(send_job_application_status_email=AsyncMock())
    application = SimpleNamespace(
        status=JobApplicationStatus.SHORTLISTED,
        candidate_email="candidate@example.com",
        candidate_name="Candidate Name",
        job=SimpleNamespace(
            title="Senior Software Engineer",
            organization=SimpleNamespace(name="Zain Mania"),
        ),
    )
    service = JobApplicationService(
        db=cast(Any, database),
        resume_service=ResumeService(),
        xkiro_service=cast(Any, SimpleNamespace()),
        email_service=cast(Any, email_service),
    )
    service.get_application = AsyncMock(return_value=application)

    await service.update_application_status(
        uuid4(),
        JobApplicationStatusUpdate(status=JobApplicationStatus.SHORTLISTED),
        cast(Any, SimpleNamespace()),
    )

    email_service.send_job_application_status_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_email_outage_does_not_undo_committed_candidate_status():
    database = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    email_service = SimpleNamespace(
        send_job_application_status_email=AsyncMock(
            side_effect=RuntimeError("Email provider unavailable")
        )
    )
    application = SimpleNamespace(
        status=JobApplicationStatus.SUBMITTED,
        candidate_email="candidate@example.com",
        candidate_name="Candidate Name",
        job=SimpleNamespace(
            title="Senior Software Engineer",
            organization=SimpleNamespace(name="Zain Mania"),
        ),
    )
    service = JobApplicationService(
        db=cast(Any, database),
        resume_service=ResumeService(),
        xkiro_service=cast(Any, SimpleNamespace()),
        email_service=cast(Any, email_service),
    )
    service.get_application = AsyncMock(return_value=application)

    updated = await service.update_application_status(
        uuid4(),
        JobApplicationStatusUpdate(status=JobApplicationStatus.REJECTED),
        cast(Any, SimpleNamespace()),
    )

    assert updated.status == JobApplicationStatus.REJECTED
    database.commit.assert_awaited_once()
    email_service.send_job_application_status_email.assert_awaited_once()
