"""006 create chore tables

Revision ID: 006_chores
Revises: 005_meals
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "006_chores"
down_revision: str = "005_meals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

recurrence_unit_type = PG_ENUM(
    "days", "weeks", "months", name="recurrenceunit", create_type=False
)
assignment_status_type = PG_ENUM(
    "pending", "completed", "cancelled", name="assignmentstatus", create_type=False
)


def upgrade() -> None:
    # Create enum types
    op.execute("DROP TYPE IF EXISTS recurrenceunit")
    op.execute("CREATE TYPE recurrenceunit AS ENUM ('days', 'weeks', 'months')")
    op.execute("DROP TYPE IF EXISTS assignmentstatus")
    op.execute(
        "CREATE TYPE assignmentstatus AS ENUM ('pending', 'completed', 'cancelled')"
    )

    # Chores table
    op.create_table(
        "chores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurrence_interval", sa.Integer(), nullable=True),
        sa.Column("recurrence_unit", recurrence_unit_type, nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column(
            "rotation_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_chores_household_id", "chores", ["household_id"])

    # Chore assignees table
    op.create_table(
        "chore_assignees",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chore_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["chore_id"], ["chores.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_chore_assignees_chore_id", "chore_assignees", ["chore_id"])
    op.create_index(
        "ix_chore_assignees_household_id", "chore_assignees", ["household_id"]
    )

    # Chore assignments table
    op.create_table(
        "chore_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chore_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("postponed_to", sa.Date(), nullable=True),
        sa.Column("status", assignment_status_type, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["chore_id"], ["chores.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_chore_assignments_chore_id", "chore_assignments", ["chore_id"]
    )
    op.create_index(
        "ix_chore_assignments_household_id", "chore_assignments", ["household_id"]
    )
    op.create_index(
        "ix_chore_assignments_due_date",
        "chore_assignments",
        ["household_id", "due_date"],
    )
    op.create_index(
        "ix_chore_assignments_status",
        "chore_assignments",
        ["chore_id", "status"],
    )

    # RLS policies
    op.execute("ALTER TABLE chores ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chores_household_isolation ON chores "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )

    op.execute("ALTER TABLE chore_assignees ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chore_assignees_household_isolation ON chore_assignees "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )

    op.execute("ALTER TABLE chore_assignments ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY chore_assignments_household_isolation ON chore_assignments "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS chore_assignments_household_isolation ON chore_assignments")
    op.execute("ALTER TABLE chore_assignments DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS chore_assignees_household_isolation ON chore_assignees")
    op.execute("ALTER TABLE chore_assignees DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS chores_household_isolation ON chores")
    op.execute("ALTER TABLE chores DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("chore_assignments")
    op.drop_table("chore_assignees")
    op.drop_table("chores")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS assignmentstatus")
    op.execute("DROP TYPE IF EXISTS recurrenceunit")
