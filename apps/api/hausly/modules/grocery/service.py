import uuid
from datetime import UTC, datetime

from hausly.modules.grocery.models import GroceryItem, GroceryList
from hausly.modules.grocery.schemas import (GroceryItemCreate,
                                            GroceryItemUpdate,
                                            SessionCompleteRequest,
                                            SessionCompleteResponse)
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.household.service import get_household_settings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class GroceryError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code


async def get_active_list(
    db: AsyncSession, household_id: uuid.UUID
) -> GroceryList:
    """Get or create the active grocery list for a household."""
    stmt = select(GroceryList).where(
        GroceryList.household_id == household_id,
        GroceryList.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    grocery_list = result.scalar_one_or_none()

    if grocery_list is None:
        grocery_list = GroceryList(household_id=household_id)
        db.add(grocery_list)
        await db.commit()
        await db.refresh(grocery_list)

    return grocery_list


async def get_lists(
    db: AsyncSession, household_id: uuid.UUID
) -> list[GroceryList]:
    """Get all lists (active + archived) for a household."""
    stmt = select(GroceryList).where(
        GroceryList.household_id == household_id
    ).order_by(GroceryList.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_items(
    db: AsyncSession,
    household_id: uuid.UUID,
    list_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[GroceryItem]:
    """Get items in a list, filtering hidden personal items for non-owners."""
    stmt = select(GroceryItem).where(
        GroceryItem.list_id == list_id,
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    # Filter hidden personal items: only show to owner
    return [
        item
        for item in items
        if not (
            item.is_personal
            and item.personal_visibility.value == "hidden"
            and item.personal_for_user_id != user_id
        )
    ]


async def add_items(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    items_data: list[GroceryItemCreate],
) -> list[GroceryItem]:
    """Add items to the active grocery list with duplicate detection."""
    grocery_list = await get_active_list(db, household_id)

    # Get existing item names for duplicate detection
    stmt = select(GroceryItem.name).where(
        GroceryItem.list_id == grocery_list.id,
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    existing_names = {name.lower() for name in result.scalars().all()}

    created_items: list[GroceryItem] = []
    for item_data in items_data:
        if item_data.name.strip().lower() in existing_names:
            raise GroceryError(
                code="DUPLICATE_ITEM",
                detail=f"Item '{item_data.name}' already exists in the active list",
                status_code=409,
            )

        item = GroceryItem(
            list_id=grocery_list.id,
            household_id=household_id,
            name=item_data.name.strip(),
            quantity=item_data.quantity,
            unit=item_data.unit,
            added_by_user_id=user_id,
            source=item_data.source,
            is_personal=item_data.is_personal,
            personal_for_user_id=user_id if item_data.is_personal else None,
            personal_visibility=item_data.personal_visibility,
        )
        db.add(item)
        created_items.append(item)
        existing_names.add(item_data.name.strip().lower())

    await db.commit()
    for item in created_items:
        await db.refresh(item)
    return created_items


async def update_item(
    db: AsyncSession,
    household_id: uuid.UUID,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    data: GroceryItemUpdate,
) -> GroceryItem:
    """Update a grocery item. Personal items can only be updated by their owner."""
    stmt = select(GroceryItem).where(
        GroceryItem.id == item_id,
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if item is None:
        raise GroceryError(
            code="ITEM_NOT_FOUND",
            detail="Grocery item not found",
            status_code=404,
        )

    # Personal items can only be updated by their owner
    if item.is_personal and item.personal_for_user_id != user_id:
        raise GroceryError(
            code="FORBIDDEN",
            detail="Cannot update another user's personal item",
            status_code=403,
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    # If marking as personal, set personal_for_user_id
    if data.is_personal is True and not item.personal_for_user_id:
        item.personal_for_user_id = user_id

    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(
    db: AsyncSession,
    household_id: uuid.UUID,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Delete a grocery item. Personal items can only be deleted by their owner."""
    stmt = select(GroceryItem).where(
        GroceryItem.id == item_id,
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if item is None:
        raise GroceryError(
            code="ITEM_NOT_FOUND",
            detail="Grocery item not found",
            status_code=404,
        )

    if item.is_personal and item.personal_for_user_id != user_id:
        raise GroceryError(
            code="FORBIDDEN",
            detail="Cannot delete another user's personal item",
            status_code=403,
        )

    await db.delete(item)
    await db.commit()


async def complete_session(
    db: AsyncSession,
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SessionCompleteRequest,
) -> SessionCompleteResponse:
    """Complete a shopping session: mark items bought, archive, optionally create expense draft."""
    # Fetch all bought items
    stmt = select(GroceryItem).where(
        GroceryItem.id.in_(data.bought_item_ids),
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    now = datetime.now(UTC)
    items_removed = 0

    non_personal_names: list[str] = []
    for item in items:
        item.is_bought = True
        item.bought_by_user_id = user_id
        item.bought_at = now
        item.is_archived = True
        items_removed += 1

        if not item.is_personal:
            non_personal_names.append(item.name)

    expense_draft_id: uuid.UUID | None = None
    expense_draft: dict | None = None

    if data.create_expense and non_personal_names:
        # Get household settings for currency
        settings = await get_household_settings(db, household_id)

        # Get active household members for equal split
        members_stmt = select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.left_at == None,  # noqa: E711
        )
        members_result = await db.execute(members_stmt)
        active_members = list(members_result.scalars().all())

        member_count = len(active_members)
        share_amount = round(data.receipt_total / member_count, 2) if member_count > 0 else data.receipt_total

        expense_draft_id = uuid.uuid4()
        expense_draft = {
            "id": str(expense_draft_id),
            "household_id": str(household_id),
            "title": f"Groceries — {len(non_personal_names)} items",
            "amount": data.receipt_total,
            "currency": settings.default_currency,
            "paid_by_user_id": str(user_id),
            "status": "draft",
            "source": "grocery_integration",
            "description": ", ".join(non_personal_names),
            "splits": [
                {
                    "user_id": str(m.user_id),
                    "share_amount": share_amount,
                }
                for m in active_members
            ],
        }

    await db.commit()

    return SessionCompleteResponse(
        items_removed=items_removed,
        expense_draft_id=expense_draft_id,
        expense_draft=expense_draft,
    )


async def archive_list(
    db: AsyncSession, household_id: uuid.UUID
) -> None:
    """Archive the active list. Does NOT create an expense."""
    grocery_list = await get_active_list(db, household_id)

    now = datetime.now(UTC)
    grocery_list.is_active = False
    grocery_list.archived_at = now

    # Mark all items as archived
    stmt = select(GroceryItem).where(
        GroceryItem.list_id == grocery_list.id,
        GroceryItem.household_id == household_id,
        GroceryItem.is_archived == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    for item in items:
        item.is_archived = True

    await db.commit()
