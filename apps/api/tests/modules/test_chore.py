"""Tests for the chore module service layer."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.modules.chores.models import (
    AssignmentStatus,
    Chore,
    ChoreAssignee,
    ChoreAssignment,
    RecurrenceUnit,
)
from hausly.modules.chores.schemas import ChoreCreate, ChoreUpdate
from hausly.modules.chores.service import (
    ChoreError,
    cancel_assignment,
    complete_assignment,
    create_chore,
    delete_chore,
    generate_assignments,
    get_assignments,
    get_chore,
    get_chores,
    on_member_leave,
    postpone_assignment,
    update_chore,
)
from hausly.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession


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


@pytest.fixture
def today():
    return date.today()


class TestCreateChore:
    @pytest.mark.asyncio
    async def test_create_chore_success(self, household_id, user_a, user_b, today, mock_db_session):
        """Creating a chore with valid data succeeds."""
        data = ChoreCreate(
            name="Clean house",
            start_date=today,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            assignee_user_ids=[user_a.id, user_b.id],
            rotation_enabled=True,
        )

        # Mock flush to assign ID
        async def fake_flush():
            pass

        mock_db_session.flush = AsyncMock(side_effect=fake_flush)

        # Mock execute for _assignment_exists, _has_unresolved_overdue, generate_assignments
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await create_chore(mock_db_session, household_id, user_a.id, data)
        assert result.name == "Clean house"
        assert result.is_recurring is True
        assert result.rotation_enabled is True
        assert result.household_id == household_id
        assert result.created_by_user_id == user_a.id
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_chore_creator_not_in_assignees(self, household_id, user_a, user_b, today, mock_db_session):
        """Creating a chore without creator in assignees raises error."""
        data = ChoreCreate(
            name="Clean house",
            start_date=today,
            is_recurring=False,
            assignee_user_ids=[user_b.id],
        )

        with pytest.raises(ChoreError) as exc_info:
            await create_chore(mock_db_session, household_id, user_a.id, data)
        assert exc_info.value.code == "CREATOR_NOT_IN_ASSIGNEES"
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_create_one_off_chore(self, household_id, user_a, user_b, today, mock_db_session):
        """Creating a one-off chore creates immediate assignments."""
        data = ChoreCreate(
            name="Move furniture",
            start_date=today,
            is_recurring=False,
            assignee_user_ids=[user_a.id, user_b.id],
            rotation_enabled=False,
        )

        mock_db_session.flush = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await create_chore(mock_db_session, household_id, user_a.id, data)
        assert result.name == "Move furniture"
        assert result.is_recurring is False


class TestGetChore:
    @pytest.mark.asyncio
    async def test_get_chore_found(self, household_id, user_a, today, mock_db_session):
        """Getting an existing chore returns it with assignees."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Test chore",
            created_by_user_id=user_a.id,
            is_recurring=False,
            start_date=today,
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

        # First call returns chore, second returns assignees
        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = [assignee]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_chore, mock_result_assignees]
        )

        result = await get_chore(mock_db_session, household_id, chore.id)
        assert result.id == chore.id
        assert result.name == "Test chore"
        assert len(result.assignees) == 1

    @pytest.mark.asyncio
    async def test_get_chore_not_found(self, household_id, mock_db_session):
        """Getting a non-existent chore raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await get_chore(mock_db_session, household_id, uuid.uuid4())
        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "CHORE_NOT_FOUND"


class TestGetChores:
    @pytest.mark.asyncio
    async def test_get_chores_returns_active(self, household_id, user_a, today, mock_db_session):
        """List chores returns only active ones."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Active chore",
            created_by_user_id=user_a.id,
            is_recurring=False,
            start_date=today,
            is_active=True,
        )

        # First call: list chores, second: load assignees for chore
        mock_result_chores = MagicMock()
        mock_result_chores.scalars.return_value.all.return_value = [chore]

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_chores, mock_result_assignees]
        )

        result = await get_chores(mock_db_session, household_id)
        assert len(result) == 1
        assert result[0].name == "Active chore"


