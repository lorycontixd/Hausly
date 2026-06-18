import uuid
from collections import defaultdict
from datetime import UTC, datetime

from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
from hausly.modules.expense.schemas import (BalanceEntry, ExpenseCreate,
                                            ExpenseUpdate,
                                            SettlementSuggestion, SplitInput)
from hausly.modules.household.models import HouseholdMembership
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class ExpenseError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code


async def create_expense(
    db: AsyncSession,
    household_id: uuid.UUID,
    data: ExpenseCreate,
) -> Expense:
    """Create an expense with splits. Validates sum(splits) == amount."""
    # Auto-generated expenses must start as draft
    if data.source != ExpenseSource.manual and data.status != ExpenseStatus.draft:
        raise ExpenseError(
            code="INVALID_STATUS",
            detail="Auto-generated expenses must start as draft",
            status_code=400,
        )

    expense = Expense(
        household_id=household_id,
        title=data.title,
        amount=data.amount,
        currency=data.currency,
        category=data.category,
        paid_by_user_id=data.paid_by_user_id,
        is_recurring=data.is_recurring,
        recurrence_rule=data.recurrence_rule,
        next_occurrence_date=data.next_occurrence_date,
        status=data.status,
        source=data.source,
        confirmed_at=datetime.now(UTC) if data.status == ExpenseStatus.confirmed else None,
    )
    db.add(expense)
    await db.flush()

    for split_data in data.splits:
        split = ExpenseSplit(
            expense_id=expense.id,
            household_id=household_id,
            user_id=split_data.user_id,
            share_amount=split_data.share_amount,
        )
        db.add(split)

    await db.commit()
    await db.refresh(expense)

    # Load splits relationship
    stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
    result = await db.execute(stmt)
    expense.splits = list(result.scalars().all())

    return expense


async def get_expense(
    db: AsyncSession,
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
) -> Expense:
    """Get a single expense with its splits."""
    stmt = select(Expense).where(
        Expense.id == expense_id,
        Expense.household_id == household_id,
    )
    result = await db.execute(stmt)
    expense = result.scalar_one_or_none()

    if expense is None:
        raise ExpenseError(
            code="EXPENSE_NOT_FOUND",
            detail="Expense not found",
            status_code=404,
        )

    splits_stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
    splits_result = await db.execute(splits_stmt)
    expense.splits = list(splits_result.scalars().all())

    return expense


async def list_expenses(
    db: AsyncSession,
    household_id: uuid.UUID,
    status: ExpenseStatus | None = None,
    category: str | None = None,
    cursor: uuid.UUID | None = None,
    limit: int = 20,
) -> list[Expense]:
    """List expenses with optional filters and cursor pagination."""
    stmt = select(Expense).where(
        Expense.household_id == household_id,
    ).order_by(Expense.created_at.desc()).limit(limit)

    if status is not None:
        stmt = stmt.where(Expense.status == status)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if cursor is not None:
        # Cursor-based: get expenses created before the cursor expense
        cursor_expense = await db.get(Expense, cursor)
        if cursor_expense:
            stmt = stmt.where(Expense.created_at < cursor_expense.created_at)

    result = await db.execute(stmt)
    expenses = list(result.scalars().all())

    # Load splits for each expense
    for expense in expenses:
        splits_stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
        splits_result = await db.execute(splits_stmt)
        expense.splits = list(splits_result.scalars().all())

    return expenses


