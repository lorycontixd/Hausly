"""003 create grocery tables

Revision ID: 003_grocery
Revises: 002_households
Create Date: 2026-06-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "003_grocery"
down_revision: str = "002_households"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Define enum types that will be created explicitly before the table
itemsource_type = PG_ENUM(
    "manual", "meal_plan", "ai_suggestion", name="itemsource", create_type=False
)
personalvisibility_type = PG_ENUM(
    "visible", "hidden", name="personalvisibility", create_type=False
)


def upgrade() -> None:
    # Grocery lists table
    op.create_table(
        "grocery_lists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default="Shopping List"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
    )
    op.create_index(
        "ix_grocery_lists_household_id",
        "grocery_lists",
        ["household_id"],
    )
    # Only one active list per household
    op.create_index(
        "ix_unique_active_grocery_list",
        "grocery_lists",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # Enum types — drop and recreate to ensure clean state
    op.execute("DROP TYPE IF EXISTS itemsource")
    op.execute("DROP TYPE IF EXISTS personalvisibility")
    op.execute("CREATE TYPE itemsource AS ENUM ('manual', 'meal_plan', 'ai_suggestion')")
    op.execute("CREATE TYPE personalvisibility AS ENUM ('visible', 'hidden')")

    # Grocery items table
    op.create_table(
        "grocery_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("list_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("is_bought", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("bought_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("bought_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source", itemsource_type, nullable=False, server_default="manual"),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("personal_for_user_id", sa.Uuid(), nullable=True),
        sa.Column("personal_visibility", personalvisibility_type, nullable=False, server_default="visible"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["list_id"], ["grocery_lists.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["bought_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["personal_for_user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_grocery_items_list_id",
        "grocery_items",
        ["list_id"],
    )
    op.create_index(
        "ix_grocery_items_household_id",
        "grocery_items",
        ["household_id"],
    )

    # RLS policies
    op.execute("ALTER TABLE grocery_lists ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE grocery_items ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE grocery_items DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE grocery_lists DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_grocery_items_household_id", table_name="grocery_items")
    op.drop_index("ix_grocery_items_list_id", table_name="grocery_items")
    op.drop_table("grocery_items")

    op.drop_index("ix_unique_active_grocery_list", table_name="grocery_lists")
    op.drop_index("ix_grocery_lists_household_id", table_name="grocery_lists")
    op.drop_table("grocery_lists")

    op.execute("DROP TYPE IF EXISTS personalvisibility;")
    op.execute("DROP TYPE IF EXISTS itemsource;")
