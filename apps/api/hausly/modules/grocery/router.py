import uuid

from fastapi import APIRouter, Depends, HTTPException
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.dependencies import get_household_membership, require_module
from hausly.modules.grocery import service
from hausly.modules.grocery.schemas import (ArchiveRequest, GroceryItemCreate,
                                            GroceryItemResponse,
                                            GroceryItemUpdate,
                                            GroceryListResponse,
                                            SessionCompleteRequest,
                                            SessionCompleteResponse)
from hausly.modules.grocery.service import GroceryError
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/v1/households/{household_id}/grocery",
    tags=["grocery"],
    dependencies=[Depends(require_module("grocery"))],
)


def _handle_service_error(e: GroceryError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("/lists", response_model=list[GroceryListResponse])
async def get_lists(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[GroceryListResponse]:
    lists = await service.get_lists(db, household_id)
    return [GroceryListResponse.model_validate(gl) for gl in lists]


@router.get("/lists/{list_id}/items", response_model=list[GroceryItemResponse])
async def get_items(
    household_id: uuid.UUID,
    list_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[GroceryItemResponse]:
    items = await service.get_items(db, household_id, list_id, user.id)
    return [GroceryItemResponse.model_validate(item) for item in items]


@router.post("/items", response_model=list[GroceryItemResponse], status_code=201)
async def add_items(
    household_id: uuid.UUID,
    items_data: list[GroceryItemCreate],
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[GroceryItemResponse]:
    try:
        items = await service.add_items(db, household_id, user.id, items_data)
    except GroceryError as e:
        _handle_service_error(e)
    return [GroceryItemResponse.model_validate(item) for item in items]


@router.patch("/items/{item_id}", response_model=GroceryItemResponse)
async def update_item(
    household_id: uuid.UUID,
    item_id: uuid.UUID,
    data: GroceryItemUpdate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> GroceryItemResponse:
    try:
        item = await service.update_item(db, household_id, item_id, user.id, data)
    except GroceryError as e:
        _handle_service_error(e)
    return GroceryItemResponse.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    household_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_item(db, household_id, item_id, user.id)
    except GroceryError as e:
        _handle_service_error(e)


@router.post("/session/complete", response_model=SessionCompleteResponse)
async def complete_session(
    household_id: uuid.UUID,
    data: SessionCompleteRequest,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> SessionCompleteResponse:
    try:
        result = await service.complete_session(db, household_id, user.id, data)
    except GroceryError as e:
        _handle_service_error(e)
    return result


@router.post("/lists/archive", status_code=204)
async def archive_list(
    household_id: uuid.UUID,
    data: ArchiveRequest,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not data.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmation required to archive the list",
        )
    await service.archive_list(db, household_id)
