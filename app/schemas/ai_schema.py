from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AIActionProposalStatus,
    AIConversationMode,
    AIMessageRole,
    AIMessageStatus,
)


class AIConversationCreate(BaseModel):
    mode: AIConversationMode = AIConversationMode.READ_MODE
    title: str | None = Field(default=None, max_length=200)


class AIConversationModeUpdate(BaseModel):
    mode: AIConversationMode


class AITurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    expected_mode: AIConversationMode


class AIMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: AIMessageRole
    status: AIMessageStatus
    content: str
    structured_results: list[dict[str, Any]] | None = None
    model: str | None = None
    error: str | None = None
    created_at: datetime


class AIConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID
    title: str | None = None
    mode: AIConversationMode
    created_at: datetime
    updated_at: datetime


class AIConversationDetail(AIConversationResponse):
    messages: list[AIMessageResponse] = Field(default_factory=list)


class AIActionProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    operation: str
    preview: dict[str, Any]
    resource_type: str | None = None
    resource_id: UUID | None = None
    status: AIActionProposalStatus
    expires_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime


class AIActionAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    conversation_id: UUID | None
    proposal_id: UUID | None
    event_type: str
    operation: str | None
    resource_type: str | None
    resource_id: UUID | None
    details: dict[str, Any]
    created_at: datetime
