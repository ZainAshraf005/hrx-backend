"""create job applications

Revision ID: d7e9c1b2a4f6
Revises: f2b8c4d9a1e3
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d7e9c1b2a4f6"
down_revision: Union[str, Sequence[str], None] = "f2b8c4d9a1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_applications",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("candidate_name", sa.String(), nullable=False),
        sa.Column("candidate_email", sa.String(), nullable=False),
        sa.Column("candidate_phone", sa.String(), nullable=True),
        sa.Column("candidate_location", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("portfolio_url", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("resume_file_name", sa.String(), nullable=True),
        sa.Column("resume_content_type", sa.String(), nullable=True),
        sa.Column("parsed_resume", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "candidate_email", name="uq_job_applications_job_email"),
    )
    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_job_applications_candidate_email"), ["candidate_email"], unique=False)
        batch_op.create_index(batch_op.f("ix_job_applications_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_job_applications_organization_id"), ["organization_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_job_applications_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("job_applications", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_applications_status"))
        batch_op.drop_index(batch_op.f("ix_job_applications_organization_id"))
        batch_op.drop_index(batch_op.f("ix_job_applications_job_id"))
        batch_op.drop_index(batch_op.f("ix_job_applications_candidate_email"))
    op.drop_table("job_applications")
