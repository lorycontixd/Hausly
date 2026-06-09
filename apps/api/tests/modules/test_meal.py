"""Tests for the meal planner module service layer."""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.modules.meal.models import MealPlanEntry, MealSlot
from hausly.modules.meal.schemas import MealEntryCreate, MealEntryUpdate
from hausly.modules.meal.service import (MealError, create_entry, delete_entry,
                                         get_entries, on_member_leave,
                                         update_entry)
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
def today():
    return date.today()


class TestGetEntries:
    @pytest.mark.asyncio
    async def test_get_entries_returns_list(self, household_id, today, mock_db_session):
        """Get entries returns entries within the date range."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Pasta",
            headcount=3,
            owner_user_id=uuid.uuid4(),
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [entry]
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_entries(
            mock_db_session, household_id, today, today + timedelta(days=7)
        )
        assert len(result) == 1
        assert result[0].text == "Pasta"

    @pytest.mark.asyncio
    async def test_get_entries_empty(self, household_id, today, mock_db_session):
        """Get entries returns empty list when no entries in range."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await get_entries(
            mock_db_session, household_id, today, today + timedelta(days=7)
        )
        assert result == []


class TestCreateEntry:
    @pytest.mark.asyncio
    async def test_create_entry_success(self, household_id, user_a, today, mock_db_session):
        """Creating an entry for a free slot succeeds."""
        data = MealEntryCreate(
            date=today,
            slot=MealSlot.dinner,
            text="Pizza night",
            headcount=4,
        )

        # Mock: no existing entry for this slot
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await create_entry(mock_db_session, household_id, user_a.id, data)
        assert result.text == "Pizza night"
        assert result.headcount == 4
        assert result.slot == MealSlot.dinner
        assert result.owner_user_id == user_a.id
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_entry_slot_taken_409(self, household_id, user_a, user_b, today, mock_db_session):
        """Creating an entry for an already-claimed slot returns 409."""
        existing = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Existing meal",
            headcount=3,
            owner_user_id=user_b.id,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        data = MealEntryCreate(
            date=today,
            slot=MealSlot.lunch,
            text="My meal",
        )

        with pytest.raises(MealError) as exc_info:
            await create_entry(mock_db_session, household_id, user_a.id, data)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "SLOT_TAKEN"

    @pytest.mark.asyncio
    async def test_create_entry_default_headcount(self, household_id, user_a, today, mock_db_session):
        """When headcount not provided, defaults to household member count."""
        data = MealEntryCreate(
            date=today,
            slot=MealSlot.dinner,
            text="Surprise dinner",
        )

        # Mock: no existing entry
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        # Mock get_active_members to return 3 members
        with patch(
            "hausly.modules.meal.service.get_active_members",
            new_callable=AsyncMock,
            return_value=[MagicMock(), MagicMock(), MagicMock()],
        ):
            result = await create_entry(mock_db_session, household_id, user_a.id, data)

        assert result.headcount == 3


class TestUpdateEntry:
    @pytest.mark.asyncio
    async def test_update_entry_owner_success(self, household_id, user_a, today, mock_db_session):
        """Owner can update their own entry."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Old text",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        data = MealEntryUpdate(text="New text", headcount=5)
        result = await update_entry(
            mock_db_session, household_id, entry.id, user_a.id, "member", data
        )
        assert result.text == "New text"
        assert result.headcount == 5

    @pytest.mark.asyncio
    async def test_update_entry_admin_success(self, household_id, user_a, user_b, today, mock_db_session):
        """Admin can update any entry."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Owner text",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        data = MealEntryUpdate(text="Admin edit")
        result = await update_entry(
            mock_db_session, household_id, entry.id, user_b.id, "admin", data
        )
        assert result.text == "Admin edit"

    @pytest.mark.asyncio
    async def test_update_entry_non_owner_forbidden(self, household_id, user_a, user_b, today, mock_db_session):
        """Non-owner non-admin cannot update an entry."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Owner text",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        data = MealEntryUpdate(text="Unauthorized edit")
        with pytest.raises(MealError) as exc_info:
            await update_entry(
                mock_db_session, household_id, entry.id, user_b.id, "member", data
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_update_entry_not_found(self, household_id, user_a, mock_db_session):
        """Updating a non-existent entry returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        data = MealEntryUpdate(text="Nope")
        with pytest.raises(MealError) as exc_info:
            await update_entry(
                mock_db_session, household_id, uuid.uuid4(), user_a.id, "member", data
            )
        assert exc_info.value.status_code == 404


class TestDeleteEntry:
    @pytest.mark.asyncio
    async def test_delete_entry_owner_success(self, household_id, user_a, today, mock_db_session):
        """Owner can delete their own entry."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.dinner,
            text="To delete",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()

        await delete_entry(mock_db_session, household_id, entry.id, user_a.id, "member")
        mock_db_session.delete.assert_awaited_once_with(entry)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_entry_non_owner_forbidden(self, household_id, user_a, user_b, today, mock_db_session):
        """Non-owner non-admin cannot delete an entry."""
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.dinner,
            text="Protected",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(MealError) as exc_info:
            await delete_entry(
                mock_db_session, household_id, entry.id, user_b.id, "member"
            )
        assert exc_info.value.status_code == 403


class TestOnMemberLeave:
    @pytest.mark.asyncio
    async def test_on_member_leave_deletes_future_entries(self, household_id, user_a, today, mock_db_session):
        """Leaving member's future entries are deleted."""
        future_entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today + timedelta(days=3),
            slot=MealSlot.lunch,
            text="Future meal",
            headcount=2,
            owner_user_id=user_a.id,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [future_entry]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()

        count = await on_member_leave(mock_db_session, household_id, user_a.id, today)
        assert count == 1
        mock_db_session.delete.assert_awaited_once_with(future_entry)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_member_leave_no_future_entries(self, household_id, user_a, today, mock_db_session):
        """No entries to delete when member has no future entries."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await on_member_leave(mock_db_session, household_id, user_a.id, today)
        assert count == 0
        mock_db_session.commit.assert_not_awaited()
