import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.dependencies import get_household_membership, require_module
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.meal import service
from hausly.modules.meal.schemas import (MealEntryCreate, MealEntryResponse,
                                         MealEntryUpdate)
from hausly.modules.meal.service import MealError
from hausly.modules.users.models import User
from hausly.realtime.signalr import signalr_service
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

router = APIRouter(
    prefix="/api/v1/households/{household_id}/meals",
    tags=["meals"],
    dependencies=[Depends(require_module("meal"))],
)


def _handle_service_error(e: MealError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _get_display_name(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    """Look up a user's display_name by id."""
    result = await db.execute(select(User.display_name).where(User.id == user_id))
    return result.scalar_one_or_none()


async def _build_response(
    db: AsyncSession, entry, current_user: User
) -> MealEntryResponse:
    """Build a MealEntryResponse with owner_display_name populated."""
    if entry.owner_user_id == current_user.id:
        display_name = current_user.display_name
    else:
        display_name = await _get_display_name(db, entry.owner_user_id)
    data = MealEntryResponse.model_validate(entry)
    data.owner_display_name = display_name or "Unknown"
    return data


@router.get("", response_model=list[MealEntryResponse])
async def get_entries(
    household_id: uuid.UUID,
    start: date = Query(..., description="Start date (inclusive)"),
    end: date = Query(..., description="End date (inclusive)"),
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[MealEntryResponse]:
    entries = await service.get_entries(db, household_id, start, end)
    # Batch-fetch display names for all unique owners
    owner_ids = {e.owner_user_id for e in entries}
    name_map: dict[uuid.UUID, str | None] = {}
    for oid in owner_ids:
        if oid == user.id:
            name_map[oid] = user.display_name
        else:
            name_map[oid] = await _get_display_name(db, oid)
    results = []
    for e in entries:
        resp = MealEntryResponse.model_validate(e)
        resp.owner_display_name = name_map.get(e.owner_user_id) or "Unknown"
        results.append(resp)
    return results


@router.post("", response_model=MealEntryResponse, status_code=201)
async def create_entry(
    household_id: uuid.UUID,
    data: MealEntryCreate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> MealEntryResponse:
    try:
        entry = await service.create_entry(db, household_id, user.id, data)
    except MealError as e:
        _handle_service_error(e)
    # Owner is always the current user on create
    resp = MealEntryResponse.model_validate(entry)
    resp.owner_display_name = user.display_name
    await signalr_service.meal_entry_created(household_id, resp.model_dump(mode="json"))
    return resp


@router.patch("/{entry_id}", response_model=MealEntryResponse)
async def update_entry(
    household_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: MealEntryUpdate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> MealEntryResponse:
    try:
        entry = await service.update_entry(
            db, household_id, entry_id, user.id, membership.role.value, data
        )
    except MealError as e:
        _handle_service_error(e)
    resp = await _build_response(db, entry, user)
    await signalr_service.meal_entry_updated(household_id, resp.model_dump(mode="json"))
    return resp


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    household_id: uuid.UUID,
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_entry(
            db, household_id, entry_id, user.id, membership.role.value
        )
    except MealError as e:
        _handle_service_error(e)
    await signalr_service.meal_entry_removed(household_id, str(entry_id))
