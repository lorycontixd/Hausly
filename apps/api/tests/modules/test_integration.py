"""Phase 16 — Integration tests for cross-module flows.

Tests cover:
- Grocery→Expense chain: items → session complete → draft expense → confirm → balance update
- Member leave: chore reassignment, meal cleanup, unsettled expense reporting
- Meal entry headcount defaults to member count
- Recurring expense generation with staleness cap
- Chore assignment generation with overdue blocking
- Error handling at the service layer (edge cases)
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.jobs.chore_assignments import process_chore_assignments
from hausly.jobs.recurring_expenses import (STALENESS_CAP,
                                            _advance_occurrence_date,
                                            _parse_rrule,
                                            process_recurring_expenses)
from hausly.modules.chores.models import (AssignmentStatus, Chore,
                                          ChoreAssignee, ChoreAssignment,
                                          RecurrenceUnit)
from hausly.modules.chores.service import ChoreError, generate_assignments
from hausly.modules.chores.service import \
    on_member_leave as chores_on_member_leave
from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
from hausly.modules.expense.schemas import ExpenseCreate, SplitInput
from hausly.modules.expense.service import (ExpenseError, confirm_expense,
                                            create_expense, get_balances)
from hausly.modules.grocery.models import (GroceryItem, GroceryList,
                                           ItemSource, PersonalVisibility)
from hausly.modules.grocery.schemas import SessionCompleteRequest
from hausly.modules.grocery.service import complete_session
from hausly.modules.household.models import (HouseholdMembership,
                                             HouseholdSettings, MemberRole)
from hausly.modules.meal.models import MealPlanEntry, MealSlot
from hausly.modules.meal.schemas import MealEntryCreate
from hausly.modules.meal.service import MealError, create_entry
from hausly.modules.meal.service import on_member_leave as meal_on_member_leave
from hausly.modules.users.models import User

# --- Shared fixtures ---

@pytest.fixture
def household_id():
    return uuid.uuid4()


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


def _make_membership(household_id, user, role=MemberRole.member):
    return HouseholdMembership(
        id=uuid.uuid4(),
        household_id=household_id,
        user_id=user.id,
        role=role,
        joined_at=datetime.now(UTC),
        left_at=None,
    )


def _make_settings(household_id, currency="EUR"):
    return HouseholdSettings(
        household_id=household_id,
        default_currency=currency,
        enabled_modules=["grocery", "expense", "meal", "chores"],
    )


# =============================================================================
# 16.1 / 16.2 — Grocery → Expense chain
# =============================================================================


class TestGroceryExpenseChain:
    """Shopping session → draft expense → confirm → balance update."""

    @pytest.mark.asyncio
    async def test_session_complete_creates_expense_draft(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Session complete with create_expense=True produces a draft with equal splits."""
        list_id = uuid.uuid4()
        item1 = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Milk", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=user_a.id, source=ItemSource.manual,
        )
        item2 = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Bread", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=user_b.id, source=ItemSource.manual,
        )

        membership_a = _make_membership(household_id, user_a, MemberRole.admin)
        membership_b = _make_membership(household_id, user_b)
        settings = _make_settings(household_id)

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            # First call: select bought items
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [item1, item2]
            # Second call: get household settings
            elif call_count["n"] == 2:
                result.scalar_one_or_none.return_value = settings
            # Third call: get active members
            elif call_count["n"] == 3:
                result.scalars.return_value.all.return_value = [membership_a, membership_b]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = SessionCompleteRequest(
            bought_item_ids=[item1.id, item2.id],
            create_expense=True,
            receipt_total=10.00,
        )
        response = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert response.items_removed == 2
        assert response.expense_draft_id is not None
        assert response.expense_draft is not None
        assert response.expense_draft["status"] == "draft"
        assert response.expense_draft["source"] == "grocery_integration"
        assert response.expense_draft["amount"] == 10.00

        # Verify equal splits
        splits = response.expense_draft["splits"]
        assert len(splits) == 2
        for split in splits:
            assert split["share_amount"] == 5.00

    @pytest.mark.asyncio
    async def test_session_complete_excludes_personal_items_from_expense(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Personal items should not be included in the expense title/description."""
        list_id = uuid.uuid4()
        shared_item = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Shared Milk", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=user_a.id, source=ItemSource.manual,
        )
        personal_item = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="My Snack", quantity=1, is_personal=True, is_archived=False,
            is_bought=False, added_by_user_id=user_b.id, source=ItemSource.manual,
            personal_for_user_id=user_b.id,
        )

        membership_a = _make_membership(household_id, user_a, MemberRole.admin)
        membership_b = _make_membership(household_id, user_b)
        settings = _make_settings(household_id)

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [shared_item, personal_item]
            elif call_count["n"] == 2:
                result.scalar_one_or_none.return_value = settings
            elif call_count["n"] == 3:
                result.scalars.return_value.all.return_value = [membership_a, membership_b]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = SessionCompleteRequest(
            bought_item_ids=[shared_item.id, personal_item.id],
            create_expense=True,
            receipt_total=15.00,
        )
        response = await complete_session(mock_db_session, household_id, user_a.id, data)

        # Title mentions only 1 shared item
        assert "1 items" in response.expense_draft["title"]
        # Description only contains the shared item name
        assert "Shared Milk" in response.expense_draft["description"]
        assert "My Snack" not in response.expense_draft["description"]

    @pytest.mark.asyncio
    async def test_session_complete_without_expense_creation(
        self, household_id, user_a, mock_db_session
    ):
        """Session complete with create_expense=False produces no draft."""
        list_id = uuid.uuid4()
        item = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Milk", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=user_a.id, source=ItemSource.manual,
        )

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = [item]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = SessionCompleteRequest(
            bought_item_ids=[item.id],
            create_expense=False,
            receipt_total=0,
        )
        response = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert response.items_removed == 1
        assert response.expense_draft_id is None
        assert response.expense_draft is None

    @pytest.mark.asyncio
    async def test_auto_generated_expense_must_be_draft(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Auto-generated expenses (non-manual source) must start as draft."""
        data = ExpenseCreate(
            title="Auto expense",
            amount=50.00,
            paid_by_user_id=user_a.id,
            splits=[
                SplitInput(user_id=user_a.id, share_amount=25.00),
                SplitInput(user_id=user_b.id, share_amount=25.00),
            ],
            source=ExpenseSource.grocery_integration,
            status=ExpenseStatus.confirmed,
        )

        with pytest.raises(ExpenseError) as exc_info:
            await create_expense(mock_db_session, household_id, data)
        assert "draft" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_confirm_expense_changes_status(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Confirming a draft expense updates its status and sets confirmed_at."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Groceries",
            amount=30.00,
            currency="EUR",
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.draft,
            source=ExpenseSource.grocery_integration,
        )
        splits = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense_id,
                household_id=household_id, user_id=user_a.id,
                share_amount=15.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense_id,
                household_id=household_id, user_id=user_b.id,
                share_amount=15.00, is_settled=False,
            ),
        ]

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = expense
            else:
                result.scalars.return_value.all.return_value = splits
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        result = await confirm_expense(mock_db_session, household_id, expense_id)
        assert result.status == ExpenseStatus.confirmed
        assert result.confirmed_at is not None

    @pytest.mark.asyncio
    async def test_confirmed_expense_affects_balances(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Confirmed expense with splits should produce correct balance entries."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Groceries",
            amount=60.00,
            currency="EUR",
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
        )

        split_a = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense_id,
            household_id=household_id, user_id=user_a.id,
            share_amount=30.00, is_settled=False,
        )
        split_b = ExpenseSplit(
            id=uuid.uuid4(), expense_id=expense_id,
            household_id=household_id, user_id=user_b.id,
            share_amount=30.00, is_settled=False,
        )

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Return confirmed expenses
                result.scalars.return_value.all.return_value = [expense]
            else:
                # Return unsettled splits
                result.scalars.return_value.all.return_value = [split_a, split_b]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        balances = await get_balances(mock_db_session, household_id)

        # user_b owes user_a 30.00 (user_a paid 60, each share is 30,
        # user_a's own share doesn't count, user_b owes 30)
        assert len(balances) == 1
        balance = balances[0]
        assert balance.net_amount == 30.00


