"""add password reset otps

Revision ID: a6d3f2c9e8b1
Revises: 8f7c2a1d9b4e
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6d3f2c9e8b1"
down_revision: Union[str, Sequence[str], None] = "8f7c2a1d9b4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_otps",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("otp_hash", sa.String(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("password_reset_otps", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_password_reset_otps_email"), ["email"], unique=False)
        batch_op.create_index(batch_op.f("ix_password_reset_otps_user_id"), ["user_id"], unique=False)
        batch_op.create_index(
            "ix_password_reset_otps_lookup",
            ["email", "is_used", "expires_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("password_reset_otps", schema=None) as batch_op:
        batch_op.drop_index("ix_password_reset_otps_lookup")
        batch_op.drop_index(batch_op.f("ix_password_reset_otps_user_id"))
        batch_op.drop_index(batch_op.f("ix_password_reset_otps_email"))
    op.drop_table("password_reset_otps")
