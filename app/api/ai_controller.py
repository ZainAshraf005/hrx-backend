from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import StreamingResponse

from app.core.frontend_url import get_frontend_url_from_request
from app.dependencies.auth import require_roles
from app.dependencies.services import (
    get_ai_action_service,
    get_ai_conversation_service,
)
from app.models.user.user_model import User
from app.schemas.ai_schema import (
    AIActionAuditResponse,
    AIActionProposalResponse,
    AIConversationCreate,
    AIConversationDetail,
    AIConversationModeUpdate,
    AIConversationResponse,
    AITurnRequest,
)
from app.services.ai.action_service import AIActionService
from app.services.ai.conversation_service import AIConversationService
from app.services.job_application_service import rerank_job_applications_for_job


router = APIRouter(prefix="/ai", tags=["ai-agent"])
agent_user = require_roles("org_admin", "hr_manager")


@router.get("/audits", response_model=list[AIActionAuditResponse])
async def list_ai_action_audits(
    limit: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_roles("org_admin")),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    return await service.list_audits(current_user, limit)


@router.post("/conversations", response_model=AIConversationResponse)
async def create_ai_conversation(
    payload: AIConversationCreate,
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    return await service.create(payload, current_user)


@router.get("/conversations", response_model=list[AIConversationResponse])
async def list_ai_conversations(
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    return await service.list(current_user)


@router.get("/conversations/{conversation_id}", response_model=AIConversationDetail)
async def get_ai_conversation(
    conversation_id: UUID,
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    return await service.get(conversation_id, current_user, include_messages=True)


@router.patch(
    "/conversations/{conversation_id}/mode",
    response_model=AIConversationResponse,
)
async def change_ai_conversation_mode(
    conversation_id: UUID,
    payload: AIConversationModeUpdate,
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    return await service.change_mode(conversation_id, payload.mode, current_user)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ai_conversation(
    conversation_id: UUID,
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    await service.delete(conversation_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/conversations/{conversation_id}/turns")
async def stream_ai_turn(
    conversation_id: UUID,
    payload: AITurnRequest,
    current_user: User = Depends(agent_user),
    service: AIConversationService = Depends(get_ai_conversation_service),
):
    conversation, user_message, assistant_message = await service.start_turn(
        conversation_id,
        payload.message,
        payload.expected_mode,
        current_user,
    )
    return StreamingResponse(
        service.stream_turn(
            conversation,
            user_message,
            assistant_message,
            current_user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/action-proposals/{proposal_id}/confirm",
    response_model=AIActionProposalResponse,
)
async def confirm_ai_action(
    proposal_id: UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    current_user: User = Depends(agent_user),
    service: AIActionService = Depends(get_ai_action_service),
):
    proposal = await service.confirm(
        proposal_id,
        current_user,
        idempotency_key,
        get_frontend_url_from_request(request),
    )
    if proposal.operation == "update_job" and proposal.resource_id:
        background_tasks.add_task(
            rerank_job_applications_for_job,
            proposal.resource_id,
        )
    return proposal


@router.post(
    "/action-proposals/{proposal_id}/cancel",
    response_model=AIActionProposalResponse,
)
async def cancel_ai_action(
    proposal_id: UUID,
    current_user: User = Depends(agent_user),
    service: AIActionService = Depends(get_ai_action_service),
):
    return await service.cancel(proposal_id, current_user)
