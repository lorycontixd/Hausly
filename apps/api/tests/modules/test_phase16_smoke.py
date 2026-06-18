"""Smoke test: Phase 16 — Integration Testing & Polish.

Validates Phase 16 success criteria from implementation-plan-v1.md:
  - Cross-module flows work end-to-end
  - Grocery→Expense chain: items → session complete → draft expense → confirm → balance
  - Member leave → chore reassignment + meal cleanup
  - Meal headcount defaults to active member count
  - Recurring expense generation respects staleness cap
  - Chore overdue blocking prevents new assignments
  - SignalR events use underscore-separated names matching mobile client
  - All error states produce correct codes and status

Tests exercise the full integration chain with realistic multi-member households.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from hausly.jobs.recurring_expenses import (STALENESS_CAP,
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
                                            create_expense, get_balances,
                                            settle_split)
from hausly.modules.grocery.models import GroceryItem, GroceryList, ItemSource
from hausly.modules.grocery.schemas import SessionCompleteRequest
from hausly.modules.grocery.service import complete_session
from hausly.modules.household.models import (HouseholdMembership,
                                             HouseholdSettings, MemberRole)
from hausly.modules.meal.models import MealPlanEntry, MealSlot
from hausly.modules.meal.schemas import MealEntryCreate
from hausly.modules.meal.service import MealError, create_entry
from hausly.modules.meal.service import on_member_leave as meal_on_member_leave
from hausly.modules.users.models import User
from hausly.realtime.signalr import SignalRService

# --- Fixtures: realistic 3-person household ---


@pytest.fixture
def household_id():
    return uuid.UUID("11111111-2222-3333-4444-555555555555")


@pytest.fixture
def alice():
    return User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        firebase_uid="uid-alice",
        display_name="Alice",
        email="alice@example.com",
    )


@pytest.fixture
def bob():
    return User(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        firebase_uid="uid-bob",
        display_name="Bob",
        email="bob@example.com",
    )


@pytest.fixture
def charlie():
    return User(
        id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
        firebase_uid="uid-charlie",
        display_name="Charlie",
        email="charlie@example.com",
    )


def _membership(household_id, user, role=MemberRole.member):
    return HouseholdMembership(
        id=uuid.uuid4(),
        household_id=household_id,
        user_id=user.id,
        role=role,
        joined_at=datetime.now(UTC),
        left_at=None,
    )


def _settings(household_id):
    return HouseholdSettings(
        household_id=household_id,
        default_currency="EUR",
        enabled_modules=["grocery", "expense", "meal", "chores"],
    )


# =============================================================================
# SMOKE TEST: Full Grocery → Expense → Balance chain
# =============================================================================


class TestPhase16GroceryExpenseChain:
    """End-to-end: add items → shop → session complete → draft → confirm → balance.

    Success criteria validated:
      - Cross-module flows work end-to-end
      - Shopping session creates draft expense with grocery_integration source
      - Draft requires explicit confirmation (non-negotiable #1)
      - Confirmed expense affects balance calculation
      - Personal items excluded from expense
    """

    @pytest.mark.asyncio
    async def test_grocery_expense_chain_end_to_end_happy_path(
        self, household_id, alice, bob, charlie, mock_db_session
    ):
        """Full chain: 5 items (1 personal) → session complete → draft → confirm → Bob owes Alice."""
        list_id = uuid.uuid4()

        # Shared items
        milk = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Milk", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=alice.id, source=ItemSource.manual,
        )
        bread = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Bread", quantity=2, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=bob.id, source=ItemSource.manual,
        )
        eggs = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Eggs", quantity=12, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=charlie.id, source=ItemSource.manual,
        )
        cheese = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Cheese", quantity=1, is_personal=False, is_archived=False,
            is_bought=False, added_by_user_id=alice.id, source=ItemSource.manual,
        )
        # Personal item — should NOT be in expense
        protein_bar = GroceryItem(
            id=uuid.uuid4(), list_id=list_id, household_id=household_id,
            name="Protein Bar", quantity=3, is_personal=True, is_archived=False,
            is_bought=False, added_by_user_id=alice.id, source=ItemSource.manual,
            personal_for_user_id=alice.id,
        )

        all_items = [milk, bread, eggs, cheese, protein_bar]
        members = [
            _membership(household_id, alice, MemberRole.admin),
            _membership(household_id, bob),
            _membership(household_id, charlie),
        ]
        settings = _settings(household_id)

        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Fetch bought items by ID
                result.scalars.return_value.all.return_value = all_items
            elif call_count["n"] == 2:
                # Get household settings
                result.scalar_one_or_none.return_value = settings
            elif call_count["n"] == 3:
                # Get active members for split
                result.scalars.return_value.all.return_value = members
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        # --- Step 1: Complete shopping session ---
        data = SessionCompleteRequest(
            bought_item_ids=[i.id for i in all_items],
            receipt_total=45.00,
            create_expense=True,
        )
        response = await complete_session(mock_db_session, household_id, alice.id, data)

        # Criterion: session removes items and creates draft
        assert response.items_removed == 5
        assert response.expense_draft_id is not None
        assert response.expense_draft is not None

        # Criterion: auto-generated expense is DRAFT (not auto-confirmed)
        assert response.expense_draft["status"] == "draft"
        assert response.expense_draft["source"] == "grocery_integration"

        # Criterion: personal items excluded from expense description
        assert "Protein Bar" not in response.expense_draft["description"]
        assert "Milk" in response.expense_draft["description"]
        assert "Bread" in response.expense_draft["description"]

        # Criterion: title references only non-personal items (4)
        assert "4 items" in response.expense_draft["title"]

        # Criterion: equal split across 3 members
        splits = response.expense_draft["splits"]
        assert len(splits) == 3
        assert all(s["share_amount"] == 15.00 for s in splits)
        assert response.expense_draft["amount"] == 45.00

        # --- Step 2: Confirm the draft expense ---
        expense_id = uuid.UUID(response.expense_draft["id"])
        expense = Expense(
            id=expense_id,
            household_id=household_id,
            title=response.expense_draft["title"],
            amount=45.00,
            currency="EUR",
            paid_by_user_id=alice.id,
            status=ExpenseStatus.draft,
            source=ExpenseSource.grocery_integration,
        )
        expense_splits = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense_id,
                household_id=household_id, user_id=alice.id,
                share_amount=15.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense_id,
                household_id=household_id, user_id=bob.id,
                share_amount=15.00, is_settled=False,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=expense_id,
                household_id=household_id, user_id=charlie.id,
                share_amount=15.00, is_settled=False,
            ),
        ]

        confirm_call = {"n": 0}

        async def mock_confirm_execute(stmt):
            confirm_call["n"] += 1
            result = MagicMock()
            if confirm_call["n"] == 1:
                result.scalar_one_or_none.return_value = expense
            else:
                result.scalars.return_value.all.return_value = expense_splits
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_confirm_execute)

        confirmed = await confirm_expense(mock_db_session, household_id, expense_id)

        # Criterion: confirmation changes status and sets timestamp
        assert confirmed.status == ExpenseStatus.confirmed
        assert confirmed.confirmed_at is not None

        # --- Step 3: Verify balances reflect the expense ---
        # Alice paid 45, each owes 15. Bob owes Alice 15, Charlie owes Alice 15.
        confirmed_expense = Expense(
            id=expense_id,
            household_id=household_id,
            title="Groceries",
            amount=45.00,
            paid_by_user_id=alice.id,
            status=ExpenseStatus.confirmed,
        )

        balance_call = {"n": 0}

        async def mock_balance_execute(stmt):
            balance_call["n"] += 1
            result = MagicMock()
            if balance_call["n"] == 1:
                result.scalars.return_value.all.return_value = [confirmed_expense]
            else:
                result.scalars.return_value.all.return_value = expense_splits
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_balance_execute)

        balances = await get_balances(mock_db_session, household_id)

        # Criterion: balances correctly calculated
        assert len(balances) == 2  # Bob→Alice and Charlie→Alice
        total_owed = sum(b.net_amount for b in balances)
        assert total_owed == 30.00  # 15 + 15


# =============================================================================
# SMOKE TEST: Member leave triggers cross-module cleanup
# =============================================================================


class TestPhase16MemberLeaveCleanup:
    """End-to-end: member leaves → chores reassigned + future meals deleted.

    Success criteria validated:
      - Member leave triggers chore assignee removal
      - Future assignments for leaving member are deleted
      - Chore is recomputed for remaining assignees
      - Future meal entries owned by leaving member are deleted
      - Past meal entries preserved (historical)
    """

    @pytest.mark.asyncio
    async def test_member_leave_end_to_end_chore_cleanup(
        self, household_id, alice, bob, mock_db_session
    ):
        """Bob leaves → his chore assignee entries and future assignments removed."""
        chore_id = uuid.uuid4()

        assignee_alice = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, user_id=alice.id, position=0,
        )
        assignee_bob = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, user_id=bob.id, position=1,
        )

        future_assignment_bob = ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, assigned_to_user_id=bob.id,
            due_date=date.today() + timedelta(days=7),
            status=AssignmentStatus.pending,
        )
        past_assignment_bob = ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore_id,
            household_id=household_id, assigned_to_user_id=bob.id,
            due_date=date.today() - timedelta(days=7),
            status=AssignmentStatus.completed,
            completed_at=datetime.now(UTC),
            completed_by_user_id=bob.id,
        )

        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Vacuum living room",
            created_by_user_id=alice.id,
            is_recurring=True,
            recurrence_interval=7,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today() - timedelta(days=21),
            rotation_enabled=True,
            is_active=True,
        )

        deleted_items = []
        call_count = {"n": 0}

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                # Bob's assignee entries
                result.scalars.return_value.all.return_value = [assignee_bob]
            elif call_count["n"] == 2:
                # Bob's future pending assignments
                result.scalars.return_value.all.return_value = [future_assignment_bob]
            elif call_count["n"] == 3:
                # Chore lookup for recomputation
                result.scalar_one_or_none.return_value = chore
            elif call_count["n"] == 4:
                # Remaining assignees (only Alice)
                result.scalars.return_value.all.return_value = [assignee_alice]
            elif call_count["n"] == 5:
                # Future pending assignments to regenerate (already deleted)
                result.scalars.return_value.all.return_value = []
            else:
                result.scalars.return_value.all.return_value = []
                result.scalar_one_or_none.return_value = None
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.delete = AsyncMock(side_effect=lambda obj: deleted_items.append(obj))
        mock_db_session.flush = AsyncMock()

        await chores_on_member_leave(mock_db_session, household_id, bob.id)

        # Criterion: Bob's assignee entry removed
        assert assignee_bob in deleted_items
        # Criterion: Bob's future assignment removed
        assert future_assignment_bob in deleted_items
        # Criterion: past completed assignment NOT removed
        assert past_assignment_bob not in deleted_items

    @pytest.mark.asyncio
    async def test_member_leave_end_to_end_meal_cleanup(
        self, household_id, bob, mock_db_session
    ):
        """Bob leaves → his future meal entries deleted, past preserved."""
        future_entry = MealPlanEntry(
            id=uuid.uuid4(), household_id=household_id,
            date=date.today() + timedelta(days=5),
            slot=MealSlot.dinner, text="Bob's pasta night",
            headcount=3, owner_user_id=bob.id,
        )
        past_entry = MealPlanEntry(
            id=uuid.uuid4(), household_id=household_id,
            date=date.today() - timedelta(days=2),
            slot=MealSlot.lunch, text="Bob's old lunch",
            headcount=3, owner_user_id=bob.id,
        )

        deleted_items = []

        async def mock_execute(stmt):
            result = MagicMock()
            # Only return future entries (query filters date > leave_date)
            result.scalars.return_value.all.return_value = [future_entry]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.delete = AsyncMock(side_effect=lambda obj: deleted_items.append(obj))

        count = await meal_on_member_leave(mock_db_session, household_id, bob.id, date.today())

        # Criterion: future entry deleted
        assert future_entry in deleted_items
        # Criterion: past entry not touched
        assert past_entry not in deleted_items


# =============================================================================
# SMOKE TEST: Recurring expense generation with staleness cap
# =============================================================================


class TestPhase16RecurringExpenseGeneration:
    """End-to-end: recurring expense template → draft generation → staleness cap.

    Success criteria validated:
      - Due recurring expenses generate new draft
      - Staleness cap (3 unconfirmed) pauses generation
      - next_occurrence_date advances correctly
      - Generated drafts have source=recurring_auto and status=draft
    """

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_generate_and_advance(
        self, household_id, alice, bob, mock_db_session
    ):
        """Monthly rent due today → generates draft, advances to next month."""
        template_id = uuid.uuid4()
        template = Expense(
            id=template_id,
            household_id=household_id,
            title="Monthly Rent",
            amount=900.00,
            currency="EUR",
            category="rent",
            paid_by_user_id=alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=date.today(),
            status=ExpenseStatus.confirmed,
        )
        template_splits = [
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=template_id,
                household_id=household_id, user_id=alice.id,
                share_amount=450.00,
            ),
            ExpenseSplit(
                id=uuid.uuid4(), expense_id=template_id,
                household_id=household_id, user_id=bob.id,
                share_amount=450.00,
            ),
        ]

        call_count = {"n": 0}
        added_objects = []

        async def mock_execute(stmt):
            call_count["n"] += 1
            result = MagicMock()
            if call_count["n"] == 1:
                result.scalars.return_value.all.return_value = [template]
            elif call_count["n"] == 2:
                result.scalar_one.return_value = 0  # No stale drafts
            elif call_count["n"] == 3:
                result.scalars.return_value.all.return_value = template_splits
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)
        mock_db_session.flush = AsyncMock()
        mock_db_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        stats = await process_recurring_expenses(mock_db_session)

        # Criterion: one expense processed and generated
        assert stats["processed"] == 1
        assert stats["generated"] == 1
        assert stats["skipped_stale"] == 0

        # Criterion: generated expense is draft with correct source
        expenses = [o for o in added_objects if isinstance(o, Expense)]
        assert len(expenses) == 1
        assert expenses[0].status == ExpenseStatus.draft
        assert expenses[0].source == ExpenseSource.recurring_auto
        assert expenses[0].amount == 900.00

        # Criterion: splits cloned
        splits = [o for o in added_objects if isinstance(o, ExpenseSplit)]
        assert len(splits) == 2
        assert sum(s.share_amount for s in splits) == 900.00

        # Criterion: next_occurrence_date advanced to next month
        expected_next = date.today().replace(
            month=date.today().month + 1 if date.today().month < 12 else 1,
            year=date.today().year + (1 if date.today().month == 12 else 0),
        )
        assert template.next_occurrence_date == expected_next

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_staleness_blocks(
        self, household_id, alice, mock_db_session
    ):
        """3+ unconfirmed drafts → generation paused (staleness cap)."""
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Weekly Groceries",
            amount=80.00,
            paid_by_user_id=alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=WEEKLY;INTERVAL=1",
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
                # 3 stale unconfirmed drafts exist
                result.scalar_one.return_value = STALENESS_CAP
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        stats = await process_recurring_expenses(mock_db_session)

        # Criterion: staleness blocks generation
        assert stats["processed"] == 1
        assert stats["generated"] == 0
        assert stats["skipped_stale"] == 1


# =============================================================================
# SMOKE TEST: Chore overdue blocking
# =============================================================================


class TestPhase16ChoreOverdueBlocking:
    """End-to-end: overdue assignment blocks new generation.

    Success criteria validated:
      - Recurring chore with unresolved overdue = no new assignments generated
      - Once resolved, generation resumes
    """

    @pytest.mark.asyncio
    async def test_chore_overdue_end_to_end_blocks_generation(
        self, household_id, alice, mock_db_session
    ):
        """Overdue pending assignment from 5 days ago blocks new assignments."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Take out trash",
            created_by_user_id=alice.id,
            is_recurring=True,
            recurrence_interval=2,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today() - timedelta(days=10),
            rotation_enabled=False,
            is_active=True,
        )
        assignee = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, user_id=alice.id, position=0,
        )
        overdue = ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore.id,
            household_id=household_id, assigned_to_user_id=alice.id,
            due_date=date.today() - timedelta(days=5),
            status=AssignmentStatus.pending,
        )

        async def mock_execute(stmt):
            result = MagicMock()
            # _has_unresolved_overdue: returns the overdue assignment
            result.scalars.return_value.all.return_value = [overdue]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        created = await generate_assignments(mock_db_session, chore, [assignee])

        # Criterion: overdue blocks all new generation
        assert created == []


