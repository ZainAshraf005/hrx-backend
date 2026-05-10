"""add organization invites

Revision ID: b4a2d4f8c7e1
Revises: 3b15ede4db92
Create Date: 2026-05-09 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4a2d4f8c7e1"
down_revision: Union[str, Sequence[str], None] = "3b15ede4db92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_invites",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("otp_hash", sa.String(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("organization_invites", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_organization_invites_email"), ["email"], unique=False)
        batch_op.create_index(
            "ix_organization_invites_lookup",
            ["email", "organization_id", "is_used", "expires_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("organization_invites", schema=None) as batch_op:
        batch_op.drop_index("ix_organization_invites_lookup")
        batch_op.drop_index(batch_op.f("ix_organization_invites_email"))
    op.drop_table("organization_invites")