# =============================================================================
# 16.2 — Meal entry headcount defaults to member count
# =============================================================================


class TestMealHeadcountDefault:

    @pytest.mark.asyncio
    async def test_headcount_defaults_to_active_member_count(
        self, household_id, user_a, user_b, user_c, mock_db_session
    ):
        """When headcount is not specified, defaults to number of active members."""
        membership_a = _make_membership(household_id, user_a, MemberRole.admin)
        membership_b = _make_membership(household_id, user_b)
        membership_c = _make_membership(household_id, user_c)

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Slot check — no existing entry
                result.scalar_one_or_none.return_value = None
            elif call_count["n"] == 2:
                # get_active_members
                result.all.return_value = [
                    (membership_a, user_a),
                    (membership_b, user_b),
                    (membership_c, user_c),
                ]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        data = MealEntryCreate(
            date=date.today(),
            slot=MealSlot.dinner,
            text="Pasta",
            headcount=None,
        )
        entry = await create_entry(mock_db_session, household_id, user_a.id, data)
        assert entry.headcount == 3

    @pytest.mark.asyncio
    async def test_slot_conflict_raises_409(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Claiming an already-taken slot should raise SLOT_TAKEN error."""
        existing_entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=date.today(),
            slot=MealSlot.lunch,
            text="Existing meal",
            headcount=2,
            owner_user_id=user_b.id,
        )

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_entry
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = MealEntryCreate(
            date=date.today(),
            slot=MealSlot.lunch,
            text="My meal",
        )
        with pytest.raises(MealError) as exc_info:
            await create_entry(mock_db_session, household_id, user_a.id, data)
        assert exc_info.value.status_code == 409
        assert "already claimed" in exc_info.value.detail


# =============================================================================
# 16.2 — Member leave → chore reassignment + meal cleanup
# =============================================================================


class TestMemberLeaveCleanup:

    @pytest.mark.asyncio
    async def test_chore_member_leave_removes_assignee_and_future_assignments(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """When a member leaves, their assignee entries and future assignments are removed."""
        chore_id = uuid.uuid4()
        assignee_a = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, user_id=user_a.id, position=0,
        )
        assignee_b = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, user_id=user_b.id, position=1,
        )

        future_assignment = ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, assigned_to_user_id=user_b.id,
            due_date=date.today() + timedelta(days=5),
            status=AssignmentStatus.pending,
        )

        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Dishes",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=7,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today() - timedelta(days=14),
            rotation_enabled=True,
            is_active=True,
        )

        deleted_items = []
        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Find assignees for leaving user
                result.scalars.return_value.all.return_value = [assignee_b]
            elif call_count["n"] == 2:
                # Future pending assignments for leaving user
                result.scalars.return_value.all.return_value = [future_assignment]
            elif call_count["n"] == 3:
                # Get chore for recomputation
                result.scalar_one_or_none.return_value = chore
            elif call_count["n"] == 4:
                # Remaining assignees after removal
                result.scalars.return_value.all.return_value = [assignee_a]
            elif call_count["n"] == 5:
                # Future pending assignments for this chore (for regeneration)
                result.scalars.return_value.all.return_value = []
            else:
                # Remaining calls for generate_assignments
                result.scalars.return_value.all.return_value = []
                result.scalar_one_or_none.return_value = None
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.delete = AsyncMock(side_effect=lambda obj: deleted_items.append(obj))
        mock_db_session.flush = AsyncMock()

        await chores_on_member_leave(mock_db_session, household_id, user_b.id)

        # Verify assignee and assignment were deleted
        assert assignee_b in deleted_items
        assert future_assignment in deleted_items

    @pytest.mark.asyncio
    async def test_meal_member_leave_deletes_future_entries(
        self, household_id, user_b, mock_db_session
    ):
        """Leaving member's future meal entries are deleted."""
        future_entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=date.today() + timedelta(days=3),
            slot=MealSlot.dinner,
            text="Future meal",
            headcount=2,
            owner_user_id=user_b.id,
        )
        past_entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=date.today() - timedelta(days=1),
            slot=MealSlot.lunch,
            text="Past meal",
            headcount=2,
            owner_user_id=user_b.id,
        )

        deleted_items = []

        async def mock_execute(stmt):
            result = MagicMock()
            # Only return future entries
            result.scalars.return_value.all.return_value = [future_entry]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.delete = AsyncMock(side_effect=lambda obj: deleted_items.append(obj))

        count = await meal_on_member_leave(
            mock_db_session, household_id, user_b.id, date.today()
        )

        assert future_entry in deleted_items
        assert past_entry not in deleted_items


