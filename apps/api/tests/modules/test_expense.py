"""Tests for the expense module service layer."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
from hausly.modules.expense.schemas import (ExpenseCreate, ExpenseUpdate,
                                            SplitInput)
from hausly.modules.expense.service import (ExpenseError, confirm_expense,
                                            create_expense, delete_expense,
                                            get_balances, get_expense,
                                            get_settlements, settle_split,
                                            update_expense)
from hausly.modules.users.models import User


@pytest.fixture
def user_a():
    return User(
        id=uuid.uuid4(),
        firebase_uid="uid-a",
        display_name="Alice",
        email="alice@example.com",
    )


@pytest.fixture
def user_b():
    return User(
        id=uuid.uuid4(),
        firebase_uid="uid-b",
        display_name="Bob",
        email="bob@example.com",
    )


@pytest.fixture
def user_c():
    return User(
        id=uuid.uuid4(),
        firebase_uid="uid-c",
        display_name="Charlie",
        email="charlie@example.com",
    )


@pytest.fixture
def household_id():
    return uuid.uuid4()


class TestCreateExpense:
    @pytest.mark.asyncio
    async def test_create_expense_success(self, household_id, user_a, user_b, mock_db_session):
        """Creating an expense with valid splits should succeed."""
        data = ExpenseCreate(
            title="Dinner",
            amount=40.00,
            paid_by_user_id=user_a.id,
            splits=[
                SplitInput(user_id=user_a.id, share_amount=20.00),
                SplitInput(user_id=user_b.id, share_amount=20.00),
            ],
            status=ExpenseStatus.confirmed,
        )

        # Mock flush to set id
        async def fake_flush():
            pass

        mock_db_session.flush = AsyncMock(side_effect=fake_flush)

        # Mock the splits query after creation
        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_splits_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await create_expense(mock_db_session, household_id, data)
        assert result.title == "Dinner"
        assert result.amount == 40.00
        assert result.status == ExpenseStatus.confirmed
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_expense_splits_validation(self, household_id, user_a, user_b):
        """Creating expense with splits != amount should fail at schema validation."""
        with pytest.raises(ValueError, match="Sum of splits"):
            ExpenseCreate(
                title="Bad",
                amount=40.00,
                paid_by_user_id=user_a.id,
                splits=[
                    SplitInput(user_id=user_a.id, share_amount=10.00),
                    SplitInput(user_id=user_b.id, share_amount=10.00),
                ],
            )

    @pytest.mark.asyncio
    async def test_auto_generated_must_be_draft(self, household_id, user_a, user_b, mock_db_session):
        """Auto-generated expenses must start as draft."""
        data = ExpenseCreate(
            title="Groceries",
            amount=30.00,
            paid_by_user_id=user_a.id,
            splits=[
                SplitInput(user_id=user_a.id, share_amount=15.00),
                SplitInput(user_id=user_b.id, share_amount=15.00),
            ],
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.grocery_integration,
        )

        with pytest.raises(ExpenseError) as exc_info:
            await create_expense(mock_db_session, household_id, data)
        assert exc_info.value.code == "INVALID_STATUS"


class TestConfirmExpense:
    @pytest.mark.asyncio
    async def test_confirm_draft_expense(self, household_id, mock_db_session):
        """Confirming a draft expense should set status and confirmed_at."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Test",
            amount=20.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.draft,
        )

        # Mock get_expense
        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result, mock_splits_result]
        )
        mock_db_session.refresh = AsyncMock()

        result = await confirm_expense(mock_db_session, household_id, expense_id)
        assert result.status == ExpenseStatus.confirmed
        assert result.confirmed_at is not None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_confirm_already_confirmed_fails(self, household_id, mock_db_session):
        """Confirming an already confirmed expense should fail."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Test",
            amount=20.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.confirmed,
            confirmed_at=datetime.now(UTC),
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result]
        )

        with pytest.raises(ExpenseError) as exc_info:
            await confirm_expense(mock_db_session, household_id, expense_id)
        assert exc_info.value.code == "ALREADY_CONFIRMED"


class TestUpdateExpense:
    @pytest.mark.asyncio
    async def test_update_draft_expense(self, household_id, mock_db_session):
        """Updating a draft expense should succeed."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Old Title",
            amount=30.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.draft,
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result, mock_splits_result]
        )
        mock_db_session.refresh = AsyncMock()

        data = ExpenseUpdate(title="New Title")
        result = await update_expense(mock_db_session, household_id, expense_id, data)
        assert result.title == "New Title"

    @pytest.mark.asyncio
    async def test_update_confirmed_expense_fails(self, household_id, mock_db_session):
        """Updating a confirmed expense should fail."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Confirmed",
            amount=30.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.confirmed,
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result]
        )

        data = ExpenseUpdate(title="Changed")
        with pytest.raises(ExpenseError) as exc_info:
            await update_expense(mock_db_session, household_id, expense_id, data)
        assert exc_info.value.code == "CANNOT_EDIT_CONFIRMED"


class TestDeleteExpense:
    @pytest.mark.asyncio
    async def test_delete_draft_expense(self, household_id, mock_db_session):
        """Deleting a draft expense should succeed."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Draft",
            amount=10.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.draft,
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result, mock_splits_result]
        )
        mock_db_session.delete = AsyncMock()

        await delete_expense(mock_db_session, household_id, expense_id)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_confirmed_expense_fails(self, household_id, mock_db_session):
        """Deleting a confirmed expense should fail."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Confirmed",
            amount=10.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.confirmed,
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result]
        )

        with pytest.raises(ExpenseError) as exc_info:
            await delete_expense(mock_db_session, household_id, expense_id)
        assert exc_info.value.code == "CANNOT_DELETE_CONFIRMED"


class TestGetBalances:
    @pytest.mark.asyncio
    async def test_balance_simple_two_users(self, household_id, user_a, user_b, mock_db_session):
        """A pays 40, split equally: B owes A 20."""
        expense = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Dinner",
            amount=40.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        split_a = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=expense.id,
            household_id=household_id,
            user_id=user_a.id,
            share_amount=20.00,
            is_settled=False,
        )
        split_b = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=expense.id,
            household_id=household_id,
            user_id=user_b.id,
            share_amount=20.00,
            is_settled=False,
        )

        # Mock: first call returns expenses, second returns splits
        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense]

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = [split_a, split_b]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_result]
        )

        balances = await get_balances(mock_db_session, household_id)
        assert len(balances) == 1

        balance = balances[0]
        # B owes A 20
        if balance.user_a_id == user_a.id:
            assert balance.direction == "b_owes_a"
            assert balance.net_amount == 20.00
        else:
            assert balance.direction == "a_owes_b"
            assert balance.net_amount == 20.00

    @pytest.mark.asyncio
    async def test_settled_splits_excluded(self, household_id, user_a, user_b, mock_db_session):
        """Settled splits should not appear in balances."""
        expense = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Dinner",
            amount=40.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        # All splits settled
        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense]

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []  # no unsettled splits

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_result]
        )

        balances = await get_balances(mock_db_session, household_id)
        assert len(balances) == 0


class TestGetSettlements:
    @pytest.mark.asyncio
    async def test_settlement_simple(self, household_id, user_a, user_b, mock_db_session):
        """Simple case: B owes A 20, settlement should suggest B pays A 20."""
        expense = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Dinner",
            amount=40.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        split_b = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=expense.id,
            household_id=household_id,
            user_id=user_b.id,
            share_amount=20.00,
            is_settled=False,
        )

        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense]

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = [split_b]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_result]
        )

        settlements = await get_settlements(mock_db_session, household_id)
        assert len(settlements) == 1
        assert settlements[0].from_user_id == user_b.id
        assert settlements[0].to_user_id == user_a.id
        assert settlements[0].amount == 20.00

    @pytest.mark.asyncio
    async def test_settlement_three_users_minimizes(
        self, household_id, user_a, user_b, user_c, mock_db_session
    ):
        """Three users: A paid 60 (split 20 each), B paid 30 (split 15 each).
        Net: A is owed 40, B is owed 15, C owes 35+... settlement minimizes transactions."""
        expense1 = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Dinner",
            amount=60.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )
        expense2 = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Taxi",
            amount=30.00,
            paid_by_user_id=user_b.id,
            status=ExpenseStatus.confirmed,
        )

        # Splits for expense 1: B and C each owe A their 20 share
        split1_b = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense1.id, household_id=household_id,
            user_id=user_b.id, share_amount=20.00, is_settled=False,
        )
        split1_c = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense1.id, household_id=household_id,
            user_id=user_c.id, share_amount=20.00, is_settled=False,
        )

        # Splits for expense 2: A and C each owe B their 10 share
        split2_a = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense2.id, household_id=household_id,
            user_id=user_a.id, share_amount=10.00, is_settled=False,
        )
        split2_c = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense2.id, household_id=household_id,
            user_id=user_c.id, share_amount=10.00, is_settled=False,
        )

        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense1, expense2]

        mock_splits1_result = MagicMock()
        mock_splits1_result.scalars.return_value.all.return_value = [split1_b, split1_c]

        mock_splits2_result = MagicMock()
        mock_splits2_result.scalars.return_value.all.return_value = [split2_a, split2_c]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits1_result, mock_splits2_result]
        )

        settlements = await get_settlements(mock_db_session, household_id)

        # Verify total flow balances out
        total_from_c = sum(s.amount for s in settlements if s.from_user_id == user_c.id)
        # C owes: 20 to A + 10 to B = 30
        assert abs(total_from_c - 30.00) < 0.01

        # Net A is owed: 40 paid out - 10 received back from exp2 split = 30 net credit
        total_to_a = sum(s.amount for s in settlements if s.to_user_id == user_a.id)
        assert abs(total_to_a - 30.00) < 0.01


class TestSettleSplit:
    @pytest.mark.asyncio
    async def test_settle_split_success(self, household_id, mock_db_session):
        """Settling an unsettled split on a confirmed expense should succeed."""
        expense_id = uuid.uuid4()
        split_id = uuid.uuid4()

        split = ExpenseSplit(
            id=split_id,
            expense_id=expense_id,
            household_id=household_id,
            user_id=uuid.uuid4(),
            share_amount=20.00,
            is_settled=False,
        )

        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Test",
            amount=40.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.confirmed,
        )

        mock_split_result = MagicMock()
        mock_split_result.scalar_one_or_none.return_value = split

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_split_result, mock_expense_result]
        )
        mock_db_session.refresh = AsyncMock()

        result = await settle_split(mock_db_session, household_id, split_id)
        assert result.is_settled is True
        assert result.settled_at is not None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_settle_already_settled_fails(self, household_id, mock_db_session):
        """Settling an already settled split should fail."""
        split_id = uuid.uuid4()
        split = ExpenseSplit(
            id=split_id,
            expense_id=uuid.uuid4(),
            household_id=household_id,
            user_id=uuid.uuid4(),
            share_amount=20.00,
            is_settled=True,
            settled_at=datetime.now(UTC),
        )

        mock_split_result = MagicMock()
        mock_split_result.scalar_one_or_none.return_value = split

        mock_db_session.execute = AsyncMock(return_value=mock_split_result)

        with pytest.raises(ExpenseError) as exc_info:
            await settle_split(mock_db_session, household_id, split_id)
        assert exc_info.value.code == "ALREADY_SETTLED"

    @pytest.mark.asyncio
    async def test_settle_split_on_draft_fails(self, household_id, mock_db_session):
        """Settling a split on a draft expense should fail."""
        expense_id = uuid.uuid4()
        split_id = uuid.uuid4()

        split = ExpenseSplit(
            id=split_id,
            expense_id=expense_id,
            household_id=household_id,
            user_id=uuid.uuid4(),
            share_amount=20.00,
            is_settled=False,
        )

        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Draft",
            amount=40.00,
            paid_by_user_id=uuid.uuid4(),
            status=ExpenseStatus.draft,
        )

        mock_split_result = MagicMock()
        mock_split_result.scalar_one_or_none.return_value = split

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_split_result, mock_expense_result]
        )

        with pytest.raises(ExpenseError) as exc_info:
            await settle_split(mock_db_session, household_id, split_id)
        assert exc_info.value.code == "EXPENSE_NOT_CONFIRMED"

    @pytest.mark.asyncio
    async def test_settle_nonexistent_split_fails(self, household_id, mock_db_session):
        """Settling a non-existent split should return 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ExpenseError) as exc_info:
            await settle_split(mock_db_session, household_id, uuid.uuid4())
        assert exc_info.value.code == "SPLIT_NOT_FOUND"
        assert exc_info.value.status_code == 404


