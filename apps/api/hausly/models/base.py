import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Base(SQLModel):
    """Base model with UUID primary key and created_at timestamp."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HouseholdScopedBase(Base):
    """Base model for tables scoped to a household (includes household_id FK)."""

    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