# =============================================================================
# 16.1 — Recurring expense generation
# =============================================================================


class TestRecurringExpenseGeneration:

    def test_parse_rrule_monthly(self):
        interval, unit = _parse_rrule("FREQ=MONTHLY;INTERVAL=1")
        assert interval == 1
        assert unit == "monthly"

    def test_parse_rrule_weekly(self):
        interval, unit = _parse_rrule("FREQ=WEEKLY;INTERVAL=2")
        assert interval == 2
        assert unit == "weekly"

    def test_advance_occurrence_date_monthly(self):
        d = date(2026, 1, 15)
        result = _advance_occurrence_date(d, "FREQ=MONTHLY;INTERVAL=1")
        assert result == date(2026, 2, 15)

    def test_advance_occurrence_date_weekly(self):
        d = date(2026, 6, 1)
        result = _advance_occurrence_date(d, "FREQ=WEEKLY;INTERVAL=2")
        assert result == date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_generates_draft_from_recurring_template(self, household_id, user_a, user_b, mock_db_session):
        """Recurring expense due today creates a draft with same splits."""
        template_id = uuid.uuid4()
        template = Expense(
            id=template_id,
            household_id=household_id,
            title="Monthly Rent",
            amount=1200.00,
            currency="EUR",
            category="rent",
            paid_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=date.today(),
            status=ExpenseStatus.confirmed,
        )

        template_split_a = ExpenseSplit(
            id=uuid.uuid4(), expense_id=template_id,
            household_id=household_id, user_id=user_a.id,
            share_amount=600.00,
        )
        template_split_b = ExpenseSplit(
            id=uuid.uuid4(), expense_id=template_id,
            household_id=household_id, user_id=user_b.id,
            share_amount=600.00,
        )

        call_count = {"n": 0}
        added_objects = []

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Fetch due recurring expenses
                result.scalars.return_value.all.return_value = [template]
            elif call_count["n"] == 2:
                # Count unconfirmed drafts (staleness check)
                result.scalar_one.return_value = 0
            elif call_count["n"] == 3:
                # Load template splits
                result.scalars.return_value.all.return_value = [template_split_a, template_split_b]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.flush = AsyncMock()
        mock_db_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        stats = await process_recurring_expenses(mock_db_session)

        assert stats["processed"] == 1
        assert stats["generated"] == 1
        assert stats["skipped_stale"] == 0

        # A draft expense + 2 splits were added
        expenses_added = [o for o in added_objects if isinstance(o, Expense)]
        splits_added = [o for o in added_objects if isinstance(o, ExpenseSplit)]
        assert len(expenses_added) == 1
        assert expenses_added[0].status == ExpenseStatus.draft
        assert expenses_added[0].source == ExpenseSource.recurring_auto
        assert len(splits_added) == 2

    @pytest.mark.asyncio
    async def test_staleness_cap_blocks_generation(self, household_id, user_a, mock_db_session):
        """If 3+ unconfirmed drafts exist, skip generation."""
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Monthly Rent",
            amount=1200.00,
            currency="EUR",
            paid_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=date.today(),
            status=ExpenseStatus.confirmed,
        )

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [template]
            elif call_count["n"] == 2:
                # 3 unconfirmed drafts exist — exceeds STALENESS_CAP
                result.scalar_one.return_value = STALENESS_CAP
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        stats = await process_recurring_expenses(mock_db_session)

        assert stats["processed"] == 1
        assert stats["generated"] == 0
        assert stats["skipped_stale"] == 1


