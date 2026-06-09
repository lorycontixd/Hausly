import uuid
from datetime import UTC, date, datetime, timedelta

from dateutil.relativedelta import relativedelta
from hausly.modules.chores.models import (AssignmentStatus, Chore,
                                          ChoreAssignee, ChoreAssignment,
                                          RecurrenceUnit)
from hausly.modules.chores.schemas import ChoreCreate, ChoreUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

HORIZON_DAYS = 14


class ChoreError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code


def _advance_date(current: date, interval: int, unit: RecurrenceUnit) -> date:
    """Advance a date by the given recurrence interval."""
    if unit == RecurrenceUnit.days:
        return current + timedelta(days=interval)
    elif unit == RecurrenceUnit.weeks:
        return current + timedelta(weeks=interval)
    elif unit == RecurrenceUnit.months:
        return current + relativedelta(months=interval)
    return current


async def _load_assignees(db: AsyncSession, chore_id: uuid.UUID) -> list[ChoreAssignee]:
    """Load assignees for a chore, ordered by position."""
    stmt = (
        select(ChoreAssignee)
        .where(ChoreAssignee.chore_id == chore_id)
        .order_by(ChoreAssignee.position)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _load_assignments(
    db: AsyncSession, chore_id: uuid.UUID
) -> list[ChoreAssignment]:
    """Load all assignments for a chore."""
    stmt = select(ChoreAssignment).where(ChoreAssignment.chore_id == chore_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _has_unresolved_overdue(db: AsyncSession, chore_id: uuid.UUID) -> bool:
    """Check if a chore has any unresolved overdue assignments."""
    today = date.today()
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.chore_id == chore_id,
        ChoreAssignment.status == AssignmentStatus.pending,
    )
    result = await db.execute(stmt)
    for assignment in result.scalars().all():
        effective_date = assignment.postponed_to or assignment.due_date
        if effective_date < today:
            return True
    return False


async def _assignment_exists(
    db: AsyncSession,
    chore_id: uuid.UUID,
    due_date: date,
    user_id: uuid.UUID,
) -> bool:
    """Check if an assignment already exists for a given chore/date/user."""
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.chore_id == chore_id,
        ChoreAssignment.due_date == due_date,
        ChoreAssignment.assigned_to_user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def generate_assignments(
    db: AsyncSession,
    chore: Chore,
    assignees: list[ChoreAssignee],
    horizon_days: int = HORIZON_DAYS,
) -> list[ChoreAssignment]:
    """Generate assignments up to horizon_days ahead. Idempotent.
    
    For recurring chores: generates from start_date forward.
    For one-off chores: creates one assignment per assignee at start_date.
    """
    if not assignees:
        return []

    created: list[ChoreAssignment] = []
    today = date.today()
    horizon = today + timedelta(days=horizon_days)

    if not chore.is_recurring:
        # One-off: one assignment per assignee on start_date
        if chore.rotation_enabled:
            # Rotation on one-off: assign to first person only
            assignee = assignees[0]
            if not await _assignment_exists(db, chore.id, chore.start_date, assignee.user_id):
                assignment = ChoreAssignment(
                    chore_id=chore.id,
                    household_id=chore.household_id,
                    assigned_to_user_id=assignee.user_id,
                    due_date=chore.start_date,
                )
                db.add(assignment)
                created.append(assignment)
        else:
            for assignee in assignees:
                if not await _assignment_exists(db, chore.id, chore.start_date, assignee.user_id):
                    assignment = ChoreAssignment(
                        chore_id=chore.id,
                        household_id=chore.household_id,
                        assigned_to_user_id=assignee.user_id,
                        due_date=chore.start_date,
                    )
                    db.add(assignment)
                    created.append(assignment)
        return created

    # Recurring: generate from start_date up to horizon
    # Check overdue blocking
    if await _has_unresolved_overdue(db, chore.id):
        return []

    # Count existing assignments to determine occurrence_index for rotation
    existing_stmt = select(ChoreAssignment).where(
        ChoreAssignment.chore_id == chore.id,
    ).order_by(ChoreAssignment.due_date)
    existing_result = await db.execute(existing_stmt)
    existing = list(existing_result.scalars().all())

    # Find existing due dates per assignee for idempotency
    existing_keys: set[tuple[date, uuid.UUID]] = set()
    for a in existing:
        existing_keys.add((a.due_date, a.assigned_to_user_id))

    # Compute occurrence index offset from existing assignments
    if chore.rotation_enabled:
        # Count distinct due_dates to find how many occurrences exist
        existing_due_dates = sorted({a.due_date for a in existing})
        occurrence_index = len(existing_due_dates)
    else:
        occurrence_index = 0  # Not used for shared assignment

    # Walk forward from start_date to find next due dates
    current_date = chore.start_date
    occurrence_count = 0

    while current_date <= horizon:
        if current_date >= today or (current_date, assignees[0].user_id if chore.rotation_enabled else assignees[0].user_id) not in existing_keys:
            if current_date >= today:
                if chore.rotation_enabled:
                    # Rotation: pick one assignee based on total occurrence count
                    total_occurrence = occurrence_count
                    assignee = assignees[total_occurrence % len(assignees)]
                    key = (current_date, assignee.user_id)
                    if key not in existing_keys:
                        assignment = ChoreAssignment(
                            chore_id=chore.id,
                            household_id=chore.household_id,
                            assigned_to_user_id=assignee.user_id,
                            due_date=current_date,
                        )
                        db.add(assignment)
                        created.append(assignment)
                        existing_keys.add(key)
                else:
                    # Shared: one assignment per assignee
                    for assignee in assignees:
                        key = (current_date, assignee.user_id)
                        if key not in existing_keys:
                            assignment = ChoreAssignment(
                                chore_id=chore.id,
                                household_id=chore.household_id,
                                assigned_to_user_id=assignee.user_id,
                                due_date=current_date,
                            )
                            db.add(assignment)
                            created.append(assignment)
                            existing_keys.add(key)

        occurrence_count += 1
        current_date = _advance_date(chore.start_date, chore.recurrence_interval * occurrence_count, chore.recurrence_unit)

    return created


async def create_chore(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ChoreCreate,
) -> Chore:
    """Create a chore with assignees and generate initial assignments."""
    # Validate creator is in assignees
    if user_id not in data.assignee_user_ids:
        raise ChoreError(
            code="CREATOR_NOT_IN_ASSIGNEES",
            detail="Creator must be included in the assignee list",
            status_code=400,
        )

    chore = Chore(
        household_id=household_id,
        name=data.name,
        created_by_user_id=user_id,
        is_recurring=data.is_recurring,
        recurrence_interval=data.recurrence_interval,
        recurrence_unit=data.recurrence_unit,
        start_date=data.start_date,
        rotation_enabled=data.rotation_enabled,
        is_active=True,
    )
    db.add(chore)
    await db.flush()

    # Create assignees with positions
    assignees: list[ChoreAssignee] = []
    for position, uid in enumerate(data.assignee_user_ids):
        assignee = ChoreAssignee(
            chore_id=chore.id,
            household_id=household_id,
            user_id=uid,
            position=position,
        )
        db.add(assignee)
        assignees.append(assignee)

    await db.flush()

    # Generate initial assignments
    await generate_assignments(db, chore, assignees)

    await db.commit()
    await db.refresh(chore)

    chore.assignees = await _load_assignees(db, chore.id)
    return chore


async def get_chores(
    db: AsyncSession,
    household_id: uuid.UUID,
) -> list[Chore]:
    """Get all active chores for a household with assignees."""
    stmt = select(Chore).where(
        Chore.household_id == household_id,
        Chore.is_active == True,  # noqa: E712
    ).order_by(Chore.created_at.desc())
    result = await db.execute(stmt)
    chores = list(result.scalars().all())

    for chore in chores:
        chore.assignees = await _load_assignees(db, chore.id)

    return chores


async def get_chore(
    db: AsyncSession,
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
) -> Chore:
    """Get a single chore with assignees."""
    stmt = select(Chore).where(
        Chore.id == chore_id,
        Chore.household_id == household_id,
    )
    result = await db.execute(stmt)
    chore = result.scalar_one_or_none()

    if chore is None:
        raise ChoreError(
            code="CHORE_NOT_FOUND",
            detail="Chore not found",
            status_code=404,
        )

    chore.assignees = await _load_assignees(db, chore.id)
    return chore


async def update_chore(
    db: AsyncSession,
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
    data: ChoreUpdate,
) -> Chore:
    """Update a chore. Recomputes assignees if changed."""
    chore = await get_chore(db, household_id, chore_id)

    update_data = data.model_dump(exclude_unset=True, exclude={"assignee_user_ids"})
    for field, value in update_data.items():
        setattr(chore, field, value)

    # If assignees changed, replace them
    if data.assignee_user_ids is not None:
        # Delete existing assignees
        existing = await _load_assignees(db, chore.id)
        for a in existing:
            await db.delete(a)

        # Create new assignees
        new_assignees: list[ChoreAssignee] = []
        for position, uid in enumerate(data.assignee_user_ids):
            assignee = ChoreAssignee(
                chore_id=chore.id,
                household_id=household_id,
                user_id=uid,
                position=position,
            )
            db.add(assignee)
            new_assignees.append(assignee)

        await db.flush()

        # Delete future pending assignments and regenerate
        today = date.today()
        stmt = select(ChoreAssignment).where(
            ChoreAssignment.chore_id == chore.id,
            ChoreAssignment.status == AssignmentStatus.pending,
            ChoreAssignment.due_date >= today,
        )
        result = await db.execute(stmt)
        for assignment in result.scalars().all():
            await db.delete(assignment)

        await db.flush()

        if chore.is_recurring:
            await generate_assignments(db, chore, new_assignees)

    await db.commit()
    await db.refresh(chore)

    chore.assignees = await _load_assignees(db, chore.id)
    return chore


async def delete_chore(
    db: AsyncSession,
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
) -> None:
    """Deactivate a chore and delete future pending assignments."""
    chore = await get_chore(db, household_id, chore_id)

    chore.is_active = False

    # Delete future pending assignments
    today = date.today()
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.chore_id == chore.id,
        ChoreAssignment.status == AssignmentStatus.pending,
        ChoreAssignment.due_date >= today,
    )
    result = await db.execute(stmt)
    for assignment in result.scalars().all():
        await db.delete(assignment)

    await db.commit()


