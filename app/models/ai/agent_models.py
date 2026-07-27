from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

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

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=True)
    mode = Column(
        SAEnum(AIConversationMode, values_callable=enum_values, name="ai_conversation_mode"),
        nullable=False,
        default=AIConversationMode.READ_MODE,
    )

    messages = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    proposals = relationship(
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

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        SAEnum(AIMessageRole, values_callable=enum_values, name="ai_message_role"),
        nullable=False,
    )
    status = Column(
        SAEnum(AIMessageStatus, values_callable=enum_values, name="ai_message_status"),
        nullable=False,
        default=AIMessageStatus.COMPLETED,
    )
    content = Column(Text, nullable=False, default="")
    structured_results = Column(JSONB, nullable=True)
    model = Column(String(120), nullable=True)
    error = Column(Text, nullable=True)

    conversation = relationship("AIConversation", back_populates="messages")


class AIActionProposal(BaseModel):
    __tablename__ = "ai_action_proposals"

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation = Column(String(80), nullable=False, index=True)
    arguments = Column(JSONB, nullable=False)
    preview = Column(JSONB, nullable=False)
    resource_type = Column(String(80), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    expected_updated_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(
        SAEnum(
            AIActionProposalStatus,
            values_callable=enum_values,
            name="ai_action_proposal_status",
        ),
        nullable=False,
        default=AIActionProposalStatus.PENDING,
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    confirmation_key = Column(String(200), nullable=True, unique=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)

    conversation = relationship("AIConversation", back_populates="proposals")


class AIActionAudit(BaseModel):
    __tablename__ = "ai_action_audits"
    __table_args__ = (
        Index("ix_ai_action_audits_org_created", "organization_id", "created_at"),
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposal_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    operation = Column(String(80), nullable=True)
    resource_type = Column(String(80), nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)


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

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(
        SAEnum(
            AIKnowledgeSourceType,
            values_callable=enum_values,
            name="ai_knowledge_source_type",
        ),
        nullable=False,
        index=True,
    )
    source_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    source_metadata = Column(JSONB, nullable=False, default=dict)
    content_hash = Column(String(64), nullable=False, index=True)
    embedding_model = Column(String(120), nullable=False)
    embedding = Column(Vector(768), nullable=False)


class AIIndexTask(BaseModel):
    __tablename__ = "ai_index_tasks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_ai_index_task_source"),
        Index("ix_ai_index_tasks_ready", "status", "available_at"),
    )

    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type = Column(
        SAEnum(
            AIKnowledgeSourceType,
            values_callable=enum_values,
            name="ai_index_task_source_type",
        ),
        nullable=False,
    )
    source_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(
        SAEnum(AIIndexTaskStatus, values_callable=enum_values, name="ai_index_task_status"),
        nullable=False,
        default=AIIndexTaskStatus.PENDING,
        index=True,
    )
    generation = Column(Integer, nullable=False, default=1)
    claimed_generation = Column(Integer, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime(timezone=True), nullable=False)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
