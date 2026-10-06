"""allow superadmin without organization

Revision ID: c9f2a1d7e4b6
Revises: b4a2d4f8c7e1
Create Date: 2026-05-10 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9f2a1d7e4b6"
down_revision: str | Sequence[str] | None = "b4a2d4f8c7e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
