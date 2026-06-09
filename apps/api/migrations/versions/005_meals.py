"""005 create meal plan entries table

Revision ID: 005_meals
Revises: 004_expenses
Create Date: 2026-06-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "005_meals"
down_revision: str = "004_expenses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

mealslot_type = PG_ENUM("lunch", "dinner", name="mealslot", create_type=False)


def upgrade() -> None:
    # Create enum type
    op.execute("DROP TYPE IF EXISTS mealslot")
    op.execute("CREATE TYPE mealslot AS ENUM ('lunch', 'dinner')")

    # Meal plan entries table
    op.create_table(
        "meal_plan_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("slot", mealslot_type, nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("headcount", sa.Integer(), nullable=False),
        sa.Column("linked_recipe_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.UniqueConstraint(
            "household_id", "date", "slot", name="uq_meal_slot_per_day"
        ),
    )
    op.create_index(
        "ix_meal_plan_entries_household_id",
        "meal_plan_entries",
        ["household_id"],
    )
    op.create_index(
        "ix_meal_plan_entries_date_range",
        "meal_plan_entries",
        ["household_id", "date"],
    )

    # RLS policy
    op.execute("ALTER TABLE meal_plan_entries ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY meal_plan_entries_household_isolation ON meal_plan_entries "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS meal_plan_entries_household_isolation ON meal_plan_entries"
    )
    op.execute("ALTER TABLE meal_plan_entries DISABLE ROW LEVEL SECURITY")

    op.drop_table("meal_plan_entries")

    op.execute("DROP TYPE IF EXISTS mealslot")
