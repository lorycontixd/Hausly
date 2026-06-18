import uuid
from datetime import date, datetime

from hausly.modules.expense.models import ExpenseSource, ExpenseStatus
from pydantic import BaseModel, model_validator


class SplitInput(BaseModel):
    user_id: uuid.UUID
    share_amount: float


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    currency: str = "EUR"
    category: str | None = None
    paid_by_user_id: uuid.UUID
    splits: list[SplitInput]
    status: ExpenseStatus = ExpenseStatus.draft
    source: ExpenseSource = ExpenseSource.manual
    is_recurring: bool = False
    recurrence_rule: str | None = None
    next_occurrence_date: date | None = None

    @model_validator(mode="after")
    def validate_splits_sum(self) -> "ExpenseCreate":
        total = sum(s.share_amount for s in self.splits)
        if abs(total - self.amount) > 0.01:
            msg = f"Sum of splits ({total}) must equal expense amount ({self.amount})"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def validate_recurring_fields(self) -> "ExpenseCreate":
        if self.is_recurring:
            if not self.recurrence_rule:
                raise ValueError("recurrence_rule is required for recurring expenses")
            if not self.next_occurrence_date:
                raise ValueError("next_occurrence_date is required for recurring expenses")
        return self


class ExpenseUpdate(BaseModel):
    title: str | None = None
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    paid_by_user_id: uuid.UUID | None = None
    splits: list[SplitInput] | None = None

    @model_validator(mode="after")
    def validate_splits_sum_if_both(self) -> "ExpenseUpdate":
        if self.splits is not None and self.amount is not None:
            total = sum(s.share_amount for s in self.splits)
            if abs(total - self.amount) > 0.01:
                msg = f"Sum of splits ({total}) must equal expense amount ({self.amount})"
                raise ValueError(msg)
        return self


class SplitResponse(BaseModel):
    id: uuid.UUID
    expense_id: uuid.UUID
    user_id: uuid.UUID
    share_amount: float
    is_settled: bool
    settled_at: datetime | None

    model_config = {"from_attributes": True}


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    title: str
    amount: float
    currency: str
    category: str | None
    paid_by_user_id: uuid.UUID
    is_recurring: bool
    status: ExpenseStatus
    source: ExpenseSource
    confirmed_at: datetime | None
    created_at: datetime
    splits: list[SplitResponse]

    model_config = {"from_attributes": True}


class BalanceEntry(BaseModel):
    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    net_amount: float
    direction: str  # "a_owes_b" or "b_owes_a"


class BalanceResponse(BaseModel):
    balances: list[BalanceEntry]


class SettlementSuggestion(BaseModel):
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    amount: float


class SettlementResponse(BaseModel):
    settlements: list[SettlementSuggestion]
