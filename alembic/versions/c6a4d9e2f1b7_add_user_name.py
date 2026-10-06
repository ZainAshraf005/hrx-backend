"""add user name

Revision ID: c6a4d9e2f1b7
Revises: b8e4f1a2c6d9
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6a4d9e2f1b7"
down_revision: str | Sequence[str] | None = "b8e4f1a2c6d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("name", sa.String(), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "name")