class TestCompleteAssignment:
    @pytest.mark.asyncio
    async def test_complete_assignment_success(self, household_id, user_a, user_b, today, mock_db_session):
        """Any member can complete any assignment."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Test",
            created_by_user_id=user_a.id,
            is_recurring=True,
            start_date=today,
            is_active=True,
        )
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        # First: get assignment, second: get chore (for auto-deactivate check)
        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_all_assignments = MagicMock()
        mock_result_all_assignments.scalars.return_value.all.return_value = [assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore, mock_result_all_assignments]
        )
        mock_db_session.refresh = AsyncMock()

        result = await complete_assignment(mock_db_session, household_id, assignment.id, user_b.id)
        assert result.status == AssignmentStatus.completed
        assert result.completed_by_user_id == user_b.id
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_assignment_not_found(self, household_id, user_a, mock_db_session):
        """Completing a non-existent assignment raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await complete_assignment(mock_db_session, household_id, uuid.uuid4(), user_a.id)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_assignment_not_pending(self, household_id, user_a, today, mock_db_session):
        """Completing an already-completed assignment raises error."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.completed,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await complete_assignment(mock_db_session, household_id, assignment.id, user_a.id)
        assert exc_info.value.code == "ASSIGNMENT_NOT_PENDING"

    @pytest.mark.asyncio
    async def test_one_off_auto_deactivates(self, household_id, user_a, today, mock_db_session):
        """Completing the last pending assignment of a one-off chore deactivates it."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="One-off",
            created_by_user_id=user_a.id,
            is_recurring=False,
            start_date=today,
            is_active=True,
        )
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        # After completion, all assignments are terminal
        completed_assignment = ChoreAssignment(
            id=assignment.id,
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.completed,
        )
        mock_result_all = MagicMock()
        mock_result_all.scalars.return_value.all.return_value = [completed_assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore, mock_result_all]
        )
        mock_db_session.refresh = AsyncMock()

        await complete_assignment(mock_db_session, household_id, assignment.id, user_a.id)
        assert chore.is_active is False


class TestPostponeAssignment:
    @pytest.mark.asyncio
    async def test_postpone_success(self, household_id, user_a, today, mock_db_session):
        """Postponing a pending assignment sets postponed_to."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today - timedelta(days=1),  # overdue
            status=AssignmentStatus.pending,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        new_date = today + timedelta(days=3)
        result = await postpone_assignment(mock_db_session, household_id, assignment.id, new_date)
        assert result.postponed_to == new_date
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_postpone_not_found(self, household_id, today, mock_db_session):
        """Postponing a non-existent assignment raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await postpone_assignment(
                mock_db_session, household_id, uuid.uuid4(), today + timedelta(days=1)
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_postpone_not_pending(self, household_id, user_a, today, mock_db_session):
        """Postponing a completed assignment raises error."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.completed,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await postpone_assignment(
                mock_db_session, household_id, assignment.id, today + timedelta(days=1)
            )
        assert exc_info.value.code == "ASSIGNMENT_NOT_PENDING"


class TestCancelAssignment:
    @pytest.mark.asyncio
    async def test_cancel_success(self, household_id, user_a, today, mock_db_session):
        """Cancelling a pending assignment sets status to cancelled."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Recurring",
            created_by_user_id=user_a.id,
            is_recurring=True,
            start_date=today,
            is_active=True,
        )
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore]
        )
        mock_db_session.refresh = AsyncMock()

        result = await cancel_assignment(mock_db_session, household_id, assignment.id)
        assert result.status == AssignmentStatus.cancelled

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, household_id, mock_db_session):
        """Cancelling a non-existent assignment raises 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await cancel_assignment(mock_db_session, household_id, uuid.uuid4())
        assert exc_info.value.status_code == 404


class TestDeleteChore:
    @pytest.mark.asyncio
    async def test_delete_chore_deactivates(self, household_id, user_a, today, mock_db_session):
        """Deleting a chore sets is_active=False and removes future pending assignments."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="To delete",
            created_by_user_id=user_a.id,
            is_recurring=True,
            start_date=today,
            is_active=True,
        )

        # Mock: get_chore (find chore + load assignees), then get future assignments
        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = []

        future_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today + timedelta(days=7),
            status=AssignmentStatus.pending,
        )
        mock_result_future = MagicMock()
        mock_result_future.scalars.return_value.all.return_value = [future_assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_chore, mock_result_assignees, mock_result_future]
        )
        mock_db_session.delete = AsyncMock()

        await delete_chore(mock_db_session, household_id, chore.id)
        assert chore.is_active is False
        mock_db_session.delete.assert_awaited_once_with(future_assignment)
        mock_db_session.commit.assert_awaited_once()


