"""007 add unique constraint to chore_assignments

Revision ID: 007_chore_assignment_unique
Revises: 006_chores
Create Date: 2026-06-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_chore_assignment_unique"
down_revision: str = "006_chores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove any existing duplicates before adding the constraint
    op.execute("""
        DELETE FROM chore_assignments
        WHERE id NOT IN (
            SELECT DISTINCT ON (chore_id, due_date, assigned_to_user_id) id
            FROM chore_assignments
            ORDER BY chore_id, due_date, assigned_to_user_id, created_at ASC
        )
    """)

    op.create_unique_constraint(
        "uq_chore_assignment_chore_date_user",
        "chore_assignments",
        ["chore_id", "due_date", "assigned_to_user_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_chore_assignment_chore_date_user",
        "chore_assignments",
        type_="unique",
    )
