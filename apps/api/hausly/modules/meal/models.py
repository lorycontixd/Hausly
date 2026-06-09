import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class MealSlot(str, enum.Enum):
    lunch = "lunch"
    dinner = "dinner"


class MealPlanEntry(SQLModel, table=True):
    __tablename__ = "meal_plan_entries"
    __table_args__ = (
        sa.UniqueConstraint(
            "household_id", "date", "slot", name="uq_meal_slot_per_day"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    date: datetime = Field(sa_type=sa.Date(), nullable=False)
    slot: MealSlot
    text: str
    headcount: int
    linked_recipe_id: uuid.UUID | None = Field(default=None)
    owner_user_id: uuid.UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
