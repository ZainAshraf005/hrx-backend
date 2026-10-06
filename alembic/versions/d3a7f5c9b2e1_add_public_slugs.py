"""add public slugs

Revision ID: d3a7f5c9b2e1
Revises: c6a4d9e2f1b7
Create Date: 2026-09-13 00:00:00.000000

"""

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d3a7f5c9b2e1"
down_revision: str | Sequence[str] | None = "c6a4d9e2f1b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG_MAX_LENGTH = 120


def _slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:SLUG_MAX_LENGTH].rstrip("-") or fallback


def _unique_slug(base: str, used: set[str]) -> str:
    if base not in used:
        used.add(base)
        return base

    suffix = 2
    while True:
        suffix_text = f"-{suffix}"
        trimmed = base[: SLUG_MAX_LENGTH - len(suffix_text)].rstrip("-")
        candidate = f"{trimmed}{suffix_text}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("slug", sa.String(length=SLUG_MAX_LENGTH), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("slug", sa.String(length=SLUG_MAX_LENGTH), nullable=True),
    )

    connection = op.get_bind()

    organization_slugs: set[str] = set()
    organizations = connection.execute(
        sa.text("SELECT id, name FROM organizations ORDER BY created_at, id")
    ).mappings()
    for organization in organizations:
        base = _slugify(organization["name"], "organization")
        slug = _unique_slug(base, organization_slugs)
        connection.execute(
            sa.text("UPDATE organizations SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": organization["id"]},
        )

    job_slugs_by_organization: dict[object, set[str]] = {}
    jobs = connection.execute(
        sa.text(
            "SELECT id, organization_id, title "
            "FROM jobs ORDER BY organization_id, created_at, id"
        )
    ).mappings()
    for job in jobs:
        used = job_slugs_by_organization.setdefault(job["organization_id"], set())
        base = _slugify(job["title"], "job")
        slug = _unique_slug(base, used)
        connection.execute(
            sa.text("UPDATE jobs SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": job["id"]},
        )

    op.alter_column("organizations", "slug", nullable=False)
    op.alter_column("jobs", "slug", nullable=False)
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_unique_constraint(
        "uq_jobs_organization_slug",
        "jobs",
        ["organization_id", "slug"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jobs_organization_slug", "jobs", type_="unique")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_column("jobs", "slug")
    op.drop_column("organizations", "slug")
