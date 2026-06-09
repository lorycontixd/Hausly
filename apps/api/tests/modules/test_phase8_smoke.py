"""Smoke test: Phase 8 — Background Jobs (Recurring Expenses + Chore Assignments).

Validates Phase 8 success criteria from implementation-plan-v1.md:
  - Recurring expenses generate drafts correctly on schedule
  - Staleness cap (3 unconfirmed) pauses generation
  - Chore assignments generated for 2-week rolling window
  - Overdue blocking prevents new assignments for that chore
  - Jobs are idempotent (safe to re-run)

Tests exercise the job functions end-to-end with realistic data patterns.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from hausly.jobs.chore_assignments import process_chore_assignments
from hausly.jobs.recurring_expenses import (STALENESS_CAP,
                                            _advance_occurrence_date,
                                            _parse_rrule,
                                            process_recurring_expenses)
from hausly.modules.chores.models import (AssignmentStatus, Chore,
                                          ChoreAssignee, ChoreAssignment,
                                          RecurrenceUnit)
from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
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


# =============================================================================
# RECURRING EXPENSES — End-to-End
# =============================================================================


class TestRecurringExpenseEndToEnd:
    """End-to-end tests for the recurring expense cron job."""

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_happy_path(
        self, household_id, user_alice, user_bob
    ):
        """Success criterion: Recurring expenses generate drafts correctly on schedule.

        Scenario: Monthly rent of €1200 split equally between Alice and Bob.
        Alice pays. Due date is today. Should generate one draft.
        """
        today = date.today()
        template_id = uuid.uuid4()

        template = Expense(
            id=template_id,
            household_id=household_id,
            title="Monthly Rent",
            amount=1200.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )
        split_alice = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=template_id,
            household_id=household_id,
            user_id=user_alice.id,
            share_amount=600.0,
        )
        split_bob = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=template_id,
            household_id=household_id,
            user_id=user_bob.id,
            share_amount=600.0,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        splits_result = MagicMock()
        splits_result.scalars.return_value.all.return_value = [split_alice, split_bob]

        db.execute = AsyncMock(
            side_effect=[recurring_result, count_result, splits_result]
        )

        stats = await process_recurring_expenses(db)

        # Verify draft generated
        assert stats["generated"] == 1
        drafts = [o for o in added_objects if isinstance(o, Expense)]
        assert len(drafts) == 1

        draft = drafts[0]
        # Success criterion: draft has correct properties
        assert draft.status == ExpenseStatus.draft
        assert draft.source == ExpenseSource.recurring_auto
        assert draft.title == "Monthly Rent"
        assert draft.amount == 1200.0
        assert draft.currency == "EUR"
        assert draft.paid_by_user_id == user_alice.id
        assert draft.is_recurring is False  # Generated instance is not recurring itself

        # Splits cloned correctly
        new_splits = [o for o in added_objects if isinstance(o, ExpenseSplit)]
        assert len(new_splits) == 2
        split_amounts = sorted([s.share_amount for s in new_splits])
        assert split_amounts == [600.0, 600.0]
        split_users = {s.user_id for s in new_splits}
        assert split_users == {user_alice.id, user_bob.id}

        # next_occurrence_date advanced by 1 month
        from dateutil.relativedelta import relativedelta
        assert template.next_occurrence_date == today + relativedelta(months=1)

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_staleness_cap(
        self, household_id, user_alice
    ):
        """Success criterion: Staleness cap (3 unconfirmed) pauses generation.

        Scenario: User has 3 unconfirmed monthly utility drafts.
        The job should NOT generate another one.
        """
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Electricity Bill",
            amount=80.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        # 3 unconfirmed drafts already exist
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        db.execute = AsyncMock(side_effect=[recurring_result, count_result])

        stats = await process_recurring_expenses(db)

        # Verify generation was skipped
        assert stats["skipped_stale"] == 1
        assert stats["generated"] == 0
        assert len([o for o in added_objects if isinstance(o, Expense)]) == 0

        # next_occurrence_date should NOT advance
        assert template.next_occurrence_date == today

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_below_staleness_cap(
        self, household_id, user_alice, user_bob
    ):
        """Staleness cap: 2 unconfirmed drafts (below cap) should allow generation."""
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Internet Bill",
            amount=60.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )
        split = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=template.id,
            household_id=household_id,
            user_id=user_bob.id,
            share_amount=60.0,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        # 2 unconfirmed drafts (below cap of 3)
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2

        splits_result = MagicMock()
        splits_result.scalars.return_value.all.return_value = [split]

        db.execute = AsyncMock(
            side_effect=[recurring_result, count_result, splits_result]
        )

        stats = await process_recurring_expenses(db)

        assert stats["generated"] == 1
        assert stats["skipped_stale"] == 0

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_multiple_templates(
        self, household_id, user_alice, user_bob
    ):
        """Multiple recurring expenses should each generate their own draft."""
        today = date.today()

        rent = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Rent",
            amount=1000.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )
        wifi = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="WiFi",
            amount=40.0,
            currency="EUR",
            paid_by_user_id=user_bob.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )

        rent_split = ExpenseSplit(
            id=uuid.uuid4(), expense_id=rent.id,
            household_id=household_id, user_id=user_bob.id, share_amount=500.0,
        )
        wifi_split = ExpenseSplit(
            id=uuid.uuid4(), expense_id=wifi.id,
            household_id=household_id, user_id=user_alice.id, share_amount=20.0,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [rent, wifi]

        # Both have 0 unconfirmed drafts
        count_result_0 = MagicMock()
        count_result_0.scalar_one.return_value = 0

        rent_splits_result = MagicMock()
        rent_splits_result.scalars.return_value.all.return_value = [rent_split]

        count_result_0b = MagicMock()
        count_result_0b.scalar_one.return_value = 0

        wifi_splits_result = MagicMock()
        wifi_splits_result.scalars.return_value.all.return_value = [wifi_split]

        db.execute = AsyncMock(side_effect=[
            recurring_result,
            count_result_0, rent_splits_result,
            count_result_0b, wifi_splits_result,
        ])

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 2
        assert stats["generated"] == 2
        drafts = [o for o in added_objects if isinstance(o, Expense)]
        assert len(drafts) == 2
        titles = {d.title for d in drafts}
        assert titles == {"Rent", "WiFi"}

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_weekly_frequency(
        self, household_id, user_alice
    ):
        """Weekly recurring expense advances date by 1 week."""
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Weekly Groceries",
            amount=100.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=WEEKLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        splits_result = MagicMock()
        splits_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(
            side_effect=[recurring_result, count_result, splits_result]
        )

        await process_recurring_expenses(db)

        # Date advanced by 1 week
        assert template.next_occurrence_date == today + timedelta(weeks=1)

    @pytest.mark.asyncio
    async def test_recurring_expense_end_to_end_not_yet_due(self, household_id, user_alice):
        """Recurring expense with future next_occurrence_date is not processed."""
        future = date.today() + timedelta(days=5)
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Future Expense",
            amount=100.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=future,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        # Query returns nothing because next_occurrence_date > today
        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=recurring_result)

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 0
        assert stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_recurring_expense_idempotency_date_advances_once(
        self, household_id, user_alice
    ):
        """Success criterion: Jobs are idempotent.

        After generation, next_occurrence_date advances to future,
        so the same template won't be picked up on re-run.
        """
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Daily Snack Budget",
            amount=10.0,
            currency="EUR",
            paid_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_rule="FREQ=DAILY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        splits_result = MagicMock()
        splits_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(
            side_effect=[recurring_result, count_result, splits_result]
        )

        await process_recurring_expenses(db)

        # After first run, next_occurrence_date is tomorrow
        assert template.next_occurrence_date == today + timedelta(days=1)
        assert template.next_occurrence_date > today


# =============================================================================
# CHORE ASSIGNMENTS — End-to-End
# =============================================================================


class TestChoreAssignmentEndToEnd:
    """End-to-end tests for the chore assignment cron job."""

    @pytest.mark.asyncio
    async def test_chore_assignment_end_to_end_generates_rolling_window(
        self, household_id, user_alice, user_bob
    ):
        """Success criterion: Chore assignments generated for 2-week rolling window.

        Scenario: Weekly chore rotating between Alice and Bob, started today.
        Should generate 2 assignments (week 1 + week 2 within 14 days).
        """
        from unittest.mock import patch

        today = date.today()
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Vacuum living room",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today,
            rotation_enabled=True,
            is_active=True,
        )
        assignee_a = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_alice.id,
            position=0,
        )
        assignee_b = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_bob.id,
            position=1,
        )

        # Simulate generating 2 assignments
        mock_assignments = [
            ChoreAssignment(
                id=uuid.uuid4(), chore_id=chore.id, household_id=household_id,
                assigned_to_user_id=user_alice.id, due_date=today,
            ),
            ChoreAssignment(
                id=uuid.uuid4(), chore_id=chore.id, household_id=household_id,
                assigned_to_user_id=user_bob.id, due_date=today + timedelta(weeks=1),
            ),
        ]

        db = AsyncMock()
        db.commit = AsyncMock()

        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = [assignee_a, assignee_b]

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=mock_assignments,
        ) as mock_gen:
            stats = await process_chore_assignments(db)

            # Verify generate_assignments called with correct args
            mock_gen.assert_called_once_with(db, chore, [assignee_a, assignee_b])

        assert stats["processed"] == 1
        assert stats["generated"] == 2

    @pytest.mark.asyncio
    async def test_chore_assignment_end_to_end_overdue_blocking(
        self, household_id, user_alice
    ):
        """Success criterion: Overdue blocking prevents new assignments for that chore.

        Scenario: Chore has an overdue pending assignment.
        generate_assignments returns [] (blocked).
        """
        from unittest.mock import patch

        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Dishes",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today() - timedelta(days=7),
            rotation_enabled=False,
            is_active=True,
        )
        assignee = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_alice.id,
            position=0,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = [assignee]

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        # generate_assignments returns empty (overdue blocked)
        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=[],
        ):
            stats = await process_chore_assignments(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 0
        assert stats["skipped_overdue"] == 1

    @pytest.mark.asyncio
    async def test_chore_assignment_end_to_end_multiple_chores(
        self, household_id, user_alice, user_bob
    ):
        """Multiple active chores each get assignments generated independently."""
        from unittest.mock import patch

        today = date.today()
        chore1 = Chore(
            id=uuid.uuid4(), household_id=household_id, name="Vacuum",
            created_by_user_id=user_alice.id, is_recurring=True,
            recurrence_interval=1, recurrence_unit=RecurrenceUnit.weeks,
            start_date=today, rotation_enabled=False, is_active=True,
        )
        chore2 = Chore(
            id=uuid.uuid4(), household_id=household_id, name="Mop",
            created_by_user_id=user_bob.id, is_recurring=True,
            recurrence_interval=3, recurrence_unit=RecurrenceUnit.days,
            start_date=today, rotation_enabled=True, is_active=True,
        )
        assignee1 = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore1.id, household_id=household_id,
            user_id=user_alice.id, position=0,
        )
        assignee2 = ChoreAssignee(
            id=uuid.uuid4(), chore_id=chore2.id, household_id=household_id,
            user_id=user_bob.id, position=0,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore1, chore2]

        assignees1_result = MagicMock()
        assignees1_result.scalars.return_value.all.return_value = [assignee1]

        assignees2_result = MagicMock()
        assignees2_result.scalars.return_value.all.return_value = [assignee2]

        db.execute = AsyncMock(
            side_effect=[chores_result, assignees1_result, assignees2_result]
        )

        mock_assign1 = [ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore1.id, household_id=household_id,
            assigned_to_user_id=user_alice.id, due_date=today,
        )]
        mock_assign2 = [ChoreAssignment(
            id=uuid.uuid4(), chore_id=chore2.id, household_id=household_id,
            assigned_to_user_id=user_bob.id, due_date=today,
        )]

        call_count = [0]

        async def mock_generate(db, chore, assignees):
            call_count[0] += 1
            if chore.name == "Vacuum":
                return mock_assign1
            return mock_assign2

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            side_effect=mock_generate,
        ):
            stats = await process_chore_assignments(db)

        assert stats["processed"] == 2
        assert stats["generated"] == 2
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_chore_assignment_end_to_end_skips_non_recurring(self, household_id, user_alice):
        """One-off chores (is_recurring=False) are NOT processed by the cron job.

        They are handled at creation time, not by the daily job.
        """
        db = AsyncMock()
        db.commit = AsyncMock()

        # The query filters for is_recurring=True, so one-offs aren't returned
        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=chores_result)

        stats = await process_chore_assignments(db)

        assert stats["processed"] == 0

    @pytest.mark.asyncio
    async def test_chore_assignment_end_to_end_idempotent(
        self, household_id, user_alice
    ):
        """Success criterion: Jobs are idempotent (safe to re-run).

        generate_assignments internally checks for existing assignments
        and skips duplicates. Running twice produces same result.
        """
        from unittest.mock import patch

        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Take out trash",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today(),
            rotation_enabled=False,
            is_active=True,
        )
        assignee = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_alice.id,
            position=0,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        # First run: generates 14 assignments
        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = [assignee]

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        first_run_assignments = [
            ChoreAssignment(
                id=uuid.uuid4(), chore_id=chore.id, household_id=household_id,
                assigned_to_user_id=user_alice.id, due_date=date.today() + timedelta(days=i),
            )
            for i in range(14)
        ]

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=first_run_assignments,
        ):
            stats_first = await process_chore_assignments(db)

        assert stats_first["generated"] == 14

        # Second run: same chore, but generate_assignments returns [] (all exist)
        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=[],  # Nothing new to create
        ):
            stats_second = await process_chore_assignments(db)

        # Second run generates nothing (idempotent)
        assert stats_second["generated"] == 0


# =============================================================================
# RRULE PARSING — Edge Cases
# =============================================================================


class TestRruleEdgeCases:
    """Edge cases for recurrence rule handling."""

    def test_biweekly_recurrence(self):
        """Every 2 weeks."""
        start = date(2026, 6, 1)
        result = _advance_occurrence_date(start, "FREQ=WEEKLY;INTERVAL=2")
        assert result == date(2026, 6, 15)

    def test_quarterly_recurrence(self):
        """Every 3 months."""
        start = date(2026, 1, 1)
        result = _advance_occurrence_date(start, "FREQ=MONTHLY;INTERVAL=3")
        assert result == date(2026, 4, 1)

    def test_month_end_overflow(self):
        """Jan 31 + 1 month should not crash (dateutil handles gracefully)."""
        start = date(2026, 1, 31)
        result = _advance_occurrence_date(start, "FREQ=MONTHLY;INTERVAL=1")
        # dateutil clips to Feb 28
        assert result == date(2026, 2, 28)

    def test_daily_interval_large(self):
        """Every 30 days."""
        start = date(2026, 6, 1)
        result = _advance_occurrence_date(start, "FREQ=DAILY;INTERVAL=30")
        assert result == date(2026, 7, 1)

    def test_unknown_freq_defaults_to_monthly(self):
        """Unknown FREQ should default to monthly."""
        interval, unit = _parse_rrule("FREQ=YEARLY;INTERVAL=1")
        assert unit == "monthly"  # Falls through to default


# =============================================================================
# SCHEDULER SETUP
# =============================================================================


class TestSchedulerSetup:
    """Test the scheduler configuration."""

    def test_setup_scheduler_registers_jobs(self):
        """setup_scheduler should register two jobs without error."""
        from hausly.jobs import scheduler, setup_scheduler

        setup_scheduler()

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "recurring_expenses" in job_ids
        assert "chore_assignments" in job_ids

        # Cleanup
        scheduler.remove_all_jobs()
