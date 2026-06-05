"""002 create households tables

Revision ID: 002_households
Revises: 001_initial
Create Date: 2026-06-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_households"
down_revision: str = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Households table
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("couple", "friends", "students", "family", "custom", name="householdtype"),
            nullable=False,
        ),
        sa.Column("invite_code", sa.String(), nullable=False),
        sa.Column(
            "subscription_tier",
            sa.Enum("free", "paid", name="subscriptiontier"),
            nullable=False,
            server_default="free",
        ),
        sa.Column("subscription_owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["subscription_owner_id"], ["users.id"]),
        sa.UniqueConstraint("invite_code"),
    )

    # Household settings table (1:1 with households)
    op.create_table(
        "household_settings",
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("default_currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("enabled_modules", sa.ARRAY(sa.String()), nullable=False),
        sa.Column(
            "notification_level",
            sa.Enum("low", "medium", "high", name="notificationlevel"),
            nullable=False,
            server_default="medium",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("household_id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
    )

    # Household memberships table
    op.create_table(
        "household_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "member", name="memberrole"),
            nullable=False,
            server_default="member",
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(
        "ix_household_memberships_household_id",
        "household_memberships",
        ["household_id"],
    )
    op.create_index(
        "ix_household_memberships_user_id",
        "household_memberships",
        ["user_id"],
    )
    # Unique constraint: one active membership per user per household
    op.create_index(
        "ix_unique_active_membership",
        "household_memberships",
        ["household_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )

    # RLS policies (PostgreSQL-specific)
    op.execute("""
        ALTER TABLE households ENABLE ROW LEVEL SECURITY;
    """)
    op.execute("""
        ALTER TABLE household_settings ENABLE ROW LEVEL SECURITY;
    """)
    op.execute("""
        ALTER TABLE household_memberships ENABLE ROW LEVEL SECURITY;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE household_memberships DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE household_settings DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE households DISABLE ROW LEVEL SECURITY;")

    op.drop_index("ix_unique_active_membership", table_name="household_memberships")
    op.drop_index("ix_household_memberships_user_id", table_name="household_memberships")
    op.drop_index("ix_household_memberships_household_id", table_name="household_memberships")
    op.drop_table("household_memberships")
    op.drop_table("household_settings")
    op.drop_table("households")

    op.execute("DROP TYPE IF EXISTS memberrole;")
    op.execute("DROP TYPE IF EXISTS notificationlevel;")
    op.execute("DROP TYPE IF EXISTS subscriptiontier;")
    op.execute("DROP TYPE IF EXISTS householdtype;")
