import enum
import uuid
from datetime import UTC, datetime
from typing import Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel


class ExpenseStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"


class ExpenseSource(str, enum.Enum):
    manual = "manual"
    grocery_integration = "grocery_integration"
    recurring_auto = "recurring_auto"


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    title: str
    amount: float = Field(sa_type=sa.Numeric(12, 2))
    currency: str = Field(default="EUR")
    category: str | None = None
    paid_by_user_id: uuid.UUID = Field(foreign_key="users.id")
    is_recurring: bool = Field(default=False)
    recurrence_rule: str | None = None
    next_occurrence_date: datetime | None = Field(
        default=None, sa_type=sa.Date()
    )
    status: ExpenseStatus = Field(default=ExpenseStatus.draft)
    source: ExpenseSource = Field(default=ExpenseSource.manual)
    confirmed_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    splits: list["ExpenseSplit"] = Relationship(
        back_populates="expense",
        sa_relationship_kwargs={"lazy": "noload"},
    )


class ExpenseSplit(SQLModel, table=True):
    __tablename__ = "expense_splits"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    expense_id: uuid.UUID = Field(foreign_key="expenses.id", index=True)
    household_id: uuid.UUID = Field(foreign_key="households.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    share_amount: float = Field(sa_type=sa.Numeric(12, 2))
    is_settled: bool = Field(default=False)
    settled_at: datetime | None = Field(
        default=None, sa_type=sa.DateTime(timezone=True)
    )

    expense: Optional[Expense] = Relationship(
        back_populates="splits",
        sa_relationship_kwargs={"lazy": "noload"},
    )
