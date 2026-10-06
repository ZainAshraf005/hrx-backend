"""add ai agent conversations, actions, and vector index

Revision ID: 9a1b2c3d4e5f
Revises: 7c3a9f1b2d5e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "7c3a9f1b2d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE TYPE ai_conversation_mode AS ENUM ('read_mode', 'action_mode')")
    op.execute("CREATE TYPE ai_message_role AS ENUM ('user', 'assistant', 'tool')")
    op.execute(
        "CREATE TYPE ai_message_status AS ENUM "
        "('in_progress', 'completed', 'failed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE ai_action_proposal_status AS ENUM "
        "('pending', 'executed', 'cancelled', 'expired', 'failed')"
    )
    op.execute("CREATE TYPE ai_knowledge_source_type AS ENUM ('job', 'application')")
    op.execute(
        "CREATE TYPE ai_index_task_status AS ENUM "
        "('pending', 'processing', 'completed', 'failed')"
    )

    op.add_column(
        "organizations",
        sa.Column(
            "timezone",
            sa.String(),
            nullable=False,
            server_default="Asia/Karachi",
        ),
    )

    op.create_table(
        "ai_conversations",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "mode",
            postgresql.ENUM(
                "read_mode",
                "action_mode",
                name="ai_conversation_mode",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_conversations_organization_id", "ai_conversations", ["organization_id"])
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index(
        "ix_ai_conversations_owner_created",
        "ai_conversations",
        ["user_id", "created_at"],
    )

    op.create_table(
        "ai_messages",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "user",
                "assistant",
                "tool",
                name="ai_message_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="ai_message_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_results", postgresql.JSONB(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])
    op.create_index(
        "ix_ai_messages_conversation_created",
        "ai_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "ai_action_proposals",
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=False),
        sa.Column("arguments", postgresql.JSONB(), nullable=False),
        sa.Column("preview", postgresql.JSONB(), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expected_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "executed",
                "cancelled",
                "expired",
                "failed",
                name="ai_action_proposal_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmation_key", sa.String(length=200), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_by_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("confirmation_key"),
    )
    for column in (
        "conversation_id",
        "proposed_by_user_id",
        "organization_id",
        "operation",
        "status",
        "expires_at",
    ):
        op.create_index(f"ix_ai_action_proposals_{column}", "ai_action_proposals", [column])

    op.create_table(
        "ai_action_audits",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=80), nullable=True),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "organization_id",
        "actor_user_id",
        "proposal_id",
        "event_type",
    ):
        op.create_index(f"ix_ai_action_audits_{column}", "ai_action_audits", [column])
    op.create_index(
        "ix_ai_action_audits_org_created",
        "ai_action_audits",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "ai_knowledge_chunks",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "job",
                "application",
                name="ai_knowledge_source_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding", Vector(dim=768), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_ai_knowledge_source_chunk",
        ),
    )
    for column in ("organization_id", "source_type", "source_id", "content_hash"):
        op.create_index(f"ix_ai_knowledge_chunks_{column}", "ai_knowledge_chunks", [column])
    op.create_index(
        "ix_ai_knowledge_org_source",
        "ai_knowledge_chunks",
        ["organization_id", "source_type", "source_id"],
    )
    op.execute(
        "CREATE INDEX ix_ai_knowledge_embedding_hnsw "
        "ON ai_knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "ai_index_tasks",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "job",
                "application",
                name="ai_knowledge_source_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                name="ai_index_task_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("claimed_generation", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_ai_index_task_source"),
    )
    for column in ("organization_id", "status"):
        op.create_index(f"ix_ai_index_tasks_{column}", "ai_index_tasks", [column])
    op.create_index(
        "ix_ai_index_tasks_ready",
        "ai_index_tasks",
        ["status", "available_at"],
    )

    op.execute(
        """
        INSERT INTO ai_index_tasks (
            organization_id, source_type, source_id, status, generation, attempts,
            available_at, id, created_at, updated_at
        )
        SELECT organization_id, 'job'::ai_knowledge_source_type, id,
               'pending'::ai_index_task_status, 1, 0, now(),
               gen_random_uuid(), now(), now()
        FROM jobs
        """
    )
    op.execute(
        """
        INSERT INTO ai_index_tasks (
            organization_id, source_type, source_id, status, generation, attempts,
            available_at, id, created_at, updated_at
        )
        SELECT organization_id, 'application'::ai_knowledge_source_type, id,
               'pending'::ai_index_task_status, 1, 0, now(),
               gen_random_uuid(), now(), now()
        FROM job_applications
        """
    )


def downgrade() -> None:
    op.drop_table("ai_index_tasks")
    op.execute("DROP INDEX IF EXISTS ix_ai_knowledge_embedding_hnsw")
    op.drop_table("ai_knowledge_chunks")
    op.drop_table("ai_action_audits")
    op.drop_table("ai_action_proposals")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
    op.drop_column("organizations", "timezone")
    op.execute("DROP TYPE ai_index_task_status")
    op.execute("DROP TYPE ai_knowledge_source_type")
    op.execute("DROP TYPE ai_action_proposal_status")
    op.execute("DROP TYPE ai_message_status")
    op.execute("DROP TYPE ai_message_role")
    op.execute("DROP TYPE ai_conversation_mode")