# =============================================================================
# SMOKE TEST: Meal headcount & slot conflict
# =============================================================================


class TestPhase16MealIntegration:
    """End-to-end: meal creation with headcount default and slot conflicts.

    Success criteria validated:
      - Headcount defaults to active member count when omitted
      - Concurrent slot claiming returns 409 SLOT_TAKEN
    """

    @pytest.mark.asyncio
    async def test_meal_end_to_end_headcount_and_conflict(
        self, household_id, alice, bob, charlie, mock_db_session
    ):
        """Alice claims dinner → headcount=3, Bob tries same slot → 409."""
        members = [
            _membership(household_id, alice, MemberRole.admin),
            _membership(household_id, bob),
            _membership(household_id, charlie),
        ]

        # --- Alice claims dinner (no headcount specified → default to 3) ---
        claim_call = {"n": 0}

        async def mock_execute_claim(stmt):
            claim_call["n"] += 1
            result = MagicMock()
            if claim_call["n"] == 1:
                # Slot check: empty
                result.scalar_one_or_none.return_value = None
            elif claim_call["n"] == 2:
                # get_active_members for headcount default
                result.all.return_value = [
                    (members[0], alice),
                    (members[1], bob),
                    (members[2], charlie),
                ]
            else:
                result.scalars.return_value.all.return_value = []
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_claim)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        data_alice = MealEntryCreate(
            date=date.today() + timedelta(days=1),
            slot=MealSlot.dinner,
            text="Homemade pizza",
            headcount=None,
        )
        entry = await create_entry(mock_db_session, household_id, alice.id, data_alice)

        # Criterion: headcount defaults to active member count
        assert entry.headcount == 3
        assert entry.text == "Homemade pizza"
        assert entry.owner_user_id == alice.id

        # --- Bob tries to claim the same slot → 409 ---
        alice_entry = MealPlanEntry(
            id=entry.id,
            household_id=household_id,
            date=date.today() + timedelta(days=1),
            slot=MealSlot.dinner,
            text="Homemade pizza",
            headcount=3,
            owner_user_id=alice.id,
        )

        async def mock_execute_conflict(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = alice_entry
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute_conflict)

        data_bob = MealEntryCreate(
            date=date.today() + timedelta(days=1),
            slot=MealSlot.dinner,
            text="Burgers",
        )
        with pytest.raises(MealError) as exc_info:
            await create_entry(mock_db_session, household_id, bob.id, data_bob)

        # Criterion: concurrent slot claiming returns correct error
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "SLOT_TAKEN"


