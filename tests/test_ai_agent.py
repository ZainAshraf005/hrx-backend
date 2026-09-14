import pathlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import MissingGreenlet

import main
from app.core.config import (
    AI_AGENT_MAX_BULK_TARGETS,
    AI_AGENT_MAX_PROPOSALS_PER_TURN,
)
from app.models.ai.agent_models import (
    AIActionProposal,
    AIConversation,
    AIIndexTask,
    AIKnowledgeChunk,
)
from app.models.enums import (
    AIActionProposalStatus,
    AIConversationMode,
    UserRole,
)
from app.models.user.user_model import User
from app.schemas.organization_schema import OrganizationUpdate
from app.services.ai.action_service import AIActionService
from app.services.ai.conversation_service import AIConversationService
from app.services.ai.indexing_service import KnowledgeIndexService
from app.services.ai.provider import AIProvider, XkiroAIProvider
from app.services.ai.tool_schemas import (
    CreateJobDraftParams,
    InviteEmployeeParams,
    JobIdsParams,
    SetJobsActiveParams,
    UpdateEmployeeParams,
)
from app.services.ai.tool_service import AgentToolService


class DummyProvider:
    model = "test-model"


def make_tool_service():
    placeholder: Any = object()
    return AgentToolService(
        db=placeholder,
        provider=cast(AIProvider, DummyProvider()),
        job_service=placeholder,
        application_service=placeholder,
        employee_service=placeholder,
        organization_service=placeholder,
    )


def user(role: UserRole, name: str = "") -> User:
    return cast(
        User,
        SimpleNamespace(id=uuid4(), organization_id=uuid4(), role=role, name=name),
    )


def test_agent_routes_are_registered():
    paths = main.app.openapi()["paths"]
    assert "/api/ai/conversations" in paths
    assert "/api/ai/conversations/{conversation_id}/turns" in paths
    assert "/api/ai/action-proposals/{proposal_id}/confirm" in paths
    parameters = paths["/api/ai/action-proposals/{proposal_id}/confirm"]["post"][
        "parameters"
    ]
    assert any(item["name"] == "Idempotency-Key" for item in parameters)


def test_conversation_service_does_not_shadow_builtin_list():
    assert not hasattr(AIConversationService, "list")
    assert hasattr(AIConversationService, "list_conversations")


def test_tool_catalog_is_role_scoped_and_read_mode_has_no_mutations():
    service = make_tool_service()

    hr_read = service.definitions(
        AIConversationMode.READ_MODE, user(UserRole.HR_MANAGER)
    )
    hr_action = service.definitions(
        AIConversationMode.ACTION_MODE,
        user(UserRole.HR_MANAGER),
    )
    admin_action = service.definitions(
        AIConversationMode.ACTION_MODE,
        user(UserRole.ORG_ADMIN),
    )

    assert all(not definition.mutation for definition in hr_read)
    assert "propose_create_job_draft" in {item.name for item in hr_action}
    assert "propose_update_organization" not in {item.name for item in hr_action}
    assert "list_employees" not in {item.name for item in hr_action}
    assert "propose_update_organization" in {item.name for item in admin_action}
    assert "list_employees" in {item.name for item in admin_action}


def test_employee_and_superadmin_cannot_use_agent():
    service = make_tool_service()
    for role in (UserRole.EMPLOYEE, UserRole.SUPERADMIN):
        with pytest.raises(HTTPException) as error:
            service.definitions(AIConversationMode.READ_MODE, user(role))
        assert error.value.status_code == 403


def test_tool_json_schemas_are_inlined_for_provider():
    definitions = make_tool_service().definitions(
        AIConversationMode.ACTION_MODE,
        user(UserRole.ORG_ADMIN),
    )
    serialized = repr([definition.parameters for definition in definitions])
    assert "$ref" not in serialized
    assert "$defs" not in serialized


def test_employee_tools_cannot_assign_privileged_roles():
    common = {
        "email": "person@example.com",
        "first_name": "A",
        "last_name": "Person",
        "designation": "Recruiter",
    }
    for role in ("org_admin", "superadmin"):
        with pytest.raises(ValidationError):
            InviteEmployeeParams(**common, role=cast(Any, role))
        with pytest.raises(ValidationError):
            UpdateEmployeeParams(employee_id=uuid4(), role=cast(Any, role))


