import uuid
from datetime import datetime

from hausly.modules.grocery.models import ItemSource, PersonalVisibility
from pydantic import BaseModel


class GroceryItemCreate(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None
    source: ItemSource = ItemSource.manual
    is_personal: bool = False
    personal_visibility: PersonalVisibility = PersonalVisibility.visible


class GroceryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    is_personal: bool | None = None
    personal_visibility: PersonalVisibility | None = None


class GroceryItemResponse(BaseModel):
    id: uuid.UUID
    list_id: uuid.UUID
    name: str
    quantity: float | None
    unit: str | None
    is_bought: bool
    bought_by_user_id: uuid.UUID | None
    bought_at: datetime | None
    added_by_user_id: uuid.UUID
    source: ItemSource
    is_personal: bool
    personal_for_user_id: uuid.UUID | None
    personal_visibility: PersonalVisibility
    created_at: datetime

    model_config = {"from_attributes": True}


class GroceryListResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class SessionCompleteRequest(BaseModel):
    bought_item_ids: list[uuid.UUID]
    receipt_total: float
    create_expense: bool = True


class SessionCompleteResponse(BaseModel):
    items_removed: int
    expense_draft_id: uuid.UUID | None = None
    expense_draft: dict | None = None


class ArchiveRequest(BaseModel):
    confirm: bool
