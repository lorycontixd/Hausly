import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.dependencies import get_household_membership, require_module
from hausly.modules.chores import service
from hausly.modules.chores.models import AssignmentStatus
from hausly.modules.chores.schemas import (AssignmentResponse, ChoreCreate,
                                           ChoreResponse, ChoreUpdate,
                                           PostponeRequest)
from hausly.modules.chores.service import ChoreError
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.users.models import User
from hausly.realtime.signalr import signalr_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/v1/households/{household_id}/chores",
    tags=["chores"],
    dependencies=[Depends(require_module("chores"))],
)


def _handle_service_error(e: ChoreError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _build_chore_response(db: AsyncSession, chore) -> ChoreResponse:
    """Build a ChoreResponse with enriched assignees."""
    enriched_assignees = await service.enrich_assignees(db, chore.assignees)
    return ChoreResponse.model_validate({
        "id": chore.id,
        "household_id": chore.household_id,
        "name": chore.name,
        "created_by_user_id": chore.created_by_user_id,
        "is_recurring": chore.is_recurring,
        "recurrence_interval": chore.recurrence_interval,
        "recurrence_unit": chore.recurrence_unit,
        "start_date": chore.start_date,
        "rotation_enabled": chore.rotation_enabled,
        "is_active": chore.is_active,
        "created_at": chore.created_at,
        "assignees": enriched_assignees,
    })


@router.get("", response_model=list[ChoreResponse])
async def list_chores(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[ChoreResponse]:
    chores = await service.get_chores(db, household_id)
    return [await _build_chore_response(db, c) for c in chores]


@router.post("", response_model=ChoreResponse, status_code=201)
async def create_chore(
    household_id: uuid.UUID,
    data: ChoreCreate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ChoreResponse:
    try:
        chore = await service.create_chore(db, household_id, user.id, data)
    except ChoreError as e:
        _handle_service_error(e)
    resp = await _build_chore_response(db, chore)
    await signalr_service.chore_created(household_id, resp.model_dump(mode="json"))
    return resp


@router.get("/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    household_id: uuid.UUID,
    status: AssignmentStatus | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentResponse]:
    assignments = await service.get_assignments(
        db, household_id, status=status, user_id=user_id,
        start_date=start_date, end_date=end_date,
    )
    enriched = await service.enrich_assignments(db, assignments)
    return [AssignmentResponse.model_validate(e) for e in enriched]


@router.get("/{chore_id}", response_model=ChoreResponse)
async def get_chore(
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ChoreResponse:
    try:
        chore = await service.get_chore(db, household_id, chore_id)
    except ChoreError as e:
        _handle_service_error(e)
    return await _build_chore_response(db, chore)


@router.patch("/{chore_id}", response_model=ChoreResponse)
async def update_chore(
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
    data: ChoreUpdate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ChoreResponse:
    try:
        chore = await service.update_chore(db, household_id, chore_id, data)
    except ChoreError as e:
        _handle_service_error(e)
    return await _build_chore_response(db, chore)


@router.delete("/{chore_id}", status_code=204)
async def delete_chore(
    household_id: uuid.UUID,
    chore_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_chore(db, household_id, chore_id)
    except ChoreError as e:
        _handle_service_error(e)
    await signalr_service.chore_deleted(household_id, str(chore_id))


@router.post("/assignments/{assignment_id}/complete", response_model=AssignmentResponse)
async def complete_assignment(
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResponse:
    try:
        assignment = await service.complete_assignment(db, household_id, assignment_id, user.id)
    except ChoreError as e:
        _handle_service_error(e)
    enriched = await service.enrich_assignment(db, assignment)
    resp = AssignmentResponse.model_validate(enriched)
    await signalr_service.assignment_completed(
        household_id, str(assignment_id), str(user.id)
    )
    return resp


@router.post("/assignments/{assignment_id}/postpone", response_model=AssignmentResponse)
async def postpone_assignment(
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: PostponeRequest,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResponse:
    try:
        assignment = await service.postpone_assignment(
            db, household_id, assignment_id, data.postpone_to
        )
    except ChoreError as e:
        _handle_service_error(e)
    enriched = await service.enrich_assignment(db, assignment)
    resp = AssignmentResponse.model_validate(enriched)
    await signalr_service.assignment_updated(household_id, resp.model_dump(mode="json"))
    return resp


@router.post("/assignments/{assignment_id}/cancel", response_model=AssignmentResponse)
async def cancel_assignment(
    household_id: uuid.UUID,
    assignment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> AssignmentResponse:
    try:
        assignment = await service.cancel_assignment(db, household_id, assignment_id)
    except ChoreError as e:
        _handle_service_error(e)
    enriched = await service.enrich_assignment(db, assignment)
    resp = AssignmentResponse.model_validate(enriched)
    await signalr_service.assignment_updated(household_id, resp.model_dump(mode="json"))
    return resp
