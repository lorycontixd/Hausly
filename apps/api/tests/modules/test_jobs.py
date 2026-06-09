"""Tests for background jobs: recurring expenses and chore assignments."""

import uuid
from datetime import date, timedelta
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
from hausly.modules.expense.models import (Expense, ExpenseSource,
                                           ExpenseSplit, ExpenseStatus)
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
def household_id():
    return uuid.uuid4()


class TestParseRrule:
    def test_parse_monthly(self):
        interval, unit = _parse_rrule("FREQ=MONTHLY;INTERVAL=1")
        assert interval == 1
        assert unit == "monthly"

    def test_parse_weekly(self):
        interval, unit = _parse_rrule("FREQ=WEEKLY;INTERVAL=2")
        assert interval == 2
        assert unit == "weekly"

    def test_parse_daily(self):
        interval, unit = _parse_rrule("FREQ=DAILY;INTERVAL=1")
        assert interval == 1
        assert unit == "daily"

    def test_parse_defaults(self):
        interval, unit = _parse_rrule("FREQ=MONTHLY")
        assert interval == 1
        assert unit == "monthly"


class TestAdvanceOccurrenceDate:
    def test_advance_monthly(self):
        start = date(2026, 1, 15)
        result = _advance_occurrence_date(start, "FREQ=MONTHLY;INTERVAL=1")
        assert result == date(2026, 2, 15)

    def test_advance_weekly(self):
        start = date(2026, 6, 1)
        result = _advance_occurrence_date(start, "FREQ=WEEKLY;INTERVAL=2")
        assert result == date(2026, 6, 15)

    def test_advance_daily(self):
        start = date(2026, 6, 1)
        result = _advance_occurrence_date(start, "FREQ=DAILY;INTERVAL=3")
        assert result == date(2026, 6, 4)


class TestProcessRecurringExpenses:
    @pytest.mark.asyncio
    async def test_generates_draft_from_recurring(self, household_id, user_a, user_b):
        """A due recurring expense should generate a draft."""
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Monthly Rent",
            amount=1000.0,
            currency="EUR",
            paid_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_rule="FREQ=MONTHLY;INTERVAL=1",
            next_occurrence_date=today,
            status=ExpenseStatus.confirmed,
            source=ExpenseSource.manual,
        )
        split_a = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=template.id,
            household_id=household_id,
            user_id=user_a.id,
            share_amount=500.0,
        )
        split_b = ExpenseSplit(
            id=uuid.uuid4(),
            expense_id=template.id,
            household_id=household_id,
            user_id=user_b.id,
            share_amount=500.0,
        )

        db = AsyncMock()
        added_objects = []
        db.add = lambda obj: added_objects.append(obj)
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        # Mock: query for recurring expenses returns template
        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        # Mock: count unconfirmed drafts returns 0
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0

        # Mock: splits query returns template splits
        splits_result = MagicMock()
        splits_result.scalars.return_value.all.return_value = [split_a, split_b]

        db.execute = AsyncMock(
            side_effect=[recurring_result, count_result, splits_result]
        )

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 1
        assert stats["skipped_stale"] == 0

        # Should have added a draft expense + 2 splits
        drafts = [o for o in added_objects if isinstance(o, Expense)]
        new_splits = [o for o in added_objects if isinstance(o, ExpenseSplit)]
        assert len(drafts) == 1
        assert drafts[0].status == ExpenseStatus.draft
        assert drafts[0].source == ExpenseSource.recurring_auto
        assert drafts[0].title == "Monthly Rent"
        assert drafts[0].amount == 1000.0
        assert len(new_splits) == 2

        # next_occurrence_date should be advanced
        assert template.next_occurrence_date > today

    @pytest.mark.asyncio
    async def test_skips_when_staleness_cap_reached(self, household_id, user_a):
        """Should skip generation when 3+ unconfirmed drafts exist."""
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Utilities",
            amount=200.0,
            currency="EUR",
            paid_by_user_id=user_a.id,
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

        # Return template
        recurring_result = MagicMock()
        recurring_result.scalars.return_value.all.return_value = [template]

        # Return count >= STALENESS_CAP
        count_result = MagicMock()
        count_result.scalar_one.return_value = STALENESS_CAP

        db.execute = AsyncMock(side_effect=[recurring_result, count_result])

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 0
        assert stats["skipped_stale"] == 1
        # No expenses should have been added
        assert len([o for o in added_objects if isinstance(o, Expense)]) == 0

    @pytest.mark.asyncio
    async def test_skips_expense_without_recurrence_rule(self, household_id, user_a):
        """Should skip recurring expense that has no recurrence_rule."""
        today = date.today()
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="No Rule",
            amount=50.0,
            currency="EUR",
            paid_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_rule=None,
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
        db.execute = AsyncMock(side_effect=[recurring_result])

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_no_recurring_expenses(self):
        """No recurring expenses should produce empty stats."""
        db = AsyncMock()
        db.commit = AsyncMock()

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        stats = await process_recurring_expenses(db)

        assert stats["processed"] == 0
        assert stats["generated"] == 0
        assert stats["skipped_stale"] == 0