class TestGetExpense:
    @pytest.mark.asyncio
    async def test_get_nonexistent_expense(self, household_id, mock_db_session):
        """Getting a non-existent expense should raise 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ExpenseError) as exc_info:
            await get_expense(mock_db_session, household_id, uuid.uuid4())
        assert exc_info.value.code == "EXPENSE_NOT_FOUND"
        assert exc_info.value.status_code == 404


class TestSplitEdgeCases:
    """Tests for asymmetric splits and payer-excluded scenarios."""

    @pytest.mark.asyncio
    async def test_balance_unequal_split_payer_excluded(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Payer excluded from splits: full amount owed to payer.

        Scenario: User A pays €60, only User B has a split of €60.
        User A is NOT in the splits array (they paid for others only).
        Expected: B owes A €60.

        Covers: unequal splits, payer exclusion, asymmetric balance.
        """
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Gift for Charlie",
            amount=60.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        # Only B's split — payer A is excluded
        split_b = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=expense_id,
            household_id=household_id,
            user_id=user_b.id,
            share_amount=60.00,
            is_settled=False,
        )

        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense]

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = [split_b]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_result]
        )

        balances = await get_balances(mock_db_session, household_id)

        # B owes A the full 60 (no self-cancelling since payer has no split)
        assert len(balances) == 1
        b = balances[0]
        assert b.net_amount == 60.00
        # Verify direction: B owes A
        if b.user_a_id == user_a.id:
            assert b.direction == "b_owes_a"
        else:
            assert b.direction == "a_owes_b"

    @pytest.mark.asyncio
    async def test_balance_unequal_custom_split(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Unequal custom split: payer's self-cancelling math with asymmetry.

        Scenario: User A pays €60, split as A=45, B=15.
        A's net credit = 60 - 45 = 15. B owes A only €15.

        Covers: asymmetric split amounts, payer included with large share.
        """
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Fancy dinner",
            amount=60.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        split_a = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense_id, household_id=household_id,
            user_id=user_a.id, share_amount=45.00, is_settled=False,
        )
        split_b = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense_id, household_id=household_id,
            user_id=user_b.id, share_amount=15.00, is_settled=False,
        )

        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense]

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = [split_a, split_b]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_result]
        )

        balances = await get_balances(mock_db_session, household_id)

        # B owes A only 15 (not 30 — A's 45 split self-cancels most of the debt)
        assert len(balances) == 1
        b = balances[0]
        assert b.net_amount == 15.00
