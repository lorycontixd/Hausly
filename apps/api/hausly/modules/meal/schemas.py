import uuid
from datetime import date, datetime

from hausly.modules.meal.models import MealSlot
from pydantic import BaseModel


class MealEntryCreate(BaseModel):
    date: date
    slot: MealSlot
    text: str
    headcount: int | None = None


class MealEntryUpdate(BaseModel):
    text: str | None = None
    headcount: int | None = None


class MealEntryResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    date: date
    slot: MealSlot
    text: str
    headcount: int
    linked_recipe_id: uuid.UUID | None
    owner_user_id: uuid.UUID
    owner_display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
