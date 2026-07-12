"""add candidate rankings

Revision ID: 7c3a9f1b2d5e
Revises: e4f2a9c8d1b5
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "7c3a9f1b2d5e"
down_revision: Union[str, Sequence[str], None] = "e4f2a9c8d1b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE candidate_ranking_recommendation AS ENUM "
        "('strong_match', 'possible_match', 'not_recommended')"
    )
    op.execute("CREATE TYPE candidate_ranking_status AS ENUM ('pending', 'completed', 'failed')")

    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ranking_score", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "ranking_recommendation",
                sa.Enum(
                    "strong_match",
                    "possible_match",
                    "not_recommended",
                    name="candidate_ranking_recommendation",
                    create_type=False,
                ),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("ranking_rationale", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ranking_strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column("ranking_gaps", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(
            sa.Column(
                "ranking_status",
                sa.Enum("pending", "completed", "failed", name="candidate_ranking_status", create_type=False),
                server_default="pending",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("ranking_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ranked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_job_applications_ranking_status"), ["ranking_status"], unique=False)
        batch_op.create_index(
            "ix_job_applications_job_id_ranking_score",
            ["job_id", "ranking_score"],
            unique=False,
        )

    op.alter_column("job_applications", "ranking_status", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        batch_op.drop_index("ix_job_applications_job_id_ranking_score")
        batch_op.drop_index(batch_op.f("ix_job_applications_ranking_status"))
        batch_op.drop_column("ranked_at")
        batch_op.drop_column("ranking_error")
        batch_op.drop_column("ranking_status")
        batch_op.drop_column("ranking_gaps")
        batch_op.drop_column("ranking_strengths")
        batch_op.drop_column("ranking_rationale")
        batch_op.drop_column("ranking_recommendation")
        batch_op.drop_column("ranking_score")

    op.execute("DROP TYPE candidate_ranking_status")
    op.execute("DROP TYPE candidate_ranking_recommendation")