async def get_assignments(
    db: AsyncSession,
    household_id: uuid.UUID,
    status: AssignmentStatus | None = None,
    user_id: uuid.UUID | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ChoreAssignment]:
    """List assignments with optional filters."""
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.household_id == household_id,
    ).order_by(ChoreAssignment.due_date)

    if status is not None:
        stmt = stmt.where(ChoreAssignment.status == status)
    if user_id is not None:
        stmt = stmt.where(ChoreAssignment.assigned_to_user_id == user_id)
    if start_date is not None:
        stmt = stmt.where(ChoreAssignment.due_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(ChoreAssignment.due_date <= end_date)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def complete_assignment(
    db: AsyncSession,
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChoreAssignment:
    """Mark an assignment as completed. Any household member can do this."""
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.id == assignment_id,
        ChoreAssignment.household_id == household_id,
    )
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise ChoreError(
            code="ASSIGNMENT_NOT_FOUND",
            detail="Assignment not found",
            status_code=404,
        )

    if assignment.status != AssignmentStatus.pending:
        raise ChoreError(
            code="ASSIGNMENT_NOT_PENDING",
            detail="Only pending assignments can be completed",
            status_code=400,
        )

    assignment.status = AssignmentStatus.completed
    assignment.completed_at = datetime.now(UTC)
    assignment.completed_by_user_id = user_id

    await db.commit()
    await db.refresh(assignment)

    # Check if one-off chore should auto-deactivate
    chore_stmt = select(Chore).where(Chore.id == assignment.chore_id)
    chore_result = await db.execute(chore_stmt)
    chore = chore_result.scalar_one_or_none()

    if chore and not chore.is_recurring:
        # Check if all assignments are in terminal state
        all_assignments_stmt = select(ChoreAssignment).where(
            ChoreAssignment.chore_id == chore.id,
        )
        all_result = await db.execute(all_assignments_stmt)
        all_assignments = list(all_result.scalars().all())

        all_terminal = all(
            a.status in (AssignmentStatus.completed, AssignmentStatus.cancelled)
            for a in all_assignments
        )
        if all_terminal:
            chore.is_active = False
            await db.commit()

    return assignment


async def postpone_assignment(
    db: AsyncSession,
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
    new_date: date,
) -> ChoreAssignment:
    """Postpone an overdue assignment to a new date."""
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.id == assignment_id,
        ChoreAssignment.household_id == household_id,
    )
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise ChoreError(
            code="ASSIGNMENT_NOT_FOUND",
            detail="Assignment not found",
            status_code=404,
        )

    if assignment.status != AssignmentStatus.pending:
        raise ChoreError(
            code="ASSIGNMENT_NOT_PENDING",
            detail="Only pending assignments can be postponed",
            status_code=400,
        )

    # Only overdue assignments can be postponed (per spec)
    today = date.today()
    effective_date = assignment.postponed_to or assignment.due_date
    if effective_date >= today:
        raise ChoreError(
            code="NOT_OVERDUE",
            detail="Only overdue assignments can be postponed",
            status_code=400,
        )

    assignment.postponed_to = new_date

    await db.commit()
    await db.refresh(assignment)
    return assignment


