import uuid
from datetime import date, datetime

from hausly.modules.chores.models import AssignmentStatus, RecurrenceUnit
from pydantic import BaseModel, model_validator


class ChoreCreate(BaseModel):
    name: str
    start_date: date
    is_recurring: bool = False
    recurrence_interval: int | None = None
    recurrence_unit: RecurrenceUnit | None = None
    assignee_user_ids: list[uuid.UUID]
    rotation_enabled: bool = False

    @model_validator(mode="after")
    def validate_recurrence(self) -> "ChoreCreate":
        if self.is_recurring:
            if self.recurrence_interval is None or self.recurrence_unit is None:
                msg = "recurrence_interval and recurrence_unit are required for recurring chores"
                raise ValueError(msg)
            if self.recurrence_interval < 1:
                msg = "recurrence_interval must be >= 1"
                raise ValueError(msg)
        return self


class ChoreUpdate(BaseModel):
    name: str | None = None
    recurrence_interval: int | None = None
    recurrence_unit: RecurrenceUnit | None = None
    assignee_user_ids: list[uuid.UUID] | None = None
    rotation_enabled: bool | None = None


class AssigneeResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    position: int

    model_config = {"from_attributes": True}


class ChoreResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    name: str
    created_by_user_id: uuid.UUID
    is_recurring: bool
    recurrence_interval: int | None
    recurrence_unit: RecurrenceUnit | None
    start_date: date
    rotation_enabled: bool
    is_active: bool
    created_at: datetime
    assignees: list[AssigneeResponse]

    model_config = {"from_attributes": True}


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    chore_id: uuid.UUID
    household_id: uuid.UUID
    assigned_to_user_id: uuid.UUID
    due_date: date
    postponed_to: date | None
    status: AssignmentStatus
    completed_at: datetime | None
    completed_by_user_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PostponeRequest(BaseModel):
    postpone_to: date

    @model_validator(mode="after")
    def validate_future_date(self) -> "PostponeRequest":
        if self.postpone_to <= date.today():
            msg = "postpone_to must be a future date"
            raise ValueError(msg)
        return self
