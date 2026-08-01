from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import MissingGreenlet

import main
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
from app.services.ai.provider import AIProvider, GeminiAIProvider
from app.services.ai.tool_schemas import (
    CreateJobDraftParams,
    InviteEmployeeParams,
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


def user(role: UserRole) -> User:
    return cast(
        User,
        SimpleNamespace(id=uuid4(), organization_id=uuid4(), role=role),
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

    hr_read = service.definitions(AIConversationMode.READ_MODE, user(UserRole.HR_MANAGER))
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


def test_tool_json_schemas_are_inlined_for_gemini():
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
    assert "New jobs must always be draft" in prompt
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
        GeminiAIProvider(api_key="test", embedding_dimensions=1536)


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
