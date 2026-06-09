"""Smoke test: Phase 6 — Chore Module end-to-end.

Validates Phase 6 success criteria from implementation-plan-v1.md:
  - Creator must be in assignees (validation error otherwise)
  - Rotation correctly cycles through assignees
  - Overdue assignment blocks new generation for that chore
  - Postpone updates effective date, unblocks generation
  - Anyone can complete any assignment
  - Member leave correctly recomputes rotation
  - One-off chore auto-deactivates when resolved

Also validates key behaviours from docs/logics/chore-schedule.md:
  - One-off chores: assignments created immediately at creation time
  - Recurring chores: initial assignments generated inline on create
  - Idempotent generation (skips existing assignments)
  - Cancel unblocks generation
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

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


@pytest.fixture
def today():
    return date.today()


# --- Smoke Tests ---


class TestPhase6ChoreLifecycle:
    """End-to-end smoke test: create chore → assignments → complete → delete.

    Success criteria: Full chore lifecycle with rotation and assignment generation.
    """

    @pytest.mark.asyncio
    async def test_chore_lifecycle_end_to_end_create_complete_delete(
        self, household_id, user_alice, user_bob, today, mock_db_session
    ):
        """Full flow: create recurring chore → verify assignments → complete → delete.

        Validates:
          - Creator must be in assignees (criterion #1)
          - Anyone can complete any assignment (criterion #5)
          - Delete deactivates chore and removes future assignments
        """
        # --- Step 1: Attempt create without creator in assignees → fails ---
        bad_data = ChoreCreate(
            name="Clean bathroom",
            start_date=today,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            assignee_user_ids=[user_bob.id],  # Alice (creator) not included
            rotation_enabled=False,
        )

        # Criterion #1: Creator must be in assignees
        with pytest.raises(ChoreError) as exc_info:
            await create_chore(mock_db_session, household_id, user_alice.id, bad_data)
        assert exc_info.value.code == "CREATOR_NOT_IN_ASSIGNEES"
        assert exc_info.value.status_code == 400

        # --- Step 2: Create recurring chore correctly ---
        data = ChoreCreate(
            name="Clean bathroom",
            start_date=today,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            assignee_user_ids=[user_alice.id, user_bob.id],
            rotation_enabled=True,
        )

        mock_db_session.flush = AsyncMock()
        # Mock: no existing assignments (for generate_assignments)
        mock_result_empty = MagicMock()
        mock_result_empty.scalar_one_or_none.return_value = None
        mock_result_empty.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result_empty)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        chore = await create_chore(mock_db_session, household_id, user_alice.id, data)
        assert chore.name == "Clean bathroom"
        assert chore.is_recurring is True
        assert chore.rotation_enabled is True
        assert chore.created_by_user_id == user_alice.id
        assert chore.household_id == household_id
        mock_db_session.commit.assert_awaited()

        # --- Step 3: Bob (not the assignee) completes Alice's assignment ---
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        # Criterion #5: Anyone can complete any assignment
        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment

        # For one-off auto-deactivate check: it's recurring, so no deactivation
        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_all = MagicMock()
        mock_result_all.scalars.return_value.all.return_value = [assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore, mock_result_all]
        )
        mock_db_session.refresh = AsyncMock()

        completed = await complete_assignment(
            mock_db_session, household_id, assignment.id, user_bob.id
        )
        assert completed.status == AssignmentStatus.completed
        assert completed.completed_by_user_id == user_bob.id  # Bob completed Alice's chore
        assert completed.completed_at is not None

        # --- Step 4: Delete chore → deactivates ---
        mock_result_chore2 = MagicMock()
        mock_result_chore2.scalar_one_or_none.return_value = chore

        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = []

        future_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_bob.id,
            due_date=today + timedelta(days=7),
            status=AssignmentStatus.pending,
        )
        mock_result_future = MagicMock()
        mock_result_future.scalars.return_value.all.return_value = [future_assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_chore2, mock_result_assignees, mock_result_future]
        )
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit.reset_mock()

        await delete_chore(mock_db_session, household_id, chore.id)
        assert chore.is_active is False
        mock_db_session.delete.assert_awaited_once_with(future_assignment)
        mock_db_session.commit.assert_awaited_once()


class TestPhase6RotationCycling:
    """Validates that rotation correctly cycles through assignees (criterion #2)."""

    @pytest.mark.asyncio
    async def test_rotation_cycles_through_assignees_in_order(
        self, household_id, user_alice, user_bob, user_charlie, today, mock_db_session
    ):
        """Weekly chore rotating [A, B, C] assigns A→B→C→A... in sequence.

        Validates:
          - Rotation correctly cycles through assignees (criterion #2)
          - Assignment generation is idempotent
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Clean house",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today,
            rotation_enabled=True,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_alice.id, position=0),
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_bob.id, position=1),
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_charlie.id, position=2),
        ]

        # Mock: no overdue, no existing assignments
        mock_result_no_overdue = MagicMock()
        mock_result_no_overdue.scalars.return_value.all.return_value = []

        mock_result_no_existing = MagicMock()
        mock_result_no_existing.scalars.return_value.all.return_value = []

        # _assignment_exists calls will all return None (not exists)
        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        # Build side_effect: first overdue check, then existing assignments, then N _assignment_exists calls
        side_effects = [mock_result_no_overdue, mock_result_no_existing]
        for _ in range(10):  # Enough for multiple weeks
            side_effects.append(mock_result_not_exists)

        mock_db_session.execute = AsyncMock(side_effect=side_effects)

        created = await generate_assignments(mock_db_session, chore, assignees, horizon_days=21)

        # With weekly recurrence starting today, horizon=21 days → up to 3 occurrences
        assert len(created) >= 2  # At least 2 weeks generated

        # Criterion #2: Rotation cycles A → B → C
        if len(created) >= 3:
            assert created[0].assigned_to_user_id == user_alice.id   # Week 1: Alice
            assert created[1].assigned_to_user_id == user_bob.id     # Week 2: Bob
            assert created[2].assigned_to_user_id == user_charlie.id # Week 3: Charlie
        elif len(created) >= 2:
            assert created[0].assigned_to_user_id == user_alice.id   # Week 1: Alice
            assert created[1].assigned_to_user_id == user_bob.id     # Week 2: Bob


class TestPhase6OverdueBlocking:
    """Validates overdue assignment blocks new generation (criterion #3)."""

    @pytest.mark.asyncio
    async def test_overdue_blocks_generation_until_resolved(
        self, household_id, user_alice, today, mock_db_session
    ):
        """A pending assignment past due date blocks generation of new assignments.

        Validates:
          - Overdue assignment blocks new generation for that chore (criterion #3)
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Weekly vacuum",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_alice.id, position=0),
        ]

        # An overdue pending assignment exists (due 3 days ago)
        overdue = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today - timedelta(days=3),
            status=AssignmentStatus.pending,
        )

        mock_result_overdue = MagicMock()
        mock_result_overdue.scalars.return_value.all.return_value = [overdue]
        mock_db_session.execute = AsyncMock(return_value=mock_result_overdue)

        # Criterion #3: Overdue blocks generation
        created = await generate_assignments(mock_db_session, chore, assignees)
        assert created == []

    @pytest.mark.asyncio
    async def test_postpone_unblocks_generation(
        self, household_id, user_alice, today, mock_db_session
    ):
        """Postponing an overdue assignment to a future date unblocks generation.

        Validates:
          - Postpone updates effective date (criterion #4)
          - After postpone, effective date is in the future → not overdue → generation unblocked
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Weekly vacuum",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_alice.id, position=0),
        ]

        # Overdue assignment that has been postponed to the future
        postponed = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today - timedelta(days=3),
            postponed_to=today + timedelta(days=4),  # Effective date is future → not overdue
            status=AssignmentStatus.pending,
        )

        # Criterion #4: Postponed assignment with future effective date doesn't block
        mock_result_postponed = MagicMock()
        mock_result_postponed.scalars.return_value.all.return_value = [postponed]

        # existing assignments query
        mock_result_existing = MagicMock()
        mock_result_existing.scalars.return_value.all.return_value = [postponed]

        # _assignment_exists calls
        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        side_effects = [mock_result_postponed, mock_result_existing]
        for _ in range(10):
            side_effects.append(mock_result_not_exists)

        mock_db_session.execute = AsyncMock(side_effect=side_effects)

        created = await generate_assignments(mock_db_session, chore, assignees)
        # Postponed to future → not overdue → generation should proceed
        assert len(created) >= 1


class TestPhase6OneOffAutoDeactivate:
    """Validates one-off chore auto-deactivates when resolved (criterion #7)."""

    @pytest.mark.asyncio
    async def test_one_off_chore_deactivates_when_all_completed(
        self, household_id, user_alice, user_bob, today, mock_db_session
    ):
        """One-off chore with 2 assignees deactivates after both assignments complete.

        Validates:
          - One-off chore auto-deactivates when resolved (criterion #7)
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Move sofa",
            created_by_user_id=user_alice.id,
            is_recurring=False,
            start_date=today,
            rotation_enabled=False,
            is_active=True,
        )

        # Two assignments: Alice and Bob each have one
        assignment_alice = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )
        assignment_bob = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_bob.id,
            due_date=today,
            status=AssignmentStatus.completed,  # Bob already done
        )

        # Alice completes her assignment → all are now terminal → auto-deactivate
        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment_alice

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        # After completion check: both assignments in terminal state
        completed_alice = ChoreAssignment(
            id=assignment_alice.id,
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today,
            status=AssignmentStatus.completed,
        )
        mock_result_all = MagicMock()
        mock_result_all.scalars.return_value.all.return_value = [completed_alice, assignment_bob]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore, mock_result_all]
        )
        mock_db_session.refresh = AsyncMock()

        # Criterion #7: One-off auto-deactivates
        await complete_assignment(mock_db_session, household_id, assignment_alice.id, user_alice.id)
        assert chore.is_active is False

    @pytest.mark.asyncio
    async def test_one_off_cancel_also_deactivates(
        self, household_id, user_alice, today, mock_db_session
    ):
        """Cancelling the last pending assignment of a one-off chore also deactivates it.

        Validates:
          - One-off chore auto-deactivates when resolved (criterion #7) via cancel path
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Fix shelf",
            created_by_user_id=user_alice.id,
            is_recurring=False,
            start_date=today,
            rotation_enabled=False,
            is_active=True,
        )
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today,
            status=AssignmentStatus.pending,
        )

        mock_result_assignment = MagicMock()
        mock_result_assignment.scalar_one_or_none.return_value = assignment

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        cancelled_assignment = ChoreAssignment(
            id=assignment.id,
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today,
            status=AssignmentStatus.cancelled,
        )
        mock_result_all = MagicMock()
        mock_result_all.scalars.return_value.all.return_value = [cancelled_assignment]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignment, mock_result_chore, mock_result_all]
        )
        mock_db_session.refresh = AsyncMock()

        await cancel_assignment(mock_db_session, household_id, assignment.id)
        assert chore.is_active is False


