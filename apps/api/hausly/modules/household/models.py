import enum
import secrets
import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class HouseholdType(str, enum.Enum):
    couple = "couple"
    friends = "friends"
    students = "students"
    family = "family"
    custom = "custom"


class SubscriptionTier(str, enum.Enum):
    free = "free"
    paid = "paid"


class MemberRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class NotificationLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(6)


class Household(SQLModel, table=True):
    __tablename__ = "households"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    type: HouseholdType
    invite_code: str = Field(default_factory=_generate_invite_code, unique=True)
    subscription_tier: SubscriptionTier = Field(default=SubscriptionTier.free)
    subscription_owner_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
    archived_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    settings: Optional["HouseholdSettings"] = Relationship(back_populates="household")
    memberships: list["HouseholdMembership"] = Relationship(back_populates="household")


class HouseholdSettings(SQLModel, table=True):
    __tablename__ = "household_settings"

    household_id: uuid.UUID = Field(
        foreign_key="households.id", primary_key=True
    )
    default_currency: str = Field(default="EUR")
    enabled_modules: list[str] = Field(
        default_factory=lambda: ["grocery", "expense", "meal", "chores"],
        sa_type=sa.ARRAY(sa.String),
    )
    notification_level: NotificationLevel = Field(default=NotificationLevel.medium)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    household: Optional[Household] = Relationship(back_populates="settings")


class HouseholdMembership(SQLModel, table=True):
    __tablename__ = "household_memberships"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", index=True)
    role: MemberRole = Field(default=MemberRole.member)
    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )
    left_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    household: Optional[Household] = Relationship(back_populates="memberships")
