"""Tests for the grocery module service layer."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.modules.grocery.models import (GroceryItem, GroceryList,
                                           ItemSource, PersonalVisibility)
from hausly.modules.grocery.schemas import (GroceryItemCreate,
                                            GroceryItemUpdate,
                                            SessionCompleteRequest)
from hausly.modules.grocery.service import (GroceryError, add_items,
                                            archive_list, complete_session,
                                            delete_item, get_active_list,
                                            get_items, update_item)
from hausly.modules.household.models import (HouseholdMembership,
                                             HouseholdSettings, MemberRole)
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


@pytest.fixture
def active_list(household_id):
    return GroceryList(
        id=uuid.uuid4(),
        household_id=household_id,
        name="Shopping List",
        is_active=True,
    )


class TestGetActiveList:
    @pytest.mark.asyncio
    async def test_returns_existing_active_list(self, household_id, active_list, mock_db_session):
        """Should return the existing active list without creating a new one."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = active_list
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_active_list(mock_db_session, household_id)
        assert result.id == active_list.id
        assert result.is_active is True
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_new_list_if_none_exists(self, household_id, mock_db_session):
        """Should create a new active list if none exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await get_active_list(mock_db_session, household_id)
        assert result.household_id == household_id
        assert result.is_active is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_awaited_once()


class TestGetItems:
    @pytest.mark.asyncio
    async def test_filters_hidden_personal_items_for_non_owners(
        self, household_id, user_a, user_b, active_list, mock_db_session
    ):
        """Hidden personal items should not be visible to non-owners."""
        list_id = active_list.id

        shared_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Milk",
            added_by_user_id=user_a.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )
        hidden_personal = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Secret Thing",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.hidden,
        )
        visible_personal = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Toothbrush",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            shared_item,
            hidden_personal,
            visible_personal,
        ]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # user_b should not see user_a's hidden personal item
        items = await get_items(mock_db_session, household_id, list_id, user_b.id)
        assert len(items) == 2
        assert shared_item in items
        assert visible_personal in items
        assert hidden_personal not in items

    @pytest.mark.asyncio
    async def test_owner_sees_own_hidden_personal_items(
        self, household_id, user_a, active_list, mock_db_session
    ):
        """Owner should see their own hidden personal items."""
        list_id = active_list.id

        hidden_personal = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Secret Thing",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.hidden,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [hidden_personal]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        items = await get_items(mock_db_session, household_id, list_id, user_a.id)
        assert len(items) == 1
        assert hidden_personal in items


class TestAddItems:
    @pytest.mark.asyncio
    async def test_add_item_success(self, household_id, user_a, active_list, mock_db_session):
        """Adding a new item should succeed when no duplicate exists."""
        # Mock get_active_list call
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        # Mock existing names query (empty)
        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        items_data = [GroceryItemCreate(name="Milk", quantity=2, unit="L")]
        result = await add_items(mock_db_session, household_id, user_a.id, items_data)

        assert len(result) == 1
        assert result[0].name == "Milk"
        assert result[0].quantity == 2
        assert result[0].added_by_user_id == user_a.id
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_duplicate_item_raises_error(
        self, household_id, user_a, active_list, mock_db_session
    ):
        """Adding a duplicate item (case-insensitive) should raise DUPLICATE_ITEM."""
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        # "milk" already exists
        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = ["milk"]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )

        items_data = [GroceryItemCreate(name="Milk")]

        with pytest.raises(GroceryError) as exc_info:
            await add_items(mock_db_session, household_id, user_a.id, items_data)

        assert exc_info.value.code == "DUPLICATE_ITEM"
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_add_personal_item_sets_personal_for_user_id(
        self, household_id, user_a, active_list, mock_db_session
    ):
        """Personal items should have personal_for_user_id set to the adding user."""
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )

        async def fake_refresh(obj):
            pass

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        items_data = [GroceryItemCreate(name="Toothbrush", is_personal=True)]
        result = await add_items(mock_db_session, household_id, user_a.id, items_data)

        assert result[0].is_personal is True
        assert result[0].personal_for_user_id == user_a.id


class TestUpdateItem:
    @pytest.mark.asyncio
    async def test_update_item_success(self, household_id, user_a, mock_db_session):
        """Updating an item should succeed for shared items."""
        item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Milk",
            added_by_user_id=user_a.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        data = GroceryItemUpdate(name="Oat Milk", quantity=1)
        result = await update_item(mock_db_session, household_id, item.id, user_a.id, data)

        assert result.name == "Oat Milk"
        assert result.quantity == 1
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_personal_item_by_non_owner_raises_error(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Non-owner cannot update another user's personal item."""
        item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Personal Thing",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        data = GroceryItemUpdate(name="Hacked")

        with pytest.raises(GroceryError) as exc_info:
            await update_item(mock_db_session, household_id, item.id, user_b.id, data)

        assert exc_info.value.code == "FORBIDDEN"
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_nonexistent_item_raises_error(
        self, household_id, user_a, mock_db_session
    ):
        """Updating a non-existent item should return 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        data = GroceryItemUpdate(name="Ghost")

        with pytest.raises(GroceryError) as exc_info:
            await update_item(mock_db_session, household_id, uuid.uuid4(), user_a.id, data)

        assert exc_info.value.code == "ITEM_NOT_FOUND"
        assert exc_info.value.status_code == 404


class TestDeleteItem:
    @pytest.mark.asyncio
    async def test_delete_item_success(self, household_id, user_a, mock_db_session):
        """Deleting an item should succeed for shared items."""
        item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Milk",
            added_by_user_id=user_a.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()

        await delete_item(mock_db_session, household_id, item.id, user_a.id)
        mock_db_session.delete.assert_awaited_once_with(item)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_personal_item_by_non_owner_raises_error(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Non-owner cannot delete another user's personal item."""
        item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Personal",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(GroceryError) as exc_info:
            await delete_item(mock_db_session, household_id, item.id, user_b.id)

        assert exc_info.value.code == "FORBIDDEN"
        assert exc_info.value.status_code == 403