def test_job_draft_params_do_not_allow_publishing_status():
    schema = CreateJobDraftParams.model_json_schema()
    assert "status" not in schema["properties"]


@pytest.mark.asyncio
async def test_confirmed_ai_job_draft_is_created_inactive():
    job_service = SimpleNamespace(create_job=AsyncMock())
    unused: Any = None
    service = AIActionService(
        unused,
        job_service,
        unused,
        unused,
        unused,
    )
    proposal = SimpleNamespace(
        operation="create_job_draft",
        arguments={"title": "Backend Engineer", "description": "Build APIs."},
    )
    actor = user(UserRole.HR_MANAGER)

    await service._execute(cast(Any, proposal), actor, "https://example.test")

    payload = job_service.create_job.await_args.args[0]
    assert payload.is_active is False
    assert "status" not in type(payload).model_fields


def test_action_proposal_expiry_and_ownership_validation():
    actor = user(UserRole.HR_MANAGER)
    proposal = AIActionProposal(
        id=uuid4(),
        conversation_id=uuid4(),
        organization_id=actor.organization_id,
        proposed_by_user_id=actor.id,
        operation="change_application_status",
        arguments={},
        preview={},
        status=AIActionProposalStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    unused: Any = None
    service = AIActionService(unused, unused, unused, unused, unused)
    service._validate_pending_proposal(proposal, actor)

    other_actor = user(UserRole.HR_MANAGER)
    with pytest.raises(HTTPException) as error:
        service._validate_pending_proposal(proposal, other_actor)
    assert error.value.status_code == 403


def test_index_task_uses_migrated_shared_source_enum():
    knowledge_enum: Any = AIKnowledgeChunk.__table__.c.source_type.type
    task_enum: Any = AIIndexTask.__table__.c.source_type.type

    assert task_enum.name == knowledge_enum.name == "ai_knowledge_source_type"


@pytest.mark.asyncio
async def test_action_failure_does_not_access_expired_actor_after_rollback():
    class ScalarResult:
        def __init__(self, value: Any):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    actor_id = uuid4()
    organization_id = uuid4()
    proposal = AIActionProposal(
        id=uuid4(),
        conversation_id=uuid4(),
        organization_id=organization_id,
        proposed_by_user_id=actor_id,
        operation="create_job_draft",
        arguments={},
        preview={},
        resource_type="job",
        status=AIActionProposalStatus.PENDING,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    conversation = cast(
        AIConversation,
        SimpleNamespace(mode=AIConversationMode.ACTION_MODE),
    )

    class FakeSession:
        def __init__(self):
            self.rolled_back = False
            self.results = [conversation, proposal, proposal]

        async def get(self, _model: Any, _identifier: Any):
            return proposal

        async def execute(self, _statement: Any):
            return ScalarResult(self.results.pop(0))

        async def scalar(self, _statement: Any):
            return None

        def add(self, _instance: Any):
            return None

        async def flush(self):
            return None

        async def rollback(self):
            self.rolled_back = True
            proposal.status = AIActionProposalStatus.PENDING
            proposal.confirmation_key = None
            proposal.executed_at = None

        async def commit(self):
            return None

        async def refresh(self, _instance: Any):
            return None

    db = FakeSession()

    class ExpiringActor:
        def __init__(self):
            self.organization_id = organization_id
            self.role = UserRole.HR_MANAGER

        @property
        def id(self):
            if db.rolled_back:
                raise MissingGreenlet("expired actor requires implicit database I/O")
            return actor_id

    unused: Any = None
    service = AIActionService(cast(Any, db), unused, unused, unused, unused)

    async def fail_execution(*_args: Any, **_kwargs: Any):
        raise RuntimeError("database action failed")

    service._execute = fail_execution  # type: ignore[method-assign]

    with pytest.raises(HTTPException) as error:
        await service.confirm(
            proposal.id,
            cast(User, ExpiringActor()),
            "test-confirmation-key",
            "https://example.test",
        )

    assert error.value.status_code == 500
    assert error.value.detail == "Action execution failed"
    assert proposal.status == AIActionProposalStatus.FAILED


def test_system_prompt_locks_scope_and_approval_semantics():
    unused: Any = None
    service = AIConversationService(
        unused,
        cast(AIProvider, DummyProvider()),
        make_tool_service(),
    )
    conversation = cast(
        AIConversation,
        SimpleNamespace(mode=AIConversationMode.ACTION_MODE),
    )
    prompt = service._system_instruction(conversation)
    assert "HRX-supported workflows" in prompt
    assert "Semantic search" in prompt
    assert "shortlist application" in prompt
    assert "New jobs must always be created inactive" in prompt
    assert "never claim a proposal" in prompt.lower()
    assert "explicit confirmation" in prompt.lower()


def test_recruiting_chunking_has_overlap_and_no_empty_chunks():
    unused: Any = None
    index_service = KnowledgeIndexService(
        unused,
        cast(AIProvider, DummyProvider()),
    )
    text = " ".join(f"skill-{index}" for index in range(1000))
    chunks = index_service._chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 2
    assert all(chunk.strip() for chunk in chunks)
    assert len(chunks[0]) <= 500


def test_vector_dimension_and_tenant_column_are_fixed():
    embedding_type: Any = AIKnowledgeChunk.__table__.c.embedding.type
    assert embedding_type.dim == 768
    assert AIKnowledgeChunk.__table__.c.organization_id.nullable is False
    with pytest.raises(ValueError):
        XkiroAIProvider(api_key="test", embedding_dimensions=1536)


def test_mutations_are_mapped_to_ambiguous_result_types():
    unused: Any = None
    service = AIConversationService(
        unused,
        cast(AIProvider, DummyProvider()),
        make_tool_service(),
    )
    assert service._mutation_target_kind("propose_update_job") == "jobs"
    assert (
        service._mutation_target_kind("propose_change_application_status")
        == "applications"
    )
    assert service._mutation_target_kind("propose_create_job_draft") is None


def test_organization_timezone_uses_iana_validation():
    assert OrganizationUpdate(timezone="Asia/Karachi").timezone == "Asia/Karachi"
    with pytest.raises(ValidationError):
        OrganizationUpdate(timezone="Not/A-Timezone")


def test_bulk_job_tools_are_available_to_hr_in_action_mode():
    names = {
        definition.name
        for definition in make_tool_service().definitions(
            AIConversationMode.ACTION_MODE,
            user(UserRole.HR_MANAGER),
        )
    }

    assert "propose_set_jobs_active" in names
    assert "propose_delete_jobs" in names


def test_bulk_job_params_accept_many_ids_and_reject_empty_lists():
    ids = [uuid4() for _ in range(3)]
    assert SetJobsActiveParams(job_ids=ids, is_active=True).is_active is True
    assert JobIdsParams(job_ids=ids).job_ids == ids

    with pytest.raises(ValidationError):
        JobIdsParams(job_ids=[])
    with pytest.raises(ValidationError):
        JobIdsParams(job_ids=[uuid4() for _ in range(AI_AGENT_MAX_BULK_TARGETS + 1)])


def test_bulk_job_tools_are_not_blocked_by_ambiguous_matches():
    unused: Any = None
    service = AIConversationService(
        unused,
        cast(AIProvider, DummyProvider()),
        make_tool_service(),
    )

    assert service._mutation_target_kind("propose_set_jobs_active") is None
    assert service._mutation_target_kind("propose_delete_jobs") is None
    assert service._mutation_target_kind("propose_update_job") == "jobs"


@pytest.mark.asyncio
async def test_bulk_activation_updates_every_selected_job():
    jobs = [
        SimpleNamespace(id=uuid4(), title="Backend Engineer", updated_at=None),
        SimpleNamespace(id=uuid4(), title="Designer", updated_at=None),
    ]
    job_service = SimpleNamespace(
        get_organization_job=AsyncMock(side_effect=list(jobs)),
        update_job=AsyncMock(
            side_effect=[
                SimpleNamespace(id=job.id, title=job.title, is_active=True)
                for job in jobs
            ]
        ),
    )
    unused: Any = None
    service = AIActionService(unused, cast(Any, job_service), unused, unused, unused)
    proposal = SimpleNamespace(
        operation="set_jobs_active",
        arguments={
            "job_ids": [str(job.id) for job in jobs],
            "is_active": True,
            "expected_updated_at": {},
        },
    )

    result = await service._execute(
        cast(Any, proposal),
        user(UserRole.HR_MANAGER),
        "https://example.test",
    )

    assert [item["is_active"] for item in result] == [True, True]
    assert job_service.update_job.await_count == 2
    assert all(
        call.args[1].is_active is True
        for call in job_service.update_job.await_args_list
    )


@pytest.mark.asyncio
async def test_bulk_delete_removes_every_selected_job():
    jobs = [SimpleNamespace(id=uuid4(), title=f"Job {index}") for index in range(3)]
    job_service = SimpleNamespace(
        get_organization_job=AsyncMock(side_effect=list(jobs)),
        delete_job=AsyncMock(return_value=None),
    )
    unused: Any = None
    service = AIActionService(unused, cast(Any, job_service), unused, unused, unused)
    proposal = SimpleNamespace(
        operation="delete_jobs",
        arguments={"job_ids": [str(job.id) for job in jobs]},
    )

    result = await service._execute(
        cast(Any, proposal),
        user(UserRole.ORG_ADMIN),
        "https://example.test",
    )

    assert job_service.delete_job.await_count == 3
    assert [item["title"] for item in result] == ["Job 0", "Job 1", "Job 2"]


@pytest.mark.asyncio
async def test_bulk_job_action_rejects_a_target_changed_after_proposal():
    job = SimpleNamespace(
        id=uuid4(),
        title="Backend Engineer",
        updated_at=datetime(2026, 9, 14, 10, 0, tzinfo=UTC),
    )
    job_service = SimpleNamespace(get_organization_job=AsyncMock(return_value=job))
    unused: Any = None
    service = AIActionService(unused, cast(Any, job_service), unused, unused, unused)
    proposal = SimpleNamespace(
        operation="delete_jobs",
        arguments={
            "job_ids": [str(job.id)],
            "expected_updated_at": {
                str(job.id): datetime(2026, 9, 14, 9, 0, tzinfo=UTC).isoformat()
            },
        },
    )

    with pytest.raises(HTTPException) as error:
        await service._execute(
            cast(Any, proposal),
            user(UserRole.ORG_ADMIN),
            "https://example.test",
        )

    assert error.value.status_code == 409


def test_system_prompt_allows_bulk_actions_and_names_the_user():
    unused: Any = None
    service = AIConversationService(
        unused,
        cast(AIProvider, DummyProvider()),
        make_tool_service(),
    )
    conversation = cast(
        AIConversation,
        SimpleNamespace(mode=AIConversationMode.ACTION_MODE),
    )

    named = service._system_instruction(
        conversation,
        speaker={"name": "Zain Ashraf", "role": "HR manager"},
    )
    assert "Zain Ashraf" in named
    assert "“Hi Zain”" in named

    anonymous = service._system_instruction(
        conversation,
        speaker={"name": "", "role": "organization admin"},
    )
    assert "“Hi organization admin”" in anonymous

    assert "Do not refuse or lecture" in named
    assert "one bulk proposal" in named
    assert "one record at a time" in named
    assert "exactly one mutation per turn" not in named
    assert str(AI_AGENT_MAX_PROPOSALS_PER_TURN) in named


@pytest.mark.asyncio
async def test_speaker_falls_back_to_the_employee_record_then_role():
    class Rows:
        def __init__(self, row: Any):
            self.row = row

        def first(self):
            return self.row

    db = SimpleNamespace(execute=AsyncMock(return_value=Rows(("Zain", "Ashraf"))))
    service = AIConversationService(
        cast(Any, db),
        cast(AIProvider, DummyProvider()),
        make_tool_service(),
    )

    assert await service._speaker(user(UserRole.HR_MANAGER, "Zain Ashraf")) == {
        "name": "Zain Ashraf",
        "role": "HR manager",
    }
    assert await service._speaker(user(UserRole.HR_MANAGER)) == {
        "name": "Zain Ashraf",
        "role": "HR manager",
    }

    db.execute = AsyncMock(return_value=Rows(None))
    assert await service._speaker(user(UserRole.ORG_ADMIN)) == {
        "name": "",
        "role": "organization admin",
    }


def test_multiple_proposals_per_turn_are_allowed_up_to_the_cap():
    source = pathlib.Path("app/services/ai/conversation_service.py").read_text()

    assert AI_AGENT_MAX_PROPOSALS_PER_TURN > 1
    assert "Only one mutation can be proposed per turn" not in source
    assert "proposals_made >= AI_AGENT_MAX_PROPOSALS_PER_TURN" in source