async def update_expense(
    db: AsyncSession,
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
) -> Expense:
    """Update an expense. Only drafts can be updated."""
    expense = await get_expense(db, household_id, expense_id)

    if expense.status != ExpenseStatus.draft:
        raise ExpenseError(
            code="CANNOT_EDIT_CONFIRMED",
            detail="Only draft expenses can be edited",
            status_code=400,
        )

    update_data = data.model_dump(exclude_unset=True, exclude={"splits"})
    for field, value in update_data.items():
        setattr(expense, field, value)

    # If splits are updated, validate and replace
    if data.splits is not None:
        amount = data.amount if data.amount is not None else expense.amount
        total = sum(s.share_amount for s in data.splits)
        if abs(total - amount) > 0.01:
            raise ExpenseError(
                code="SPLITS_MISMATCH",
                detail=f"Sum of splits ({total}) must equal expense amount ({amount})",
                status_code=400,
            )

        # Delete existing splits
        existing_splits_stmt = select(ExpenseSplit).where(
            ExpenseSplit.expense_id == expense.id
        )
        existing_result = await db.execute(existing_splits_stmt)
        for old_split in existing_result.scalars().all():
            await db.delete(old_split)

        # Create new splits
        new_splits = []
        for split_data in data.splits:
            split = ExpenseSplit(
                expense_id=expense.id,
                household_id=household_id,
                user_id=split_data.user_id,
                share_amount=split_data.share_amount,
            )
            db.add(split)
            new_splits.append(split)

    await db.commit()
    await db.refresh(expense)

    # Reload splits
    splits_stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
    splits_result = await db.execute(splits_stmt)
    expense.splits = list(splits_result.scalars().all())

    return expense


async def confirm_expense(
    db: AsyncSession,
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
) -> Expense:
    """Confirm a draft expense. Activates balance impact."""
    expense = await get_expense(db, household_id, expense_id)

    if expense.status != ExpenseStatus.draft:
        raise ExpenseError(
            code="ALREADY_CONFIRMED",
            detail="Expense is already confirmed",
            status_code=400,
        )

    expense.status = ExpenseStatus.confirmed
    expense.confirmed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(expense)

    # Reload splits
    splits_stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
    splits_result = await db.execute(splits_stmt)
    expense.splits = list(splits_result.scalars().all())

    return expense


async def delete_expense(
    db: AsyncSession,
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
) -> None:
    """Delete a draft expense. Confirmed expenses cannot be deleted."""
    expense = await get_expense(db, household_id, expense_id)

    if expense.status != ExpenseStatus.draft:
        raise ExpenseError(
            code="CANNOT_DELETE_CONFIRMED",
            detail="Confirmed expenses cannot be deleted",
            status_code=400,
        )

    # Delete splits first
    splits_stmt = select(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id)
    splits_result = await db.execute(splits_stmt)
    for split in splits_result.scalars().all():
        await db.delete(split)

    await db.delete(expense)
    await db.commit()