class TestCompleteSession:
    @pytest.mark.asyncio
    async def test_complete_session_creates_expense_draft(
        self, household_id, user_a, user_b, mock_db_session
    ):
        """Session complete with create_expense=True should produce an expense draft."""
        items = [
            GroceryItem(
                id=uuid.uuid4(),
                list_id=uuid.uuid4(),
                household_id=household_id,
                name="Milk",
                added_by_user_id=user_a.id,
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
            GroceryItem(
                id=uuid.uuid4(),
                list_id=uuid.uuid4(),
                household_id=household_id,
                name="Eggs",
                added_by_user_id=user_a.id,
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
        ]

        settings = HouseholdSettings(
            household_id=household_id,
            default_currency="EUR",
        )
        memberships = [
            HouseholdMembership(
                id=uuid.uuid4(),
                household_id=household_id,
                user_id=user_a.id,
                role=MemberRole.admin,
            ),
            HouseholdMembership(
                id=uuid.uuid4(),
                household_id=household_id,
                user_id=user_b.id,
                role=MemberRole.member,
            ),
        ]

        # Mock: items query, settings query, members query
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = items

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = settings

        mock_members_result = MagicMock()
        mock_members_result.scalars.return_value.all.return_value = memberships

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_items_result, mock_settings_result, mock_members_result]
        )

        data = SessionCompleteRequest(
            bought_item_ids=[item.id for item in items],
            receipt_total=25.0,
            create_expense=True,
        )

        result = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert result.items_removed == 2
        assert result.expense_draft_id is not None
        assert result.expense_draft is not None
        assert result.expense_draft["amount"] == 25.0
        assert result.expense_draft["status"] == "draft"
        assert result.expense_draft["source"] == "grocery_integration"
        assert len(result.expense_draft["splits"]) == 2
        # Equal split: 25.0 / 2 = 12.5
        assert result.expense_draft["splits"][0]["share_amount"] == 12.5

        # Verify items are archived
        for item in items:
            assert item.is_bought is True
            assert item.is_archived is True
            assert item.bought_by_user_id == user_a.id

        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_complete_session_excludes_personal_items_from_expense(
        self, household_id, user_a, mock_db_session
    ):
        """Personal items should be archived but excluded from the expense draft."""
        shared_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Milk",
            added_by_user_id=user_a.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )
        personal_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Toothbrush",
            added_by_user_id=user_a.id,
            is_personal=True,
            personal_for_user_id=user_a.id,
            personal_visibility=PersonalVisibility.visible,
        )

        settings = HouseholdSettings(
            household_id=household_id, default_currency="EUR"
        )
        memberships = [
            HouseholdMembership(
                id=uuid.uuid4(),
                household_id=household_id,
                user_id=user_a.id,
                role=MemberRole.admin,
            ),
        ]

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = [shared_item, personal_item]

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = settings

        mock_members_result = MagicMock()
        mock_members_result.scalars.return_value.all.return_value = memberships

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_items_result, mock_settings_result, mock_members_result]
        )

        data = SessionCompleteRequest(
            bought_item_ids=[shared_item.id, personal_item.id],
            receipt_total=30.0,
            create_expense=True,
        )

        result = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert result.items_removed == 2
        # Expense only mentions the shared item
        assert result.expense_draft["title"] == "Groceries — 1 items"
        assert "Toothbrush" not in result.expense_draft["description"]
        assert "Milk" in result.expense_draft["description"]

        # Both items still archived
        assert shared_item.is_archived is True
        assert personal_item.is_archived is True

    @pytest.mark.asyncio
    async def test_complete_session_without_expense(
        self, household_id, user_a, mock_db_session
    ):
        """Session complete with create_expense=False should not create expense."""
        items = [
            GroceryItem(
                id=uuid.uuid4(),
                list_id=uuid.uuid4(),
                household_id=household_id,
                name="Bread",
                added_by_user_id=user_a.id,
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
        ]

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = items

        mock_db_session.execute = AsyncMock(return_value=mock_items_result)

        data = SessionCompleteRequest(
            bought_item_ids=[items[0].id],
            receipt_total=3.0,
            create_expense=False,
        )

        result = await complete_session(mock_db_session, household_id, user_a.id, data)

        assert result.items_removed == 1
        assert result.expense_draft_id is None
        assert result.expense_draft is None
        assert items[0].is_archived is True

    @pytest.mark.asyncio
    async def test_complete_session_skips_already_archived_items(
        self, household_id, user_a, mock_db_session
    ):
        """Already-archived items (bought by another user) should be silently skipped."""
        # The query only returns non-archived items, so an ID for an archived item
        # simply won't appear in results — items_removed will be 0.
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_items_result)

        data = SessionCompleteRequest(
            bought_item_ids=[uuid.uuid4()],
            receipt_total=10.0,
            create_expense=False,
        )

        result = await complete_session(mock_db_session, household_id, user_a.id, data)
        assert result.items_removed == 0


class TestArchiveList:
    @pytest.mark.asyncio
    async def test_archive_list_success(self, household_id, active_list, mock_db_session):
        """Archiving should deactivate the list and mark all items as archived."""
        items = [
            GroceryItem(
                id=uuid.uuid4(),
                list_id=active_list.id,
                household_id=household_id,
                name="Item1",
                added_by_user_id=uuid.uuid4(),
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
        ]

        # First call: get_active_list, second call: get items
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = items

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_items_result]
        )

        await archive_list(mock_db_session, household_id)

        assert active_list.is_active is False
        assert active_list.archived_at is not None
        assert items[0].is_archived is True
        mock_db_session.commit.assert_awaited_once()
