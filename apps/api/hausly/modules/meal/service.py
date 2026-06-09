import uuid
from datetime import date

from hausly.modules.household.service import get_active_members
from hausly.modules.meal.models import MealPlanEntry
from hausly.modules.meal.schemas import MealEntryCreate, MealEntryUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class MealError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code


async def get_entries(
    db: AsyncSession,
    household_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[MealPlanEntry]:
    """Get meal plan entries for a date range."""
    stmt = (
        select(MealPlanEntry)
        .where(
            MealPlanEntry.household_id == household_id,
            MealPlanEntry.date >= start_date,
            MealPlanEntry.date <= end_date,
        )
        .order_by(MealPlanEntry.date, MealPlanEntry.slot)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_entry(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MealEntryCreate,
) -> MealPlanEntry:
    """Claim a meal slot. Fails with 409 if slot already taken."""
    # Check if slot is already claimed
    stmt = select(MealPlanEntry).where(
        MealPlanEntry.household_id == household_id,
        MealPlanEntry.date == data.date,
        MealPlanEntry.slot == data.slot,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise MealError(
            code="SLOT_TAKEN",
            detail=f"Slot '{data.slot.value}' on {data.date} is already claimed",
            status_code=409,
        )

    # Determine headcount: default to active member count
    headcount = data.headcount
    if headcount is None:
        members = await get_active_members(db, household_id)
        headcount = len(members)

    entry = MealPlanEntry(
        household_id=household_id,
        date=data.date,
        slot=data.slot,
        text=data.text,
        headcount=headcount,
        owner_user_id=user_id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def update_entry(
    db: AsyncSession,
    household_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: str,
    data: MealEntryUpdate,
) -> MealPlanEntry:
    """Update a meal entry. Only owner or admin can edit."""
    entry = await _get_entry(db, household_id, entry_id)

    if entry.owner_user_id != user_id and user_role != "admin":
        raise MealError(
            code="FORBIDDEN",
            detail="Only the owner or an admin can edit this entry",
            status_code=403,
        )

    if data.text is not None:
        entry.text = data.text
    if data.headcount is not None:
        entry.headcount = data.headcount

    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entry(
    db: AsyncSession,
    household_id: uuid.UUID,
    entry_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: str,
) -> None:
    """Delete a meal entry. Only owner or admin can delete."""
    entry = await _get_entry(db, household_id, entry_id)

    if entry.owner_user_id != user_id and user_role != "admin":
        raise MealError(
            code="FORBIDDEN",
            detail="Only the owner or an admin can delete this entry",
            status_code=403,
        )

    await db.delete(entry)
    await db.commit()


async def on_member_leave(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    leave_date: date,
) -> int:
    """Delete future entries owned by leaving user. Returns count deleted."""
    stmt = select(MealPlanEntry).where(
        MealPlanEntry.household_id == household_id,
        MealPlanEntry.owner_user_id == user_id,
        MealPlanEntry.date > leave_date,
    )
    result = await db.execute(stmt)
    entries = list(result.scalars().all())

    for entry in entries:
        await db.delete(entry)

    if entries:
        await db.commit()

    return len(entries)


async def _get_entry(
    db: AsyncSession,
    household_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> MealPlanEntry:
    """Fetch a meal entry by id, scoped to household."""
    stmt = select(MealPlanEntry).where(
        MealPlanEntry.id == entry_id,
        MealPlanEntry.household_id == household_id,
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is None:
        raise MealError(
            code="NOT_FOUND",
            detail="Meal entry not found",
            status_code=404,
        )
    return entry
