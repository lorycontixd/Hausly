import uuid
from datetime import datetime

from hausly.modules.household.models import (HouseholdType, MemberRole,
                                             NotificationLevel,
                                             SubscriptionTier)
from pydantic import BaseModel, Field


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: HouseholdType


class HouseholdUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: HouseholdType | None = None


class HouseholdSettingsUpdate(BaseModel):
    enabled_modules: list[str] | None = None
    default_currency: str | None = Field(default=None, min_length=3, max_length=3)
    notification_level: NotificationLevel | None = None


class MemberResponse(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    role: MemberRole
    joined_at: datetime


class HouseholdSettingsResponse(BaseModel):
    default_currency: str
    enabled_modules: list[str]
    notification_level: NotificationLevel


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: HouseholdType
    invite_code: str
    subscription_tier: SubscriptionTier
    created_at: datetime
    settings: HouseholdSettingsResponse
    members: list[MemberResponse]


class InvitePreviewResponse(BaseModel):
    household_name: str
    member_count: int
    type: HouseholdType


class JoinRequest(BaseModel):
    invite_code: str


class LeaveResponse(BaseModel):
    unsettled_expenses: list[dict] = []
    pending_chores: list[dict] = []


class RoleChangeRequest(BaseModel):
    role: MemberRole
