"""add attendance and leave management

Revision ID: b8e4f1a2c6d9
Revises: 9a1b2c3d4e5f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8e4f1a2c6d9"
down_revision: str | Sequence[str] | None = "9a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM users
                WHERE role = 'hr_manager'::user_role
                  AND is_active IS TRUE
                  AND organization_id IS NOT NULL
                GROUP BY organization_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot enforce one active HR manager: duplicate active HR managers exist';
            END IF;
        END
        $$;
        """
    )
    op.create_index(
        "uq_users_one_active_hr_per_organization",
        "users",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text(
            "role = 'hr_manager'::user_role AND is_active IS TRUE"
        ),
    )

    op.execute("CREATE TYPE leave_type AS ENUM ('sick', 'casual', 'annual', 'unpaid')")
    op.execute(
        "CREATE TYPE leave_status AS ENUM "
        "('pending', 'approved', 'rejected', 'withdrawn')"
    )

    op.create_table(
        "attendance_records",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "checkout_completed_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("checkout_completion_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "check_out_at IS NULL OR check_out_at > check_in_at",
            name="ck_attendance_checkout_after_checkin",
        ),
        sa.ForeignKeyConstraint(
            ["checkout_completed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employee_id",
            "work_date",
            name="uq_attendance_employee_work_date",
        ),
    )
    op.create_index(
        "ix_attendance_records_employee_id",
        "attendance_records",
        ["employee_id"],
    )
    op.create_index(
        "ix_attendance_records_work_date",
        "attendance_records",
        ["work_date"],
    )
    op.create_index(
        "ix_attendance_organization_work_date",
        "attendance_records",
        ["organization_id", "work_date"],
    )
    op.create_index(
        "uq_attendance_employee_open",
        "attendance_records",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("check_out_at IS NULL"),
    )

    op.create_table(
        "leave_requests",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "leave_type",
            postgresql.ENUM(
                "sick",
                "casual",
                "annual",
                "unpaid",
                name="leave_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "approved",
                "rejected",
                "withdrawn",
                name="leave_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status_changed_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_date >= start_date",
            name="ck_leave_end_on_or_after_start",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["status_changed_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_leave_requests_employee_id",
        "leave_requests",
        ["employee_id"],
    )
    op.create_index(
        "ix_leave_requests_status",
        "leave_requests",
        ["status"],
    )
    op.create_index(
        "ix_leave_organization_status",
        "leave_requests",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_leave_employee_dates",
        "leave_requests",
        ["employee_id", "start_date", "end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_leave_employee_dates", table_name="leave_requests")
    op.drop_index("ix_leave_organization_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_status", table_name="leave_requests")
    op.drop_index("ix_leave_requests_employee_id", table_name="leave_requests")
    op.drop_table("leave_requests")

    op.drop_index("uq_attendance_employee_open", table_name="attendance_records")
    op.drop_index(
        "ix_attendance_organization_work_date",
        table_name="attendance_records",
    )
    op.drop_index("ix_attendance_records_work_date", table_name="attendance_records")
    op.drop_index("ix_attendance_records_employee_id", table_name="attendance_records")
    op.drop_table("attendance_records")

    op.execute("DROP TYPE leave_status")
    op.execute("DROP TYPE leave_type")
    op.drop_index(
        "uq_users_one_active_hr_per_organization",
        table_name="users",
    )