async def cancel_assignment(
    db: AsyncSession,
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
) -> ChoreAssignment:
    """Cancel a pending assignment."""
    stmt = select(ChoreAssignment).where(
        ChoreAssignment.id == assignment_id,
        ChoreAssignment.household_id == household_id,
    )
    result = await db.execute(stmt)
    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise ChoreError(
            code="ASSIGNMENT_NOT_FOUND",
            detail="Assignment not found",
            status_code=404,
        )

    if assignment.status != AssignmentStatus.pending:
        raise ChoreError(
            code="ASSIGNMENT_NOT_PENDING",
            detail="Only pending assignments can be cancelled",
            status_code=400,
        )

    assignment.status = AssignmentStatus.cancelled

    await db.commit()
    await db.refresh(assignment)

    # Check if one-off chore should auto-deactivate
    chore_stmt = select(Chore).where(Chore.id == assignment.chore_id)
    chore_result = await db.execute(chore_stmt)
    chore = chore_result.scalar_one_or_none()

    if chore and not chore.is_recurring:
        all_assignments_stmt = select(ChoreAssignment).where(
            ChoreAssignment.chore_id == chore.id,
        )
        all_result = await db.execute(all_assignments_stmt)
        all_assignments = list(all_result.scalars().all())

        all_terminal = all(
            a.status in (AssignmentStatus.completed, AssignmentStatus.cancelled)
            for a in all_assignments
        )
        if all_terminal:
            chore.is_active = False
            await db.commit()

    return assignment