# =============================================================================
# 16.1 — Chore assignment generation + overdue blocking
# =============================================================================


class TestChoreAssignmentGeneration:

    @pytest.mark.asyncio
    async def test_overdue_blocks_new_assignments(self, household_id, user_a, mock_db_session):
        """Recurring chore with unresolved overdue assignment should not generate new ones."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Vacuum",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=7,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today() - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )

        assignee = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, user_id=user_a.id, position=0,
        )

        overdue_assignment = ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, assigned_to_user_id=user_a.id,
            due_date=date.today() - timedelta(days=3),
            status=AssignmentStatus.pending,
        )

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # _has_unresolved_overdue: return pending assignment with past date
                result.scalars.return_value.all.return_value = [overdue_assignment]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        created = await generate_assignments(mock_db_session, chore, [assignee])
        assert created == []

    @pytest.mark.asyncio
    async def test_one_off_chore_generates_single_assignment(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Non-recurring chore generates one assignment per assignee at start_date."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Clean garage",
            created_by_user_id=user_a.id,
            is_recurring=False,
            start_date=date.today(),
            rotation_enabled=False,
            is_active=True,
        )

        assignee_a = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, user_id=user_a.id, position=0,
        )
        assignee_b = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, user_id=user_b.id, position=1,
        )

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        created = await generate_assignments(mock_db_session, chore, [assignee_a, assignee_b])

        assert len(created) == 2
        assert all(a.due_date == date.today() for a in created)
        assigned_users = {a.assigned_to_user_id for a in created}
        assert assigned_users == {user_a.id, user_b.id}


# =============================================================================
# 16.3 — Error handling & edge cases
# =============================================================================


class TestErrorHandlingEdgeCases:

    @pytest.mark.asyncio
    async def test_confirm_already_confirmed_expense_raises(
        self, household_id, user_a, mock_db_session
    ):
        """Attempting to confirm an already confirmed expense should fail."""
        expense_id = uuid.uuid4()
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Already confirmed",
            amount=10.00,
            paid_by_user_id=user_a.id,
            status=ExpenseStatus.confirmed,
            confirmed_at=datetime.now(UTC),
        )
        splits = []

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalar_one_or_none.return_value = expense
            else:
                result.scalars.return_value.all.return_value = splits
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(ExpenseError) as exc_info:
            await confirm_expense(mock_db_session, household_id, expense_id)
        assert exc_info.value.code == "ALREADY_CONFIRMED"

    @pytest.mark.asyncio
    async def test_splits_must_sum_to_amount(self, household_id, user_a, user_b):
        """Schema validation: sum(splits) must equal expense amount."""
        with pytest.raises(ValueError, match="Sum of splits"):
            ExpenseCreate(
                title="Bad splits",
                amount=100.00,
                paid_by_user_id=user_a.id,
                splits=[
                    SplitInput(user_id=user_a.id, share_amount=40.00),
                    SplitInput(user_id=user_b.id, share_amount=40.00),
                ],
            )

    @pytest.mark.asyncio
    async def test_expense_not_found_raises_404(self, household_id, mock_db_session):
        """Getting a non-existent expense should raise 404."""
        from hausly.modules.expense.service import get_expense

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(ExpenseError) as exc_info:
            await get_expense(mock_db_session, household_id, uuid.uuid4())
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_meal_slot_conflict_returns_409(self, household_id, user_a, mock_db_session):
        """Claiming an already taken meal slot raises SLOT_TAKEN."""
        existing = MealPlanEntry(
            id=uuid.uuid4(), household_id=household_id,
            date=date.today(), slot=MealSlot.dinner,
            text="Already taken", headcount=2, owner_user_id=uuid.uuid4(),
        )

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = MealEntryCreate(date=date.today(), slot=MealSlot.dinner, text="Mine")
        with pytest.raises(MealError) as exc_info:
            await create_entry(mock_db_session, household_id, user_a.id, data)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "SLOT_TAKEN"

    @pytest.mark.asyncio
    async def test_chore_creator_not_in_assignees_raises_error(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Creator must be in assignee list or creation fails."""
        from hausly.modules.chores.schemas import ChoreCreate
        from hausly.modules.chores.service import create_chore

        data = ChoreCreate(
            name="Dishes",
            assignee_user_ids=[user_b.id],
            is_recurring=False,
            start_date=date.today(),
        )

        with pytest.raises(ChoreError) as exc_info:
            await create_chore(mock_db_session, household_id, user_a.id, data)
        assert exc_info.value.code == "CREATOR_NOT_IN_ASSIGNEES"

    @pytest.mark.asyncio
    async def test_grocery_empty_session_no_expense(
        self, household_id, user_a, mock_db_session
    ):
        """Session complete with no items still completes without error."""
        async def mock_execute(stmt):
            result = MagicMock()
            result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = SessionCompleteRequest(
            bought_item_ids=[],
            create_expense=True,
            receipt_total=0,
        )
        response = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert response.items_removed == 0
        assert response.expense_draft is None
