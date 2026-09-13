"""use is_active for job lifecycle

Revision ID: a4e6c8d0f2b1
Revises: d3a7f5c9b2e1
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a4e6c8d0f2b1"
down_revision: str | Sequence[str] | None = "d3a7f5c9b2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve the effective public state before dropping the duplicate field.
    # Draft and closed jobs become inactive; only previously open, active jobs
    # remain publicly visible.
    op.execute(
        "UPDATE jobs "
        "SET is_active = (COALESCE(is_active, TRUE) AND status = 'open'::job_status)"
    )
    op.alter_column(
        "jobs",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_column("jobs", "status")
    op.execute("DROP TYPE job_status")


def downgrade() -> None:
    op.execute("CREATE TYPE job_status AS ENUM ('draft', 'open', 'closed')")
    op.add_column(
        "jobs",
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "open",
                "closed",
                name="job_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'draft'::job_status"),
        ),
    )
    op.execute(
        "UPDATE jobs SET status = "
        "CASE WHEN is_active THEN 'open'::job_status ELSE 'draft'::job_status END"
    )
    op.create_index("ix_jobs_status", "jobs", ["status"], unique=False)
    op.alter_column(
        "jobs",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