async def get_balances(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[BalanceEntry]:
    """Compute net balances between all member pairs (confirmed, unsettled only)."""
    # Get all confirmed expenses with unsettled splits
    stmt = select(Expense).where(
        Expense.household_id == household_id,
        Expense.status == ExpenseStatus.confirmed,
    )
    result = await db.execute(stmt)
    expenses = list(result.scalars().all())

    # Build a map of what each person owes each other
    # owes[A][B] = total that A owes B
    owes: dict[uuid.UUID, dict[uuid.UUID, float]] = defaultdict(lambda: defaultdict(float))

    for expense in expenses:
        splits_stmt = select(ExpenseSplit).where(
            ExpenseSplit.expense_id == expense.id,
            ExpenseSplit.is_settled == False,  # noqa: E712
        )
        splits_result = await db.execute(splits_stmt)
        splits = list(splits_result.scalars().all())

        payer = expense.paid_by_user_id
        for split in splits:
            if split.user_id != payer:
                owes[split.user_id][payer] += float(split.share_amount)

    # Compute net balances for each unique pair
    balances: list[BalanceEntry] = []
    processed: set[tuple[uuid.UUID, uuid.UUID]] = set()

    all_users = set(owes.keys())
    for debts in owes.values():
        all_users.update(debts.keys())

    user_list = sorted(all_users)
    for i, user_a in enumerate(user_list):
        for user_b in user_list[i + 1:]:
            if (user_a, user_b) in processed:
                continue
            processed.add((user_a, user_b))

            a_owes_b = owes[user_a].get(user_b, 0.0)
            b_owes_a = owes[user_b].get(user_a, 0.0)
            net = a_owes_b - b_owes_a

            if abs(net) < 0.01:
                continue

            if net > 0:
                balances.append(BalanceEntry(
                    user_a_id=user_a,
                    user_b_id=user_b,
                    net_amount=round(net, 2),
                    direction="a_owes_b",
                ))
            else:
                balances.append(BalanceEntry(
                    user_a_id=user_a,
                    user_b_id=user_b,
                    net_amount=round(abs(net), 2),
                    direction="b_owes_a",
                ))

    return balances


async def get_settlements(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[SettlementSuggestion]:
    """Compute minimum-transaction settlement suggestions using greedy algorithm."""
    # Get all confirmed expenses
    stmt = select(Expense).where(
        Expense.household_id == household_id,
        Expense.status == ExpenseStatus.confirmed,
    )
    result = await db.execute(stmt)
    expenses = list(result.scalars().all())

    # Compute net balance per person: positive = owed money, negative = owes money
    net_balance: dict[uuid.UUID, float] = defaultdict(float)

    for expense in expenses:
        splits_stmt = select(ExpenseSplit).where(
            ExpenseSplit.expense_id == expense.id,
            ExpenseSplit.is_settled == False,  # noqa: E712
        )
        splits_result = await db.execute(splits_stmt)
        splits = list(splits_result.scalars().all())

        payer = expense.paid_by_user_id
        for split in splits:
            if split.user_id != payer:
                # split.user_id owes payer
                net_balance[split.user_id] -= float(split.share_amount)
                net_balance[payer] += float(split.share_amount)

    # Separate into debtors and creditors
    debtors: list[tuple[uuid.UUID, float]] = []  # (user_id, amount_they_owe)
    creditors: list[tuple[uuid.UUID, float]] = []  # (user_id, amount_owed_to_them)

    for user_id, balance in net_balance.items():
        if balance < -0.01:
            debtors.append((user_id, abs(balance)))
        elif balance > 0.01:
            creditors.append((user_id, balance))

    # Sort largest first
    debtors.sort(key=lambda x: x[1], reverse=True)
    creditors.sort(key=lambda x: x[1], reverse=True)

    # Greedy matching
    settlements: list[SettlementSuggestion] = []
    i, j = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor_id, debt = debtors[i]
        creditor_id, credit = creditors[j]

        transfer = min(debt, credit)
        if transfer > 0.01:
            settlements.append(SettlementSuggestion(
                from_user_id=debtor_id,
                to_user_id=creditor_id,
                amount=round(transfer, 2),
            ))

        debtors[i] = (debtor_id, debt - transfer)
        creditors[j] = (creditor_id, credit - transfer)

        if debtors[i][1] < 0.01:
            i += 1
        if creditors[j][1] < 0.01:
            j += 1

    return settlements


async def settle_split(
    db: AsyncSession,
    household_id: uuid.UUID,
    split_id: uuid.UUID,
) -> ExpenseSplit:
    """Mark a split as settled."""
    stmt = select(ExpenseSplit).where(
        ExpenseSplit.id == split_id,
        ExpenseSplit.household_id == household_id,
    )
    result = await db.execute(stmt)
    split = result.scalar_one_or_none()

    if split is None:
        raise ExpenseError(
            code="SPLIT_NOT_FOUND",
            detail="Expense split not found",
            status_code=404,
        )

    if split.is_settled:
        raise ExpenseError(
            code="ALREADY_SETTLED",
            detail="Split is already settled",
            status_code=400,
        )

    # Verify the expense is confirmed
    expense_stmt = select(Expense).where(Expense.id == split.expense_id)
    expense_result = await db.execute(expense_stmt)
    expense = expense_result.scalar_one_or_none()

    if expense is None or expense.status != ExpenseStatus.confirmed:
        raise ExpenseError(
            code="EXPENSE_NOT_CONFIRMED",
            detail="Cannot settle splits on unconfirmed expenses",
            status_code=400,
        )

    split.is_settled = True
    split.settled_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(split)
    return split
