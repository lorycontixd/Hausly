"""004 create expense tables

Revision ID: 004_expenses
Revises: 003_grocery
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "004_expenses"
down_revision: str = "003_grocery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enum types
expensestatus_type = PG_ENUM(
    "draft", "confirmed", name="expensestatus", create_type=False
)
expensesource_type = PG_ENUM(
    "manual", "grocery_integration", "recurring_auto", name="expensesource", create_type=False
)


def upgrade() -> None:
    # Create enum types
    op.execute("DROP TYPE IF EXISTS expensestatus")
    op.execute("DROP TYPE IF EXISTS expensesource")
    op.execute("CREATE TYPE expensestatus AS ENUM ('draft', 'confirmed')")
    op.execute("CREATE TYPE expensesource AS ENUM ('manual', 'grocery_integration', 'recurring_auto')")

    # Expenses table
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("paid_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("recurrence_rule", sa.String(), nullable=True),
        sa.Column("next_occurrence_date", sa.Date(), nullable=True),
        sa.Column("status", expensestatus_type, nullable=False, server_default="draft"),
        sa.Column("source", expensesource_type, nullable=False, server_default="manual"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["paid_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_expenses_household_id", "expenses", ["household_id"])
    op.create_index("ix_expenses_status", "expenses", ["household_id", "status"])
    op.create_index("ix_expenses_created_at", "expenses", ["household_id", "created_at"])

    # Expense splits table
    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("expense_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("share_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_settled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_expense_splits_expense_id", "expense_splits", ["expense_id"])
    op.create_index("ix_expense_splits_household_id", "expense_splits", ["household_id"])
    op.create_index("ix_expense_splits_user_id", "expense_splits", ["user_id"])

    # RLS policies
    op.execute("ALTER TABLE expenses ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY expenses_household_isolation ON expenses "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )
    op.execute("ALTER TABLE expense_splits ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY expense_splits_household_isolation ON expense_splits "
        "USING (household_id = current_setting('app.current_household_id')::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS expense_splits_household_isolation ON expense_splits")
    op.execute("ALTER TABLE expense_splits DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS expenses_household_isolation ON expenses")
    op.execute("ALTER TABLE expenses DISABLE ROW LEVEL SECURITY")

    op.drop_table("expense_splits")
    op.drop_table("expenses")

    op.execute("DROP TYPE IF EXISTS expensesource")
    op.execute("DROP TYPE IF EXISTS expensestatus")