class TestGetAssignments:
    @pytest.mark.asyncio
    async def test_get_assignments_with_filters(self, household_id, user_a, today, mock_db_session):
        """List assignments with status/user/date filters."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [assignment]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_assignments(
            mock_db_session,
            household_id,
            status=AssignmentStatus.pending,
            user_id=user_a.id,
            start_date=today,
            end_date=today + timedelta(days=7),
        )
        assert len(result) == 1
        assert result[0].assigned_to_user_id == user_a.id


class TestGenerateAssignments:
    @pytest.mark.asyncio
    async def test_generate_one_off_shared(self, household_id, user_a, user_b, today, mock_db_session):
        """One-off chore with shared assignment creates one per assignee."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="One-off shared",
            created_by_user_id=user_a.id,
            is_recurring=False,
            start_date=today,
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_a.id, position=0),
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_b.id, position=1),
        ]

        # Mock _assignment_exists -> False
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        created = await generate_assignments(mock_db_session, chore, assignees)
        assert len(created) == 2
        user_ids = {a.assigned_to_user_id for a in created}
        assert user_a.id in user_ids
        assert user_b.id in user_ids

    @pytest.mark.asyncio
    async def test_generate_blocked_by_overdue(self, household_id, user_a, today, mock_db_session):
        """Recurring chore with overdue assignment blocks generation."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Blocked chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_a.id, position=0),
        ]

        # Mock _has_unresolved_overdue -> True
        overdue_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today - timedelta(days=7),  # overdue
            status=AssignmentStatus.pending,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [overdue_assignment]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        created = await generate_assignments(mock_db_session, chore, assignees)
        assert len(created) == 0

    @pytest.mark.asyncio
    async def test_generate_empty_assignees(self, household_id, today, mock_db_session):
        """No assignees returns empty list."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="No one",
            created_by_user_id=uuid.uuid4(),
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=today,
            is_active=True,
        )

        created = await generate_assignments(mock_db_session, chore, [])
        assert created == []


