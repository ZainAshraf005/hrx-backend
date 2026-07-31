from datetime import datetime
from typing import Any
from uuid import UUID as PyUUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import BaseModel
from app.models.enums import (
    AIActionProposalStatus,
    AIConversationMode,
    AIIndexTaskStatus,
    AIKnowledgeSourceType,
    AIMessageRole,
    AIMessageStatus,
    enum_values,
)


class AIConversation(BaseModel):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        Index("ix_ai_conversations_owner_created", "user_id", "created_at"),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mode: Mapped[AIConversationMode] = mapped_column(
        SAEnum(AIConversationMode, values_callable=enum_values, name="ai_conversation_mode"),
        nullable=False,
        default=AIConversationMode.READ_MODE,
    )

    messages: Mapped[list[AIMessage]] = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    proposals: Mapped[list[AIActionProposal]] = relationship(
        "AIActionProposal",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AIMessage(BaseModel):
    __tablename__ = "ai_messages"
    __table_args__ = (
        Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[AIMessageRole] = mapped_column(
        SAEnum(AIMessageRole, values_callable=enum_values, name="ai_message_role"),
        nullable=False,
    )
    status: Mapped[AIMessageStatus] = mapped_column(
        SAEnum(AIMessageStatus, values_callable=enum_values, name="ai_message_status"),
        nullable=False,
        default=AIMessageStatus.COMPLETED,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    structured_results: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[AIConversation] = relationship(
        "AIConversation",
        back_populates="messages",
    )


class AIActionProposal(BaseModel):
    __tablename__ = "ai_action_proposals"

    conversation_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposed_by_user_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preview: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expected_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[AIActionProposalStatus] = mapped_column(
        SAEnum(
            AIActionProposalStatus,
            values_callable=enum_values,
            name="ai_action_proposal_status",
        ),
        nullable=False,
        default=AIActionProposalStatus.PENDING,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    confirmation_key: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        unique=True,
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    conversation: Mapped[AIConversation] = relationship(
        "AIConversation",
        back_populates="proposals",
    )


class AIActionAudit(BaseModel):
    __tablename__ = "ai_action_audits"
    __table_args__ = (
        Index("ix_ai_action_audits_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposal_id: Mapped[PyUUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operation: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    resource_id: Mapped[PyUUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )


class AIKnowledgeChunk(BaseModel):
    __tablename__ = "ai_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_ai_knowledge_source_chunk",
        ),
        Index("ix_ai_knowledge_org_source", "organization_id", "source_type", "source_id"),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[AIKnowledgeSourceType] = mapped_column(
        SAEnum(
            AIKnowledgeSourceType,
            values_callable=enum_values,
            name="ai_knowledge_source_type",
        ),
        nullable=False,
        index=True,
    )
    source_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)


class AIIndexTask(BaseModel):
    __tablename__ = "ai_index_tasks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_ai_index_task_source"),
        Index("ix_ai_index_tasks_ready", "status", "available_at"),
    )

    organization_id: Mapped[PyUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[AIKnowledgeSourceType] = mapped_column(
        SAEnum(
            AIKnowledgeSourceType,
            values_callable=enum_values,
            name="ai_index_task_source_type",
        ),
        nullable=False,
    )
    source_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[AIIndexTaskStatus] = mapped_column(
        SAEnum(AIIndexTaskStatus, values_callable=enum_values, name="ai_index_task_status"),
        nullable=False,
        default=AIIndexTaskStatus.PENDING,
        index=True,
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    claimed_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