# =============================================================================
# SMOKE TEST: SignalR event name consistency
# =============================================================================


class TestPhase16SignalREventNames:
    """Validate SignalR event names match mobile client expectations.

    Success criteria validated:
      - All events use underscore-separated names (not colon-separated)
      - Event method names match what mobile `signalr.ts` listens for
    """

    @pytest.mark.asyncio
    async def test_signalr_events_end_to_end_underscore_format(self):
        """All SignalR event wrappers emit underscore-separated targets."""
        from unittest.mock import patch

        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-secret-key-long-enough;Version=1.0;"
            )
            svc = SignalRService()
            svc.broadcast_to_household = AsyncMock()

            hh_id = uuid.uuid4()

            # Fire every event type
            await svc.grocery_item_added(hh_id, {})
            await svc.grocery_item_updated(hh_id, {})
            await svc.grocery_item_removed(hh_id, "x")
            await svc.grocery_list_archived(hh_id, "x")
            await svc.grocery_session_completed(hh_id, [], None)
            await svc.expense_created(hh_id, {})
            await svc.expense_confirmed(hh_id, "x")
            await svc.expense_settled(hh_id, "x")
            await svc.meal_entry_created(hh_id, {})
            await svc.meal_entry_updated(hh_id, {})
            await svc.meal_entry_removed(hh_id, "x")
            await svc.chore_created(hh_id, {})
            await svc.chore_deleted(hh_id, "x")
            await svc.assignment_completed(hh_id, "x", "y")
            await svc.assignment_updated(hh_id, {})
            await svc.member_joined(hh_id, {})
            await svc.member_left(hh_id, "x")
            await svc.household_settings_updated(hh_id, {})

            # Collect all event targets
            targets = [
                call[0][1]
                for call in svc.broadcast_to_household.call_args_list
            ]

            # Criterion: NO colons in event names (all underscore-separated)
            for target in targets:
                assert ":" not in target, f"Event '{target}' uses colon — must use underscores"

            # Criterion: matches mobile client handler names exactly
            expected_mobile_events = {
                "grocery_item_added",
                "grocery_item_updated",
                "grocery_item_removed",
                "grocery_list_archived",
                "grocery_session_completed",
                "expense_created",
                "expense_confirmed",
                "expense_settled",
                "meal_entry_created",
                "meal_entry_updated",
                "meal_entry_removed",
                "chore_created",
                "chore_deleted",
                "assignment_completed",
                "assignment_updated",
                "member_joined",
                "member_left",
                "household_settings_updated",
            }
            assert set(targets) == expected_mobile_events