class TestProcessChoreAssignments:
    @pytest.mark.asyncio
    async def test_generates_assignments_for_recurring_chore(self, household_id, user_a):
        """Should call generate_assignments for each active recurring chore."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Clean bathroom",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=date.today(),
            rotation_enabled=False,
            is_active=True,
        )
        assignee = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_a.id,
            position=0,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        # Mock chores query
        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        # Mock assignees query
        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = [assignee]

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        mock_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=date.today() + timedelta(days=7),
        )

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=[mock_assignment],
        ):
            stats = await process_chore_assignments(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 1

    @pytest.mark.asyncio
    async def test_skips_chore_with_no_assignees(self, household_id, user_a):
        """Should skip chores that have no assignees."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Orphan chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=date.today(),
            rotation_enabled=False,
            is_active=True,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        stats = await process_chore_assignments(db)

        assert stats["processed"] == 1
        assert stats["generated"] == 0

    @pytest.mark.asyncio
    async def test_overdue_blocked_chore_returns_empty(self, household_id, user_a):
        """Chores blocked by overdue assignments return [] from generate_assignments."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Blocked chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=date.today() - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )
        assignee = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            user_id=user_a.id,
            position=0,
        )

        db = AsyncMock()
        db.commit = AsyncMock()

        chores_result = MagicMock()
        chores_result.scalars.return_value.all.return_value = [chore]

        assignees_result = MagicMock()
        assignees_result.scalars.return_value.all.return_value = [assignee]

        db.execute = AsyncMock(side_effect=[chores_result, assignees_result])

        with patch(
            "hausly.jobs.chore_assignments.generate_assignments",
            new_callable=AsyncMock,
            return_value=[],
        ):
            stats = await process_chore_assignments(db)

        assert stats["processed"] == 1
        assert stats["skipped_overdue"] == 1

    @pytest.mark.asyncio
    async def test_no_active_chores(self):
        """No active recurring chores should produce empty stats."""
        db = AsyncMock()
        db.commit = AsyncMock()

        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        stats = await process_chore_assignments(db)

        assert stats["processed"] == 0
        assert stats["generated"] == 0
        assert stats["skipped_overdue"] == 0


class TestJobsIdempotency:
    @pytest.mark.asyncio
    async def test_recurring_expense_advances_date(self, household_id, user_a):
        """next_occurrence_date should advance after generation."""
        today = date.today()
        original_date = today
        template = Expense(
            id=uuid.uuid4(),
            household_id=household_id,
            title="Weekly groceries",
            amount=100.0,
            currency="EUR",
            paid_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_rule="FREQ=WEEKLY;INTERVAL=1",
            next_occurrence_date=original_date,
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

        # Date should have advanced by 1 week
        assert template.next_occurrence_date == original_date + timedelta(weeks=1)
