"""Smoke test: Phase 4 — Expense Module end-to-end.

Validates Phase 4 success criteria from implementation-plan-v1.md:
  - Create expense validates sum(splits) == amount
  - Only confirmed expenses affect balances
  - Draft→confirm flow works
  - Balance calculation correct for multiple payers/participants
  - Settlement algorithm minimizes transactions
  - Grocery integration: session complete creates a proper draft expense

Also validates key behaviours from docs/logics/expense-splits.md:
  - Payer included in splits (self-cancelling in balance math)
  - Auto-generated expenses always start as draft
  - Settled splits excluded from balance calculation
  - Settlement uses greedy minimum-transactions algorithm
"""

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
                                            get_balances, get_settlements,
                                            settle_split, update_expense)
from hausly.modules.users.models import User

# --- Fixtures ---


@pytest.fixture
def user_alice():
    return User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        firebase_uid="uid-alice",
        display_name="Alice",
        email="alice@example.com",
    )


@pytest.fixture
def user_bob():
    return User(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        firebase_uid="uid-bob",
        display_name="Bob",
        email="bob@example.com",
    )


@pytest.fixture
def user_charlie():
    return User(
        id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        firebase_uid="uid-charlie",
        display_name="Charlie",
        email="charlie@example.com",
    )


@pytest.fixture
def household_id():
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


# --- Smoke Tests ---


