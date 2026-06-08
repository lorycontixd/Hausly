"""Smoke test: Phase 3 — Grocery Module end-to-end.

Validates Phase 3 success criteria from implementation-plan-v1.md:
  - Add/update/delete items works
  - Personal items hidden from non-owners
  - Session complete: items archived, draft expense created
  - Duplicate detection prevents same-name item in active list
  - Archive list works without creating expense

Also validates key behaviours from docs/logics/grocery-session.md:
  - Personal items excluded from expense generation
  - Already-archived items silently skipped (simultaneous shopping)
  - Equal split across all active household members
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

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
def household_id():
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def active_list(household_id):
    return GroceryList(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        household_id=household_id,
        name="Shopping List",
        is_active=True,
    )


@pytest.fixture
def household_settings(household_id):
    return HouseholdSettings(
        household_id=household_id,
        default_currency="EUR",
        enabled_modules=["grocery", "expense", "meal", "chores"],
    )


@pytest.fixture
def memberships(household_id, user_alice, user_bob):
    return [
        HouseholdMembership(
            id=uuid.uuid4(),
            household_id=household_id,
            user_id=user_alice.id,
            role=MemberRole.admin,
        ),
        HouseholdMembership(
            id=uuid.uuid4(),
            household_id=household_id,
            user_id=user_bob.id,
            role=MemberRole.member,
        ),
    ]


class TestPhase3GroceryLifecycle:
    """End-to-end smoke test: add items → shop → session complete → expense draft.

    Success criteria: Full grocery lifecycle works from adding items to generating
    an expense draft via session completion.
    """

    @pytest.mark.asyncio
    async def test_grocery_lifecycle_end_to_end(
        self, household_id, user_alice, user_bob, active_list, household_settings, memberships, mock_db_session
    ):
        """Full flow: add items → complete session → expense draft generated.

        Validates:
          - Add items works (success criterion #1)
          - Session complete archives items and creates expense draft (criterion #3)
          - Equal split across all active household members (grocery-session.md)
        """
        # --- Step 1: Add items to the active list ---
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )
        mock_db_session.refresh = AsyncMock()

        items_data = [
            GroceryItemCreate(name="Milk", quantity=2, unit="L"),
            GroceryItemCreate(name="Eggs", quantity=12, unit="pcs"),
            GroceryItemCreate(name="Bread"),
        ]
        created = await add_items(mock_db_session, household_id, user_alice.id, items_data)

        # Success criterion: Add items works
        assert len(created) == 3
        assert created[0].name == "Milk"
        assert created[0].added_by_user_id == user_alice.id
        assert created[1].name == "Eggs"
        assert created[2].name == "Bread"

        # --- Step 2: Complete shopping session with expense ---
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = created

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = household_settings

        mock_members_result = MagicMock()
        mock_members_result.scalars.return_value.all.return_value = memberships

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_items_result, mock_settings_result, mock_members_result]
        )

        session_data = SessionCompleteRequest(
            bought_item_ids=[item.id for item in created],
            receipt_total=35.50,
            create_expense=True,
        )
        result = await complete_session(mock_db_session, household_id, user_alice.id, session_data)

        # Success criterion: Session complete — items archived
        assert result.items_removed == 3
        for item in created:
            assert item.is_bought is True
            assert item.is_archived is True
            assert item.bought_by_user_id == user_alice.id

        # Success criterion: Draft expense created
        assert result.expense_draft_id is not None
        assert result.expense_draft is not None
        assert result.expense_draft["amount"] == 35.50
        assert result.expense_draft["status"] == "draft"
        assert result.expense_draft["source"] == "grocery_integration"
        assert result.expense_draft["currency"] == "EUR"
        assert result.expense_draft["paid_by_user_id"] == str(user_alice.id)

        # grocery-session.md: equal split across ALL active household members
        splits = result.expense_draft["splits"]
        assert len(splits) == 2
        assert splits[0]["share_amount"] == 17.75  # 35.50 / 2
        assert splits[1]["share_amount"] == 17.75

        # grocery-session.md: title follows format "Groceries — {n} items"
        assert result.expense_draft["title"] == "Groceries — 3 items"

        # grocery-session.md: description is comma-separated item names
        assert "Milk" in result.expense_draft["description"]
        assert "Eggs" in result.expense_draft["description"]
        assert "Bread" in result.expense_draft["description"]


class TestPhase3PersonalItemVisibility:
    """Smoke test: personal item filtering rules.

    Success criteria: Personal items hidden from non-owners.
    """

    @pytest.mark.asyncio
    async def test_personal_items_end_to_end_visibility(
        self, household_id, user_alice, user_bob, active_list, mock_db_session
    ):
        """Validate the full personal item visibility matrix from grocery-session.md.

        | Non-personal        | visible to all  |
        | Personal (visible)  | visible to all  |
        | Personal (hidden)   | visible ONLY to owner |
        """
        list_id = active_list.id

        shared_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Shared Bread",
            added_by_user_id=user_alice.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )
        visible_personal = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Alice Toothbrush",
            added_by_user_id=user_alice.id,
            is_personal=True,
            personal_for_user_id=user_alice.id,
            personal_visibility=PersonalVisibility.visible,
        )
        hidden_personal_alice = GroceryItem(
            id=uuid.uuid4(),
            list_id=list_id,
            household_id=household_id,
            name="Secret Item",
            added_by_user_id=user_alice.id,
            is_personal=True,
            personal_for_user_id=user_alice.id,
            personal_visibility=PersonalVisibility.hidden,
        )

        all_items = [shared_item, visible_personal, hidden_personal_alice]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = all_items
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Bob sees: shared + visible personal, NOT hidden personal
        bob_items = await get_items(mock_db_session, household_id, list_id, user_bob.id)
        assert len(bob_items) == 2
        item_names = {i.name for i in bob_items}
        assert "Shared Bread" in item_names
        assert "Alice Toothbrush" in item_names
        assert "Secret Item" not in item_names  # Success criterion: hidden from non-owner

        # Alice sees all (she owns the hidden item)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        alice_items = await get_items(mock_db_session, household_id, list_id, user_alice.id)
        assert len(alice_items) == 3
        assert "Secret Item" in {i.name for i in alice_items}


class TestPhase3DuplicateDetection:
    """Smoke test: duplicate detection prevents same-name item.

    Success criteria: Duplicate detection prevents same-name item in active list.
    """

    @pytest.mark.asyncio
    async def test_duplicate_detection_case_insensitive(
        self, household_id, user_alice, active_list, mock_db_session
    ):
        """Case-insensitive duplicate detection across the active list."""
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        # "Milk" already exists in the list
        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = ["Milk"]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )

        # Try adding "milk" (lowercase) — should conflict
        items_data = [GroceryItemCreate(name="milk")]

        with pytest.raises(GroceryError) as exc_info:
            await add_items(mock_db_session, household_id, user_alice.id, items_data)

        assert exc_info.value.code == "DUPLICATE_ITEM"
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_duplicate_detection_within_batch(
        self, household_id, user_alice, active_list, mock_db_session
    ):
        """Adding the same item twice in one batch should fail on the duplicate."""
        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        mock_names_result = MagicMock()
        mock_names_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_names_result]
        )
        mock_db_session.refresh = AsyncMock()

        # "Milk" appears twice in the batch
        items_data = [
            GroceryItemCreate(name="Milk"),
            GroceryItemCreate(name="milk"),  # duplicate within batch
        ]

        with pytest.raises(GroceryError) as exc_info:
            await add_items(mock_db_session, household_id, user_alice.id, items_data)

        assert exc_info.value.code == "DUPLICATE_ITEM"


class TestPhase3ArchiveList:
    """Smoke test: archive list does NOT create an expense.

    Success criteria: Archive list works without creating expense.
    """

    @pytest.mark.asyncio
    async def test_archive_list_no_expense_created(
        self, household_id, active_list, mock_db_session
    ):
        """Archiving (clear list) deactivates the list and archives all items.
        Does NOT trigger any expense creation — distinct from session complete.
        """
        items = [
            GroceryItem(
                id=uuid.uuid4(),
                list_id=active_list.id,
                household_id=household_id,
                name="Leftover Item 1",
                added_by_user_id=uuid.uuid4(),
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
            GroceryItem(
                id=uuid.uuid4(),
                list_id=active_list.id,
                household_id=household_id,
                name="Leftover Item 2",
                added_by_user_id=uuid.uuid4(),
                is_personal=False,
                personal_visibility=PersonalVisibility.visible,
            ),
        ]

        mock_list_result = MagicMock()
        mock_list_result.scalar_one_or_none.return_value = active_list

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = items

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_list_result, mock_items_result]
        )

        await archive_list(mock_db_session, household_id)

        # List is deactivated and archived
        assert active_list.is_active is False
        assert active_list.archived_at is not None

        # All items are archived
        for item in items:
            assert item.is_archived is True

        # Commit called exactly once — no expense service interaction
        mock_db_session.commit.assert_awaited_once()


class TestPhase3SessionEdgeCases:
    """Smoke test: session completion edge cases from grocery-session.md."""

    @pytest.mark.asyncio
    async def test_session_complete_personal_items_excluded_from_expense(
        self, household_id, user_alice, household_settings, memberships, mock_db_session
    ):
        """Personal items are archived but NOT included in the expense draft.

        grocery-session.md key rule: Personal items are always excluded from
        expense generation regardless of visibility setting.
        """
        shared_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Shared Milk",
            added_by_user_id=user_alice.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )
        personal_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="My Shampoo",
            added_by_user_id=user_alice.id,
            is_personal=True,
            personal_for_user_id=user_alice.id,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = [shared_item, personal_item]

        mock_settings_result = MagicMock()
        mock_settings_result.scalar_one_or_none.return_value = household_settings

        mock_members_result = MagicMock()
        mock_members_result.scalars.return_value.all.return_value = memberships

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_items_result, mock_settings_result, mock_members_result]
        )

        data = SessionCompleteRequest(
            bought_item_ids=[shared_item.id, personal_item.id],
            receipt_total=20.0,
            create_expense=True,
        )

        result = await complete_session(mock_db_session, household_id, user_alice.id, data)

        # Both items archived
        assert result.items_removed == 2
        assert shared_item.is_archived is True
        assert personal_item.is_archived is True

        # Expense only mentions the shared item
        assert result.expense_draft["title"] == "Groceries — 1 items"
        assert "Shared Milk" in result.expense_draft["description"]
        assert "My Shampoo" not in result.expense_draft["description"]

    @pytest.mark.asyncio
    async def test_session_complete_simultaneous_shopping_skips_archived(
        self, household_id, user_bob, mock_db_session
    ):
        """Simultaneous shopping: second session silently skips already-archived items.

        grocery-session.md: If both check the same item, first session/complete
        archives it; second call silently skips items that are already archived.
        """
        # The query filters by is_archived == False, so already-archived items
        # won't appear in the result — simulating this with an empty result.
        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_items_result)

        data = SessionCompleteRequest(
            bought_item_ids=[uuid.uuid4(), uuid.uuid4()],  # IDs of already-archived items
            receipt_total=15.0,
            create_expense=False,
        )

        result = await complete_session(mock_db_session, household_id, user_bob.id, data)

        # No error — silently handles the overlap
        assert result.items_removed == 0
        assert result.expense_draft_id is None

    @pytest.mark.asyncio
    async def test_session_complete_no_expense_when_only_personal_items(
        self, household_id, user_alice, household_settings, memberships, mock_db_session
    ):
        """If all checked items are personal, no expense draft is created even
        with create_expense=True.
        """
        personal_only = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Personal Razor",
            added_by_user_id=user_alice.id,
            is_personal=True,
            personal_for_user_id=user_alice.id,
            personal_visibility=PersonalVisibility.visible,
        )

        mock_items_result = MagicMock()
        mock_items_result.scalars.return_value.all.return_value = [personal_only]

        mock_db_session.execute = AsyncMock(return_value=mock_items_result)

        data = SessionCompleteRequest(
            bought_item_ids=[personal_only.id],
            receipt_total=8.0,
            create_expense=True,  # Requested but should not happen
        )

        result = await complete_session(mock_db_session, household_id, user_alice.id, data)

        # Item archived
        assert result.items_removed == 1
        assert personal_only.is_archived is True

        # No expense created (no non-personal items to include)
        assert result.expense_draft_id is None
        assert result.expense_draft is None


class TestPhase3ItemCRUD:
    """Smoke test: update and delete operations with ownership rules.

    Success criteria: Add/update/delete items works.
    """

    @pytest.mark.asyncio
    async def test_update_then_delete_shared_item(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Any household member can update and delete shared items."""
        item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Milk",
            quantity=1,
            added_by_user_id=user_alice.id,
            is_personal=False,
            personal_visibility=PersonalVisibility.visible,
        )

        # Bob updates Alice's shared item — should succeed
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = item
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        updated = await update_item(
            mock_db_session, household_id, item.id, user_bob.id,
            GroceryItemUpdate(name="Oat Milk", quantity=2)
        )
        assert updated.name == "Oat Milk"
        assert updated.quantity == 2

        # Bob deletes the item — should succeed
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()
        await delete_item(mock_db_session, household_id, item.id, user_bob.id)
        mock_db_session.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_personal_item_ownership_protection(
        self, household_id, user_alice, user_bob, mock_db_session
    ):
        """Personal items can only be modified by their owner."""
        personal_item = GroceryItem(
            id=uuid.uuid4(),
            list_id=uuid.uuid4(),
            household_id=household_id,
            name="Alice's Private Item",
            added_by_user_id=user_alice.id,
            is_personal=True,
            personal_for_user_id=user_alice.id,
            personal_visibility=PersonalVisibility.hidden,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = personal_item
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        # Bob tries to update — should fail
        with pytest.raises(GroceryError) as exc_info:
            await update_item(
                mock_db_session, household_id, personal_item.id, user_bob.id,
                GroceryItemUpdate(name="Hacked!")
            )
        assert exc_info.value.status_code == 403

        # Bob tries to delete — should fail
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        with pytest.raises(GroceryError) as exc_info:
            await delete_item(mock_db_session, household_id, personal_item.id, user_bob.id)
        assert exc_info.value.status_code == 403

        # Alice updates — should succeed
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()
        updated = await update_item(
            mock_db_session, household_id, personal_item.id, user_alice.id,
            GroceryItemUpdate(name="Updated Private Item")
        )
        assert updated.name == "Updated Private Item"