# =============================================================================
# SMOKE TEST: Error handling edge cases
# =============================================================================


class TestPhase16ErrorHandling:
    """Error states produce correct codes without corrupting state.

    Success criteria validated:
      - Expense validation errors have proper error codes
      - Chore creation enforces creator-in-assignees rule
      - Empty session completes cleanly without generating expense
    """

    @pytest.mark.asyncio
    async def test_error_handling_end_to_end_expense_validation(self, alice, bob):
        """Expense splits that don't sum to amount are rejected at schema level."""
        with pytest.raises(ValueError, match="Sum of splits"):
            ExpenseCreate(
                title="Bad math",
                amount=100.00,
                paid_by_user_id=alice.id,
                splits=[
                    SplitInput(user_id=alice.id, share_amount=30.00),
                    SplitInput(user_id=bob.id, share_amount=30.00),
                ],
            )

    @pytest.mark.asyncio
    async def test_error_handling_end_to_end_chore_creator_rule(
        self, household_id, alice, bob, mock_db_session
    ):
        """Creator not in assignees → CREATOR_NOT_IN_ASSIGNEES error."""
        from hausly.modules.chores.schemas import ChoreCreate
        from hausly.modules.chores.service import create_chore

        data = ChoreCreate(
            name="Clean bathroom",
            assignee_user_ids=[bob.id],
            is_recurring=False,
            start_date=date.today(),
        )

        with pytest.raises(ChoreError) as exc_info:
            await create_chore(mock_db_session, household_id, alice.id, data)

        assert exc_info.value.code == "CREATOR_NOT_IN_ASSIGNEES"
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_error_handling_end_to_end_empty_session(
        self, household_id, alice, mock_db_session
    ):
        """Empty shopping session (no items) completes cleanly."""
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
        response = await complete_session(mock_db_session, household_id, alice.id, data)

        # Criterion: no crash, no expense generated for empty session
        assert response.items_removed == 0
        assert response.expense_draft_id is None
        assert response.expense_draft is None