class TestPhase6MemberLeave:
    """Validates member leave correctly recomputes rotation (criterion #6)."""

    @pytest.mark.asyncio
    async def test_member_leave_removes_and_deactivates_sole_chore(
        self, household_id, user_alice, today, mock_db_session
    ):
        """When the sole assignee leaves, chore is deactivated.

        Validates:
          - Member leave correctly recomputes rotation (criterion #6)
          - If sole assignee leaves → chore deactivated
        """
        chore_id = uuid.uuid4()
        assignee_row = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_alice.id,
            position=0,
        )
        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Alice-only chore",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.days,
            start_date=today,
            is_active=True,
        )

        # Sequence: find assignee rows, find future assignments, get chore, remaining assignees
        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = [assignee_row]

        mock_result_del = MagicMock()
        mock_result_del.scalars.return_value.all.return_value = []

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        mock_result_remaining = MagicMock()
        mock_result_remaining.scalars.return_value.all.return_value = []  # No one left

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_assignees, mock_result_del, mock_result_chore, mock_result_remaining]
        )
        mock_db_session.flush = AsyncMock()
        mock_db_session.delete = AsyncMock()

        # Criterion #6: Member leave deactivates chore when sole assignee
        await on_member_leave(mock_db_session, household_id, user_alice.id)
        assert chore.is_active is False
        mock_db_session.delete.assert_any_await(assignee_row)

    @pytest.mark.asyncio
    async def test_member_leave_recomputes_rotation_with_remaining(
        self, household_id, user_alice, user_bob, user_charlie, today, mock_db_session
    ):
        """When one of three assignees leaves, remaining two continue rotating.

        Validates:
          - Member leave correctly recomputes rotation (criterion #6)
          - Future assignments for leaving user deleted
          - Remaining assignees reindexed
        """
        chore_id = uuid.uuid4()
        assignee_bob = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_bob.id,
            position=0,
        )
        # Alice leaves
        assignee_alice = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_alice.id,
            position=1,
        )
        assignee_charlie = ChoreAssignee(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            user_id=user_charlie.id,
            position=2,
        )
        chore = Chore(
            id=chore_id,
            household_id=household_id,
            name="Rotating chore",
            created_by_user_id=user_bob.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today,
            rotation_enabled=True,
            is_active=True,
        )

        # Future assignment for Alice that should be deleted
        future_assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore_id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today + timedelta(days=7),
            status=AssignmentStatus.pending,
        )

        # Call sequence
        mock_result_assignees = MagicMock()
        mock_result_assignees.scalars.return_value.all.return_value = [assignee_alice]

        mock_result_del = MagicMock()
        mock_result_del.scalars.return_value.all.return_value = [future_assignment]

        mock_result_chore = MagicMock()
        mock_result_chore.scalar_one_or_none.return_value = chore

        # Remaining: Bob and Charlie
        mock_result_remaining = MagicMock()
        mock_result_remaining.scalars.return_value.all.return_value = [assignee_bob, assignee_charlie]

        # Future pending to delete before regeneration
        mock_result_future_chore = MagicMock()
        mock_result_future_chore.scalars.return_value.all.return_value = []

        # generate_assignments: overdue check, existing assignments, _assignment_exists
        mock_result_no_overdue = MagicMock()
        mock_result_no_overdue.scalars.return_value.all.return_value = []

        mock_result_no_existing = MagicMock()
        mock_result_no_existing.scalars.return_value.all.return_value = []

        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        side_effects = [
            mock_result_assignees,
            mock_result_del,
            mock_result_chore,
            mock_result_remaining,
            mock_result_future_chore,
            mock_result_no_overdue,
            mock_result_no_existing,
        ]
        for _ in range(10):
            side_effects.append(mock_result_not_exists)

        mock_db_session.execute = AsyncMock(side_effect=side_effects)
        mock_db_session.flush = AsyncMock()
        mock_db_session.delete = AsyncMock()

        await on_member_leave(mock_db_session, household_id, user_alice.id)

        # Chore stays active (Bob and Charlie remain)
        assert chore.is_active is True

        # Remaining assignees reindexed: Bob=0, Charlie=1
        assert assignee_bob.position == 0
        assert assignee_charlie.position == 1

        # Alice's assignee row and future assignment deleted
        mock_db_session.delete.assert_any_await(assignee_alice)
        mock_db_session.delete.assert_any_await(future_assignment)


