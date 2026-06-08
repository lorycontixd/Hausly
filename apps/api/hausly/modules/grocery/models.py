import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class ItemSource(str, enum.Enum):
    manual = "manual"
    meal_plan = "meal_plan"
    ai_suggestion = "ai_suggestion"


class PersonalVisibility(str, enum.Enum):
    visible = "visible"
    hidden = "hidden"


class GroceryList(SQLModel, table=True):
    __tablename__ = "grocery_lists"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    name: str = Field(default="Shopping List")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
    archived_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    items: list["GroceryItem"] = Relationship(back_populates="grocery_list")


class GroceryItem(SQLModel, table=True):
    __tablename__ = "grocery_items"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    list_id: uuid.UUID = Field(foreign_key="grocery_lists.id", index=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    name: str
    quantity: float | None = None
    unit: str | None = None
    is_bought: bool = Field(default=False)
    bought_by_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    bought_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    added_by_user_id: uuid.UUID = Field(foreign_key="users.id")
    source: ItemSource = Field(default=ItemSource.manual)
    is_personal: bool = Field(default=False)
    personal_for_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    personal_visibility: PersonalVisibility = Field(
        default=PersonalVisibility.visible
    )
    is_archived: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    grocery_list: Optional[GroceryList] = Relationship(back_populates="items")
