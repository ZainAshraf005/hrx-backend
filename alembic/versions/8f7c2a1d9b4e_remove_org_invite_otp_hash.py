"""remove org invite otp hash

Revision ID: 8f7c2a1d9b4e
Revises: e1d4a8c2b7f9
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f7c2a1d9b4e"
down_revision: Union[str, Sequence[str], None] = "e1d4a8c2b7f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organization_invites", schema=None) as batch_op:
        batch_op.drop_column("otp_hash")


def downgrade() -> None:
    with op.batch_alter_table("organization_invites", schema=None) as batch_op:
        batch_op.add_column(sa.Column("otp_hash", sa.String(), server_default="", nullable=False))
        batch_op.alter_column("otp_hash", server_default=None)