async def on_member_leave(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Handle member leaving: remove from assignees, delete future assignments, recompute."""
    # Find all chores where this user is an assignee
    stmt = select(ChoreAssignee).where(
        ChoreAssignee.household_id == household_id,
        ChoreAssignee.user_id == user_id,
    )
    result = await db.execute(stmt)
    assignee_rows = list(result.scalars().all())

    affected_chore_ids = {a.chore_id for a in assignee_rows}

    # Remove user from assignee lists
    for a in assignee_rows:
        await db.delete(a)

    # Delete future pending assignments for this user
    today = date.today()
    del_stmt = select(ChoreAssignment).where(
        ChoreAssignment.household_id == household_id,
        ChoreAssignment.assigned_to_user_id == user_id,
        ChoreAssignment.status == AssignmentStatus.pending,
        ChoreAssignment.due_date >= today,
    )
    del_result = await db.execute(del_stmt)
    for assignment in del_result.scalars().all():
        await db.delete(assignment)

    await db.flush()

    # Recompute rotation for affected chores
    for chore_id in affected_chore_ids:
        chore_stmt = select(Chore).where(Chore.id == chore_id)
        chore_result = await db.execute(chore_stmt)
        chore = chore_result.scalar_one_or_none()

        if chore is None or not chore.is_active:
            continue

        remaining_assignees = await _load_assignees(db, chore_id)

        if not remaining_assignees:
            # No assignees left — deactivate chore
            chore.is_active = False
        else:
            # Reorder positions
            for i, assignee in enumerate(remaining_assignees):
                assignee.position = i

            # Delete future pending assignments for this chore and regenerate
            future_stmt = select(ChoreAssignment).where(
                ChoreAssignment.chore_id == chore_id,
                ChoreAssignment.status == AssignmentStatus.pending,
                ChoreAssignment.due_date >= today,
            )
            future_result = await db.execute(future_stmt)
            for fa in future_result.scalars().all():
                await db.delete(fa)

            await db.flush()

            if chore.is_recurring:
                await generate_assignments(db, chore, remaining_assignees)

    await db.commit()