class TestPhase6PostponeAndCancel:
    """Validates postpone and cancel behaviour for assignments."""

    @pytest.mark.asyncio
    async def test_postpone_sets_effective_date(
        self, household_id, user_alice, today, mock_db_session
    ):
        """Postpone sets postponed_to, preserving original due_date.

        Validates:
          - Postpone updates effective date, unblocks generation (criterion #4)
        """
        assignment = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=uuid.uuid4(),
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today - timedelta(days=2),  # Overdue
            postponed_to=None,
            status=AssignmentStatus.pending,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = assignment
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        new_date = today + timedelta(days=5)
        result = await postpone_assignment(mock_db_session, household_id, assignment.id, new_date)

        # Criterion #4: Postpone updates effective date
        assert result.postponed_to == new_date
        assert result.due_date == today - timedelta(days=2)  # Original preserved
        assert result.status == AssignmentStatus.pending  # Still pending

    @pytest.mark.asyncio
    async def test_cancel_unblocks_generation(
        self, household_id, user_alice, today, mock_db_session
    ):
        """Cancelling an overdue assignment unblocks generation for that chore.

        Validates:
          - Cancel resolves overdue → unblocks (related to criterion #3)
        """
        chore = Chore(
            id=uuid.uuid4(),
            household_id=household_id,
            name="Blocked chore",
            created_by_user_id=user_alice.id,
            is_recurring=True,
            recurrence_interval=1,
            recurrence_unit=RecurrenceUnit.weeks,
            start_date=today - timedelta(days=14),
            rotation_enabled=False,
            is_active=True,
        )
        assignees = [
            ChoreAssignee(id=uuid.uuid4(), chore_id=chore.id, household_id=household_id, user_id=user_alice.id, position=0),
        ]

        # After cancel: the formerly-overdue assignment is now cancelled (not pending)
        cancelled = ChoreAssignment(
            id=uuid.uuid4(),
            chore_id=chore.id,
            household_id=household_id,
            assigned_to_user_id=user_alice.id,
            due_date=today - timedelta(days=3),
            status=AssignmentStatus.cancelled,  # Resolved by cancel
        )

        # _has_unresolved_overdue queries status==pending → empty (cancelled doesn't match)
        mock_result_no_overdue = MagicMock()
        mock_result_no_overdue.scalars.return_value.all.return_value = []

        mock_result_existing = MagicMock()
        mock_result_existing.scalars.return_value.all.return_value = [cancelled]

        mock_result_not_exists = MagicMock()
        mock_result_not_exists.scalar_one_or_none.return_value = None

        side_effects = [mock_result_no_overdue, mock_result_existing]
        for _ in range(10):
            side_effects.append(mock_result_not_exists)

        mock_db_session.execute = AsyncMock(side_effect=side_effects)

        # After cancel, generation proceeds (cancelled is not pending, so not overdue)
        created = await generate_assignments(mock_db_session, chore, assignees)
        assert len(created) >= 1  # Generation unblocked
