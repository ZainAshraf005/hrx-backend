"""convert choice strings to enums

Revision ID: e4f2a9c8d1b5
Revises: d7e9c1b2a4f6
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e4f2a9c8d1b5"
down_revision: Union[str, Sequence[str], None] = "d7e9c1b2a4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE user_role AS ENUM ('superadmin', 'org_admin', 'hr_manager', 'employee')")
    op.execute("CREATE TYPE job_employment_type AS ENUM ('full_time', 'part_time', 'contract', 'internship', 'temporary')")
    op.execute("CREATE TYPE job_workplace_type AS ENUM ('onsite', 'remote', 'hybrid')")
    op.execute("CREATE TYPE job_status AS ENUM ('draft', 'open', 'closed')")
    op.execute("CREATE TYPE salary_period AS ENUM ('hourly', 'monthly', 'yearly')")
    op.execute("CREATE TYPE job_application_status AS ENUM ('submitted', 'reviewing', 'shortlisted', 'rejected', 'hired')")

    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::text::user_role"
    )
    op.execute(
        "ALTER TABLE organization_invites ALTER COLUMN role TYPE user_role USING role::text::user_role"
    )
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN employment_type TYPE job_employment_type "
        "USING employment_type::text::job_employment_type"
    )
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN workplace_type TYPE job_workplace_type "
        "USING workplace_type::text::job_workplace_type"
    )
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN status TYPE job_status USING status::text::job_status"
    )
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN salary_period TYPE salary_period "
        "USING salary_period::text::salary_period"
    )
    op.execute(
        "ALTER TABLE job_applications ALTER COLUMN status TYPE job_application_status "
        "USING status::text::job_application_status"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE job_applications ALTER COLUMN status TYPE VARCHAR USING status::text")
    op.execute("ALTER TABLE jobs ALTER COLUMN salary_period TYPE VARCHAR USING salary_period::text")
    op.execute("ALTER TABLE jobs ALTER COLUMN status TYPE VARCHAR USING status::text")
    op.execute("ALTER TABLE jobs ALTER COLUMN workplace_type TYPE VARCHAR USING workplace_type::text")
    op.execute("ALTER TABLE jobs ALTER COLUMN employment_type TYPE VARCHAR USING employment_type::text")
    op.execute("ALTER TABLE organization_invites ALTER COLUMN role TYPE VARCHAR USING role::text")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING role::text")

    op.execute("DROP TYPE job_application_status")
    op.execute("DROP TYPE salary_period")
    op.execute("DROP TYPE job_status")
    op.execute("DROP TYPE job_workplace_type")
    op.execute("DROP TYPE job_employment_type")
    op.execute("DROP TYPE user_role")