class TestOnMemberLeave:
    @pytest.mark.asyncio
    async def test_on_member_leave_removes_assignee(self, household_id, user_a, user_b, today, mock_db_session):
        """Member leave removes them from assignees and deletes future assignments."""
        chore_id = uuid.uuid4()
        assignee_row = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_a.id,
            position=0,
        )
        remaining_assignee = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_b.id,
            position=1,
        )
        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Rotating chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today,
            is_active=True,
        )

        # Call sequence:
        # 1. Find assignee rows for leaving user
        # 2. Find future pending assignments for user
        # 3. Get chore
        # 4. Load remaining assignees
        # 5. Get future pending assignments for chore (to delete+regenerate)
        # 6+. generate_assignments calls

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = [assignee_row]

        mock_result_del = MagicMock()
        mock_result_del.scalars.return_value.all.return_value = []

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_remaining = MagicMock()
        mock_result_remaining.scalars.return_value.all.return_value = [remaining_assignee]

        mock_result_future = MagicMock()
        mock_result_future.scalars.return_value.all.return_value = []

        # For generate_assignments: _has_unresolved_overdue + existing assignments
        mock_result_no_overdue = MagicMock()
        mock_result_no_overdue.scalars.return_value.all.return_value = []

        mock_result_existing = MagicMock()
        mock_result_existing.scalars.return_value.all.return_value = []

        # _assignment_exists checks
        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[
                mock_result_assignees,
                mock_result_del,
                mock_result_chore,
                mock_result_remaining,
                mock_result_future,
                mock_result_no_overdue,
                mock_result_existing,
                mock_result_not_exists,
                mock_result_not_exists,
                mock_result_not_exists,
            ]
        )
        mock_db_session.flush = AsyncMock()
        mock_db_session.delete = AsyncMock()

        await on_member_leave(mock_db_session, household_id, user_a.id)

        # Verify the leaving user's assignee row was deleted
        mock_db_session.delete.assert_any_await(assignee_row)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_member_leave_sole_assignee_deactivates(self, household_id, user_a, today, mock_db_session):
        """If leaving user is sole assignee, chore is deactivated."""
        chore_id = uuid.uuid4()
        assignee_row = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_a.id,
            position=0,
        )
        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Solo chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=today,
            is_active=True,
        )

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = [assignee_row]

        mock_result_del = MagicMock()
        mock_result_del.scalars.return_value.all.return_value = []

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        # No remaining assignees
        mock_result_remaining = MagicMock()
        mock_result_remaining.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[
                mock_result_assignees,
                mock_result_del,
                mock_result_chore,
                mock_result_remaining,
            ]
        )
        mock_db_session.flush = AsyncMock()
        mock_db_session.delete = AsyncMock()

        await on_member_leave(mock_db_session, household_id, user_a.id)
        assert chore.is_active is False


class TestRecurrenceValidation:
    def test_recurring_requires_interval_and_unit(self):
        """Recurring chore without interval/unit raises validation error."""
        with pytest.raises(ValueError):
            ChoreCreate(
                name="Test",
                start_date=date.today(),
                is_recurring=True,
                assignee_user_ids=[uuid.uuid4()],
            )

    def test_non_recurring_no_interval_needed(self):
        """Non-recurring chore doesn't need interval/unit."""
        uid = uuid.uuid4()
        data = ChoreCreate(
            name="Test",
            start_date=date.today(),
            is_recurring=False,
            assignee_user_ids=[uid],
        )
        assert data.recurrence_interval is None
        assert data.recurrence_unit is None


