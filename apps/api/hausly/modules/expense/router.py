import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.dependencies import get_household_membership, require_module
from hausly.modules.expense import service
from hausly.modules.expense.models import ExpenseStatus
from hausly.modules.expense.schemas import (BalanceResponse, ExpenseCreate,
                                            ExpenseResponse, ExpenseUpdate,
                                            SettlementResponse, SplitResponse)
from hausly.modules.expense.service import ExpenseError
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.users.models import User
from hausly.realtime.signalr import signalr_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/api/v1/households/{household_id}/expenses",
    tags=["expenses"],
    dependencies=[Depends(require_module("expense"))],
)


def _handle_service_error(e: ExpenseError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    household_id: uuid.UUID,
    status: ExpenseStatus | None = Query(None),
    category: str | None = Query(None),
    cursor: uuid.UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[ExpenseResponse]:
    expenses = await service.list_expenses(
        db, household_id, status=status, category=category, cursor=cursor, limit=limit
    )
    return [ExpenseResponse.model_validate(e) for e in expenses]


@router.post("", response_model=ExpenseResponse, status_code=201)
async def create_expense(
    household_id: uuid.UUID,
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        expense = await service.create_expense(db, household_id, data)
    except ExpenseError as e:
        _handle_service_error(e)
    resp = ExpenseResponse.model_validate(expense)
    await signalr_service.expense_created(household_id, resp.model_dump(mode="json"))
    return resp


@router.get("/balances", response_model=BalanceResponse)
async def get_balances(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> BalanceResponse:
    balances = await service.get_balances(db, household_id)
    return BalanceResponse(balances=balances)


@router.get("/settlements", response_model=SettlementResponse)
async def get_settlements(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> SettlementResponse:
    settlements = await service.get_settlements(db, household_id)
    return SettlementResponse(settlements=settlements)


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        expense = await service.get_expense(db, household_id, expense_id)
    except ExpenseError as e:
        _handle_service_error(e)
    return ExpenseResponse.model_validate(expense)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    data: ExpenseUpdate,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        expense = await service.update_expense(db, household_id, expense_id, data)
    except ExpenseError as e:
        _handle_service_error(e)
    return ExpenseResponse.model_validate(expense)


@router.post("/{expense_id}/confirm", response_model=ExpenseResponse)
async def confirm_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> ExpenseResponse:
    try:
        expense = await service.confirm_expense(db, household_id, expense_id)
    except ExpenseError as e:
        _handle_service_error(e)
    await signalr_service.expense_confirmed(household_id, str(expense_id))
    return ExpenseResponse.model_validate(expense)


@router.delete("/{expense_id}", status_code=204)
async def delete_expense(
    household_id: uuid.UUID,
    expense_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.delete_expense(db, household_id, expense_id)
    except ExpenseError as e:
        _handle_service_error(e)


@router.post("/splits/{split_id}/settle", response_model=SplitResponse)
async def settle_split(
    household_id: uuid.UUID,
    split_id: uuid.UUID,
    user: User = Depends(get_current_user),
    membership: HouseholdMembership = Depends(get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> SplitResponse:
    try:
        split = await service.settle_split(db, household_id, split_id)
    except ExpenseError as e:
        _handle_service_error(e)
    await signalr_service.expense_settled(household_id, str(split_id))
    return SplitResponse.model_validate(split)