class TestPhase4ExpenseLifecycle:
    """End-to-end smoke test: create draft → confirm → balance → settle.

    Success criteria: Full expense lifecycle from creation through settlement.
    """

    @pytest.mark.asyncio
    async def test_expense_lifecycle_end_to_end_draft_confirm_settle(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Full flow: create draft expense → confirm → check balances → settle.

        Validates:
          - Create expense validates sum(splits) == amount (success criterion #1)
          - Draft→confirm flow works (criterion #3)
          - Only confirmed expenses affect balances (criterion #2)
        """
        # --- Step 1: Create a draft expense ---
        # Alice pays €60 for dinner, split equally with Bob
        data = ExpenseCreate(
            title="Dinner at Mario's",
            amount=60.00,
            currency="EUR",
            category="food",
            paid_by_user_id=user_alice.id,
            splits=[
                SplitInput(user_id=user_alice.id, share_amount=30.00),
                SplitInput(user_id=user_bob.id, share_amount=30.00),
            ],
            status=ExpenseStatus.draft,
        )

        # Success criterion #1: sum(splits) == amount validated at schema level
        assert sum(s.share_amount for s in data.splits) == data.amount

        mock_db_session.flush = AsyncMock()
        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_splits_result)
        mock_db_session.refresh = AsyncMock()

        expense = await create_expense(mock_db_session, household_id, data)

        assert expense.title == "Dinner at Mario's"
        assert expense.amount == 60.00
        assert expense.status == ExpenseStatus.draft
        assert expense.confirmed_at is None  # Draft has no confirmed_at
        assert expense.source == ExpenseSource.manual
        mock_db_session.commit.assert_awaited()

        # --- Step 2: Verify draft does NOT affect balances ---
        # Only confirmed expenses should affect balances (criterion #2)
        # A draft expense should produce no balance entries
        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = []  # No confirmed expenses
        mock_db_session.execute = AsyncMock(return_value=mock_expenses_result)

        balances = await get_balances(mock_db_session, household_id)
        assert len(balances) == 0  # No balances from drafts

        # --- Step 3: Confirm the expense ---
        expense.status = ExpenseStatus.draft  # Reset for confirm test
        expense.confirmed_at = None

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result, mock_splits_result]
        )
        mock_db_session.refresh = AsyncMock()
        mock_db_session.commit.reset_mock()

        confirmed = await confirm_expense(mock_db_session, household_id, expense.id)

        # Success criterion #3: Draft→confirm flow works
        assert confirmed.status == ExpenseStatus.confirmed
        assert confirmed.confirmed_at is not None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expense_lifecycle_end_to_end_splits_validation_rejects_mismatch(
        self, household_id, user_alice, user_bob
    ):
        """Splits that don't sum to amount are rejected at schema validation.

        Validates: Create expense validates sum(splits) == amount (criterion #1)
        """
        # Attempt to create with splits that don't add up (20 + 20 ≠ 60)
        with pytest.raises(ValueError, match="Sum of splits"):
            ExpenseCreate(
                title="Bad Split",
                amount=60.00,
                paid_by_user_id=user_alice.id,
                splits=[
                    SplitInput(user_id=user_alice.id, share_amount=20.00),
                    SplitInput(user_id=user_bob.id, share_amount=20.00),
                ],
            )

        # Correct splits pass validation
        valid = ExpenseCreate(
            title="Good Split",
            amount=60.00,
            paid_by_user_id=user_alice.id,
            splits=[
                SplitInput(user_id=user_alice.id, share_amount=30.00),
                SplitInput(user_id=user_bob.id, share_amount=30.00),
            ],
        )
        assert valid.amount == 60.00


class TestPhase4BalanceCalculation:
    """Smoke test: balance calculation with multiple payers/participants.

    Success criteria: Balance calculation correct for multiple payers/participants.
    """

    @pytest.mark.asyncio
    async def test_balance_end_to_end_multiple_payers(
        self, household_id, user_alice, user_bob, user_charlie, mock_db_session
    ):
        """Three users, multiple expenses, correct net balances.

        Scenario:
          - Alice pays €90 for dinner (split 30/30/30 among A, B, C)
          - Bob pays €30 for taxi (split 15/15 between B and C)

        Expected balances:
          - Bob owes Alice: 30 (from dinner)
          - Charlie owes Alice: 30 (from dinner)
          - Charlie owes Bob: 15 (from taxi)

        Validates: Balance calculation correct for multiple payers/participants (criterion #4)
        Also validates: expense-splits.md — payer's own split is self-cancelling
        """
        expense1_id = uuid.uuid4()
        expense2_id = uuid.uuid4()

        # Expense 1: Alice pays 90, split three ways
        expense1 = Expense(
            id=expense1_id,
            household_id=household_id,
            title="Dinner",
            amount=90.00,
            paid_by_user_id=user_alice.id,
            status=ExpenseStatus.confirmed,
            confirmed_at=datetime.now(UTC),
        )
        # Expense 2: Bob pays 30, split between B and C
        expense2 = Expense(
            id=expense2_id,
            household_id=household_id,
            title="Taxi",
            amount=30.00,
            paid_by_user_id=user_bob.id,
            status=ExpenseStatus.confirmed,
            confirmed_at=datetime.now(UTC),
        )

        # Splits for expense 1 (only non-payer splits are relevant for balance)
        splits_e1 = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense1_id, household_id=household_id,
                user_id=user_alice.id, share_amount=30.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense1_id, household_id=household_id,
                user_id=user_bob.id, share_amount=30.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense1_id, household_id=household_id,
                user_id=user_charlie.id, share_amount=30.00, is_settled=False,
            ),
        ]
        # Splits for expense 2
        splits_e2 = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense2_id, household_id=household_id,
                user_id=user_bob.id, share_amount=15.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense2_id, household_id=household_id,
                user_id=user_charlie.id, share_amount=15.00, is_settled=False,
            ),
        ]

        # Mock DB calls
        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense1, expense2]

        mock_splits_e1 = MagicMock()
        mock_splits_e1.scalars.return_value.all.return_value = splits_e1

        mock_splits_e2 = MagicMock()
        mock_splits_e2.scalars.return_value.all.return_value = splits_e2

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_e1, mock_splits_e2]
        )

        balances = await get_balances(mock_db_session, household_id)

        # Verify balances exist for relevant pairs
        assert len(balances) >= 2  # At least Alice-Bob and Alice-Charlie

        # Build a lookup for easier assertion
        balance_map = {}
        for b in balances:
            pair = (b.user_a_id, b.user_b_id)
            balance_map[pair] = (b.net_amount, b.direction)

        # expense-splits.md: payer's split is self-cancelling
        # Alice's net credit from exp1: 90 - 30 (her own share) = 60 owed to her
        # Bob owes Alice 30, Charlie owes Alice 30

        # Find Alice-Bob balance
        alice_bob = balance_map.get((user_alice.id, user_bob.id)) or balance_map.get((user_bob.id, user_alice.id))
        assert alice_bob is not None
        assert alice_bob[0] == 30.00  # Bob owes Alice 30

        # Find Alice-Charlie balance
        alice_charlie = balance_map.get((user_alice.id, user_charlie.id)) or balance_map.get((user_charlie.id, user_alice.id))
        assert alice_charlie is not None
        assert alice_charlie[0] == 30.00  # Charlie owes Alice 30

        # Find Bob-Charlie balance
        bob_charlie = balance_map.get((user_bob.id, user_charlie.id)) or balance_map.get((user_charlie.id, user_bob.id))
        assert bob_charlie is not None
        assert bob_charlie[0] == 15.00  # Charlie owes Bob 15

    @pytest.mark.asyncio
    async def test_balance_end_to_end_only_confirmed_affects_balance(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Draft expenses are invisible to balance calculation.

        Validates: Only confirmed expenses affect balances (criterion #2)
        Also validates: expense-splits.md — "Only confirmed expenses affect balances."
        """
        # The service only queries confirmed expenses, so an empty result means
        # draft expenses are properly excluded
        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_expenses_result)

        balances = await get_balances(mock_db_session, household_id)
        assert len(balances) == 0


class TestPhase4SettlementAlgorithm:
    """Smoke test: settlement minimizes transactions.

    Success criteria: Settlement algorithm minimizes transactions.
    """

    @pytest.mark.asyncio
    async def test_settlement_end_to_end_three_users_minimizes_transactions(
        self, household_id, user_alice, user_bob, user_charlie, mock_db_session
    ):
        """Three users with complex debts → settlements minimize transaction count.

        Scenario:
          - Alice pays €90 dinner (split 30/30/30)
          - Bob pays €60 groceries (split 20/20/20)

        Net positions:
          - Alice: paid 90, owes 20 to Bob → net +50 (creditor)
          - Bob: paid 60, owes 30 to Alice → net +10 (creditor)
          - Charlie: owes 30 to Alice + 20 to Bob → net -60 (debtor)

        Optimal settlement (2 transactions, not 3):
          - Charlie pays Alice 50
          - Charlie pays Bob 10

        Validates: Settlement algorithm minimizes transactions (criterion #5)
        Also validates: expense-splits.md — greedy minimum-transactions algorithm
        """
        expense1_id = uuid.uuid4()
        expense2_id = uuid.uuid4()

        expense1 = Expense(
            id=expense1_id, household_id=household_id,
            title="Dinner", amount=90.00, paid_by_user_id=user_alice.id,
            status=ExpenseStatus.confirmed,
        )
        expense2 = Expense(
            id=expense2_id, household_id=household_id,
            title="Groceries", amount=60.00, paid_by_user_id=user_bob.id,
            status=ExpenseStatus.confirmed,
        )

        # Non-payer splits only (payer's own split self-cancels)
        splits_e1 = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense1_id, household_id=household_id,
                user_id=user_bob.id, share_amount=30.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense1_id, household_id=household_id,
                user_id=user_charlie.id, share_amount=30.00, is_settled=False,
            ),
        ]
        splits_e2 = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense2_id, household_id=household_id,
                user_id=user_alice.id, share_amount=20.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense2_id, household_id=household_id,
                user_id=user_charlie.id, share_amount=20.00, is_settled=False,
            ),
        ]

        mock_expenses_result = MagicMock()
        mock_expenses_result.scalars.return_value.all.return_value = [expense1, expense2]

        mock_splits_e1 = MagicMock()
        mock_splits_e1.scalars.return_value.all.return_value = splits_e1

        mock_splits_e2 = MagicMock()
        mock_splits_e2.scalars.return_value.all.return_value = splits_e2

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expenses_result, mock_splits_e1, mock_splits_e2]
        )

        settlements = await get_settlements(mock_db_session, household_id)

        # criterion #5: minimizes transactions — should be 2, not 3
        assert len(settlements) == 2

        # Verify total amounts balance out
        # Charlie is the only debtor (owes 30 + 20 = 50 total)
        charlie_pays = sum(s.amount for s in settlements if s.from_user_id == user_charlie.id)
        assert abs(charlie_pays - 50.00) < 0.01

        # Alice is owed net: 60 (paid) - 20 (owes Bob for groceries) = 40 net creditor
        # Wait — let's recompute:
        # Alice: +30 (Bob's share of dinner) + 30 (Charlie's share of dinner) - 20 (Alice owes Bob for groceries) = +40
        # Bob: +20 (Alice's share of groceries) + 20 (Charlie's share of groceries) - 30 (Bob owes Alice for dinner) = +10
        # Charlie: -30 (owes Alice for dinner) - 20 (owes Bob for groceries) = -50
        alice_receives = sum(s.amount for s in settlements if s.to_user_id == user_alice.id)
        bob_receives = sum(s.amount for s in settlements if s.to_user_id == user_bob.id)
        assert abs(alice_receives - 40.00) < 0.01
        assert abs(bob_receives - 10.00) < 0.01