class TestRecurringSharedAssignments:
    """Recurring shared chore (rotation=False) creates one assignment per assignee per occurrence."""

    @pytest.fixture
    def household_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_a(self):
        return User(id=uuid.uuid4(), firebase_uid="a", email="a@test.com", display_name="A")

    @pytest.fixture
    def user_b(self):
        return User(id=uuid.uuid4(), firebase_uid="b", email="b@test.com", display_name="B")

    @pytest.fixture
    def today(self):
        return date.today()

    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    async def test_shared_recurring_generates_for_all_assignees(
        self, household_id, user_a, user_b, today, mock_db_session
    ):
        """Shared recurring (rotation=False) creates one assignment per assignee per due date."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Shared weekly",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=7,
            recurrence_unit=RecurrenceUnit.days,
            start_date=today - timedelta(days=7),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_a.id, position=0),
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_b.id, position=1),
        ]

        # No overdue, no existing assignments
        mock_result_overdue = MagicMock()
        mock_result_overdue.scalars.return_value.all.return_value = []

        mock_result_existing = MagicMock()
        mock_result_existing.scalars.return_value.all.return_value = []

        # _assignment_exists returns None (not exists) for all checks
        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_overdue, mock_result_existing, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists, mock_result_not_exists]
        )

        added = []
        mock_db_session.add = lambda obj: added.append(obj)

        await generate_assignments(mock_db_session, chore, assignees)

        # Each due date gets one assignment per assignee (2 assignees)
        assignments = [a for a in added if isinstance(a, ChoreAssignment)]
        # With 14-day horizon, start_date=today-7, interval=7 → due dates: today, today+7, today+14
        # Each gets 2 assignees → 6 assignments
        assert len(assignments) == 6
        user_ids = {a.assigned_to_user_id for a in assignments}
        assert user_ids == {user_a.id, user_b.id}


class TestMonthlyRecurrence:
    """Monthly recurrence uses relativedelta for date advancement."""

    @pytest.fixture
    def household_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_a(self):
        return User(id=uuid.uuid4(), firebase_uid="a", email="a@test.com", display_name="A")

    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.mark.asyncio
    @patch("hausly.modules.chores.service.date")
    async def test_monthly_advances_by_month(
        self, mock_date, household_id, user_a, mock_db_session
    ):
        """Monthly recurrence advances by calendar months, not fixed days."""
        # Pin today to Jan 1; start_date=Jan 1, so first due date is Jan 1 (today) → generated
        fake_today = date(2025, 1, 1)
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Monthly rent",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.months,
            start_date=date(2025, 1, 1),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_a.id, position=0),
        ]

        mock_result_overdue = MagicMock()
        mock_result_overdue.scalars.return_value.all.return_value = []

        mock_result_existing = MagicMock()
        mock_result_existing.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_overdue, mock_result_existing]
        )

        added = []
        mock_db_session.add = lambda obj: added.append(obj)

        await generate_assignments(mock_db_session, chore, assignees)

        assignments = [a for a in added if isinstance(a, ChoreAssignment)]
        # start_date=Jan 1, today=Jan 1, horizon=Jan 15
        # Due dates: Jan 1 (>=today, in horizon) → 1 assignment
        # Next due: Feb 1 → outside 14-day horizon
        assert len(assignments) == 1
        assert assignments[0].due_date == date(2025, 1, 1)


class TestPostponeNotOverdue:
    """Postpone rejects non-overdue assignments."""

    @pytest.fixture
    def household_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_a(self):
        return User(id=uuid.uuid4(), firebase_uid="a", email="a@test.com", display_name="A")

    @pytest.fixture
    def today(self):
        return date.today()

    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_postpone_rejects_future_assignment(self, household_id, user_a, today, mock_db_session):
        """Cannot postpone an assignment that is not yet overdue."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today + timedelta(days=2),  # future = not overdue
            status=AssignmentStatus.pending,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await postpone_assignment(
                mock_db_session, household_id, assignment.id, today + timedelta(days=5)
            )
        assert exc_info.value.code == "NOT_OVERDUE"
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_postpone_rejects_due_today(self, household_id, user_a, today, mock_db_session):
        """Cannot postpone an assignment due today (not yet overdue)."""
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,  # due today = not overdue yet
            status=AssignmentStatus.pending,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(ChoreError) as exc_info:
            await postpone_assignment(
                mock_db_session, household_id, assignment.id, today + timedelta(days=3)
            )
        assert exc_info.value.code == "NOT_OVERDUE"


class TestPastAssignmentsSurvive:
    """Completed assignments survive chore deletion and member leave."""

    @pytest.fixture
    def household_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def user_a(self):
        return User(id=uuid.uuid4(), firebase_uid="a", email="a@test.com", display_name="A")

    @pytest.fixture
    def today(self):
        return date.today()

    @pytest.fixture
    def mock_db_session(self):
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_delete_chore_keeps_completed_assignments(self, household_id, user_a, today, mock_db_session):
        """Deleting a chore only removes pending assignments, not completed ones."""
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Old chore",
            created_by_user_id=user_a.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )

        completed_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today - timedelta(days=7),
            status=AssignmentStatus.completed,
        )
        pending_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_a.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        # Query for chore
        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        # Query for _load_assignees
        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = []

        # Query for pending assignments to delete
        mock_result_pending = MagicMock()
        mock_result_pending.scalars.return_value.all.return_value = [pending_assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_chore, mock_result_assignees, mock_result_pending]
        )

        await delete_chore(mock_db_session, household_id, chore.id)

        # Only pending assignment should be deleted, not the completed one
        deleted_objects = [call.args[0] for call in mock_db_session.delete.call_args_list]
        assert pending_assignment in deleted_objects
        assert completed_assignment not in deleted_objects
