import enum
import uuid
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class RecurrenceUnit(str, enum.Enum):
    days = "days"
    weeks = "weeks"
    months = "months"


class AssignmentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class Chore(SQLModel, table=True):
    __tablename__ = "chores"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    name: str
    created_by_user_id: uuid.UUID = Field(foreign_key="users.id")
    is_recurring: bool = Field(default=False)
    recurrence_interval: int | None = None
    recurrence_unit: RecurrenceUnit | None = Field(
        default=None, sa_type=sa.Enum(RecurrenceUnit)
    )
    start_date: date = Field(sa_type=sa.Date())
    rotation_enabled: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    assignees: list["ChoreAssignee"] = Relationship(
        back_populates="chore",
        sa_relationship_kwargs={"lazy": "noload"},
    )
    assignments: list["ChoreAssignment"] = Relationship(
        back_populates="chore",
        sa_relationship_kwargs={"lazy": "noload"},
    )


class ChoreAssignee(SQLModel, table=True):
    __tablename__ = "chore_assignees"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chore_id: uuid.UUID = Field(foreign_key="chores.id", index=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    position: int = Field(default=0)

    chore: Chore | None = Relationship(
        back_populates="assignees",
        sa_relationship_kwargs={"lazy": "noload"},
    )


class ChoreAssignment(SQLModel, table=True):
    __tablename__ = "chore_assignments"
    __table_args__ = (
        sa.UniqueConstraint(
            "chore_id", "due_date", "assigned_to_user_id",
            name="uq_chore_assignment_chore_date_user",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chore_id: uuid.UUID = Field(foreign_key="chores.id", index=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    assigned_to_user_id: uuid.UUID = Field(foreign_key="users.id")
    due_date: date = Field(sa_type=sa.Date())
    postponed_to: date | None = Field(default=None, sa_type=sa.Date())
    status: AssignmentStatus = Field(default=AssignmentStatus.pending)
    completed_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    completed_by_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    chore: Chore | None = Relationship(
        back_populates="assignments",
        sa_relationship_kwargs={"lazy": "noload"},
    )