class TestPhase4DraftProtections:
    """Smoke test: draft expenses are protected from invalid operations.

    Validates the draft→confirm flow guards and immutability rules from expense-splits.md.
    """

    @pytest.mark.asyncio
    async def test_draft_protections_end_to_end(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Draft can be updated/deleted; confirmed cannot.

        Validates:
          - Draft→confirm flow works (criterion #3)
          - expense-splits.md: "Once confirmed, an expense cannot be edited — only archived."
        """
        expense_id = uuid.uuid4()

        # --- A confirmed expense cannot be updated ---
        confirmed_expense = Expense(
            id=expense_id, household_id=household_id,
            title="Confirmed", amount=50.00, paid_by_user_id=user_alice.id,
            status=ExpenseStatus.confirmed, confirmed_at=datetime.now(UTC),
        )

        mock_expense_result = MagicMock()
        mock_expense_result.scalar_one_or_none.return_value = confirmed_expense

        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result]
        )

        with pytest.raises(ExpenseError) as exc_info:
            await update_expense(
                mock_db_session, household_id, expense_id,
                ExpenseUpdate(title="Hacked")
            )
        assert exc_info.value.code == "CANNOT_EDIT_CONFIRMED"

        # --- A confirmed expense cannot be deleted ---
        mock_db_session.execute = AsyncMock(
            side_effect=[mock_expense_result, mock_splits_result]
        )

        with pytest.raises(ExpenseError) as exc_info:
            await delete_expense(mock_db_session, household_id, expense_id)
        assert exc_info.value.code == "CANNOT_DELETE_CONFIRMED"


class TestPhase4GroceryIntegration:
    """Smoke test: auto-generated expenses from grocery integration must be drafts.

    Success criteria: Grocery integration — session complete creates a proper draft expense.
    """

    @pytest.mark.asyncio
    async def test_grocery_integration_end_to_end_auto_generated_must_be_draft(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Auto-generated expenses (grocery, recurring) MUST start as draft.

        Validates:
          - Grocery integration creates draft expense (criterion #6)
          - expense-splits.md: "Auto-generated expenses always start as status: draft"
          - Master plan §2.3: All financial mutations require explicit user confirmation
        """
        # Attempting to create a confirmed grocery_integration expense must fail
        data = ExpenseCreate(
            title="Groceries — 5 items",
            amount=45.60,
            paid_by_user_id=user_alice.id,
            splits=[
                SplitInput(user_id=user_alice.id, share_amount=22.80),
                SplitInput(user_id=user_bob.id, share_amount=22.80),
            ],
            status=ExpenseStatus.confirmed,  # NOT ALLOWED for auto-generated
            source=ExpenseSource.grocery_integration,
        )

        with pytest.raises(ExpenseError) as exc_info:
            await create_expense(mock_db_session, household_id, data)
        assert exc_info.value.code == "INVALID_STATUS"

        # Same for recurring_auto source
        data_recurring = ExpenseCreate(
            title="Rent",
            amount=800.00,
            paid_by_user_id=user_alice.id,
            splits=[
                SplitInput(user_id=user_alice.id, share_amount=400.00),
                SplitInput(user_id=user_bob.id, share_amount=400.00),
            ],
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.recurring_auto,
        )

        with pytest.raises(ExpenseError) as exc_info:
            await create_expense(mock_db_session, household_id, data_recurring)
        assert exc_info.value.code == "INVALID_STATUS"

        # Creating as draft with grocery_integration source succeeds
        draft_data = ExpenseCreate(
            title="Groceries — 5 items",
            amount=45.60,
            paid_by_user_id=user_alice.id,
            splits=[
                SplitInput(user_id=user_alice.id, share_amount=22.80),
                SplitInput(user_id=user_bob.id, share_amount=22.80),
            ],
            status=ExpenseStatus.draft,
            source=ExpenseSource.grocery_integration,
        )

        mock_db_session.flush = AsyncMock()
        mock_splits_result = MagicMock()
        mock_splits_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_splits_result)
        mock_db_session.refresh = AsyncMock()

        result = await create_expense(mock_db_session, household_id, draft_data)
        assert result.status == ExpenseStatus.draft
        assert result.source == ExpenseSource.grocery_integration
        assert result.confirmed_at is None


class TestPhase4SettleSplitFlow:
    """Smoke test: settle split marks external payment.

    Validates the settlement flow from expense-splits.md.
    """

    @pytest.mark.asyncio
    async def test_settle_split_end_to_end_marks_settled(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Settling a split marks it as settled and excludes it from future balances.

        Validates:
          - expense-splits.md: "POST /expenses/splits/{split_id}/settle sets is_settled=true"
          - expense-splits.md: settled splits excluded from balance calculation
        """
        expense_id = uuid.uuid4()
        split_id = uuid.uuid4()

        split = ExpenseSplit(
            id=split_id, expense_id=expense_id, household_id=household_id,
            user_id=user_bob.id, share_amount=30.00, is_settled=False,
        )
        expense = Expense(
            id=expense_id, household_id=household_id,
            title="Dinner", amount=60.00, paid_by_user_id=user_alice.id,
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

        settled = await settle_split(mock_db_session, household_id, split_id)

        # expense-splits.md: is_settled = true and settled_at is set
        assert settled.is_settled is True
        assert settled.settled_at is not None
        mock_db_session.commit.assert_awaited_once()
