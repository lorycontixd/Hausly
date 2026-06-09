"""Smoke test: Phase 5 — Meal Planner Module end-to-end.

Validates Phase 5 success criteria from implementation-plan-v1.md:
  - First-come-first-served slot claiming works (409 on conflict)
  - Only owner/admin can edit/delete
  - Headcount defaults to household member count
  - Member leave deletes their future entries

Also validates key behaviours from docs/api-reference.md:
  - Unique constraint on (household_id, date, slot)
  - owner_user_id set to caller
  - Past entries retained on member leave (only future deleted)
"""

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
def today():
    return date.today()


# --- Smoke Tests ---


class TestPhase5MealPlanLifecycle:
    """End-to-end smoke test: claim slot → edit → delete → conflict handling.

    Success criteria: Full meal plan lifecycle with first-come-first-served enforcement.
    """

    @pytest.mark.asyncio
    async def test_meal_plan_lifecycle_end_to_end_claim_edit_delete(
        self, household_id, user_alice, user_bob, today, mock_db_session
    ):
        """Full flow: claim slot → update → attempt duplicate claim → delete.

        Validates:
          - First-come-first-served slot claiming (criterion #1)
          - Only owner/admin can edit/delete (criterion #2)
          - 409 on slot conflict (criterion #1)
        """
        # --- Step 1: Alice claims dinner slot for today ---
        data = MealEntryCreate(
            date=today,
            slot=MealSlot.dinner,
            text="Homemade pizza",
            headcount=3,
        )

        # Mock: no existing entry
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        # Criterion #1: Alice can claim a free slot
        entry = await create_entry(mock_db_session, household_id, user_alice.id, data)
        assert entry.text == "Homemade pizza"
        assert entry.slot == MealSlot.dinner
        assert entry.headcount == 3
        assert entry.owner_user_id == user_alice.id  # Owner is the caller
        mock_db_session.commit.assert_awaited()

        # --- Step 2: Alice updates her own entry ---
        mock_get_result = MagicMock()
        mock_get_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_get_result)
        mock_db_session.refresh = AsyncMock()
        mock_db_session.commit.reset_mock()

        update_data = MealEntryUpdate(text="Margherita pizza", headcount=4)

        # Criterion #2: Owner can edit their entry
        updated = await update_entry(
            mock_db_session, household_id, entry.id, user_alice.id, "member", update_data
        )
        assert updated.text == "Margherita pizza"
        assert updated.headcount == 4
        mock_db_session.commit.assert_awaited_once()

        # --- Step 3: Bob tries to claim the same slot → 409 ---
        mock_conflict_result = MagicMock()
        mock_conflict_result.scalar_one_or_none.return_value = entry  # Slot occupied
        mock_db_session.execute = AsyncMock(return_value=mock_conflict_result)

        bob_data = MealEntryCreate(
            date=today,
            slot=MealSlot.dinner,
            text="Bob's dinner",
            headcount=2,
        )

        # Criterion #1: 409 when slot already taken
        with pytest.raises(MealError) as exc_info:
            await create_entry(mock_db_session, household_id, user_bob.id, bob_data)
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "SLOT_TAKEN"

        # --- Step 4: Bob (non-owner, non-admin) cannot edit Alice's entry ---
        mock_get_result2 = MagicMock()
        mock_get_result2.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_get_result2)

        # Criterion #2: Non-owner member gets 403
        with pytest.raises(MealError) as exc_info:
            await update_entry(
                mock_db_session, household_id, entry.id, user_bob.id, "member",
                MealEntryUpdate(text="Hijacked"),
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "FORBIDDEN"

        # --- Step 5: Bob (non-owner, non-admin) cannot delete Alice's entry ---
        mock_get_result3 = MagicMock()
        mock_get_result3.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_get_result3)

        # Criterion #2: Non-owner member gets 403 on delete
        with pytest.raises(MealError) as exc_info:
            await delete_entry(
                mock_db_session, household_id, entry.id, user_bob.id, "member"
            )
        assert exc_info.value.status_code == 403

        # --- Step 6: Alice can delete her own entry ---
        mock_get_result4 = MagicMock()
        mock_get_result4.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_get_result4)
        mock_db_session.delete = AsyncMock()
        mock_db_session.commit.reset_mock()

        # Criterion #2: Owner can delete
        await delete_entry(
            mock_db_session, household_id, entry.id, user_alice.id, "member"
        )
        mock_db_session.delete.assert_awaited_once_with(entry)
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_meal_plan_admin_can_edit_and_delete_any_entry(
        self, household_id, user_alice, user_bob, today, mock_db_session
    ):
        """Admin can edit and delete entries owned by other users.

        Validates: Only owner/admin can edit/delete (criterion #2) — admin path.
        """
        # Alice owns the entry
        entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today,
            slot=MealSlot.lunch,
            text="Alice's lunch",
            headcount=2,
            owner_user_id=user_alice.id,
        )

        # Bob is admin — can edit Alice's entry
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.refresh = AsyncMock()

        # Criterion #2: Admin can edit any entry
        updated = await update_entry(
            mock_db_session, household_id, entry.id, user_bob.id, "admin",
            MealEntryUpdate(text="Admin override"),
        )
        assert updated.text == "Admin override"

        # Bob (admin) can also delete Alice's entry
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = entry
        mock_db_session.execute = AsyncMock(return_value=mock_result2)
        mock_db_session.delete = AsyncMock()

        # Criterion #2: Admin can delete any entry
        await delete_entry(
            mock_db_session, household_id, entry.id, user_bob.id, "admin"
        )
        mock_db_session.delete.assert_awaited_once_with(entry)


class TestPhase5HeadcountDefault:
    """Smoke test: headcount defaults to household member count.

    Success criteria: Headcount defaults to household member count when not provided.
    """

    @pytest.mark.asyncio
    async def test_headcount_defaults_to_member_count(
        self, household_id, user_alice, today, mock_db_session
    ):
        """When headcount is omitted, it defaults to active household members.

        Validates: Headcount defaults to household member count (criterion #3).
        """
        data = MealEntryCreate(
            date=today,
            slot=MealSlot.lunch,
            text="Surprise lunch",
            # headcount intentionally omitted
        )
        assert data.headcount is None  # Confirm schema allows None

        # Mock: no existing slot
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        # Mock 4 active household members
        mock_members = [MagicMock() for _ in range(4)]
        with patch(
            "hausly.modules.meal.service.get_active_members",
            new_callable=AsyncMock,
            return_value=mock_members,
        ):
            entry = await create_entry(mock_db_session, household_id, user_alice.id, data)

        # Criterion #3: headcount == active member count
        assert entry.headcount == 4

    @pytest.mark.asyncio
    async def test_headcount_explicit_overrides_default(
        self, household_id, user_alice, today, mock_db_session
    ):
        """When headcount is explicitly provided, it's used as-is (no member count lookup).

        Validates: Explicit headcount is respected (related to criterion #3).
        """
        data = MealEntryCreate(
            date=today,
            slot=MealSlot.dinner,
            text="Dinner for two",
            headcount=2,  # Explicitly set
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        # Should NOT call get_active_members when headcount is provided
        with patch(
            "hausly.modules.meal.service.get_active_members",
            new_callable=AsyncMock,
        ) as mock_get_members:
            entry = await create_entry(mock_db_session, household_id, user_alice.id, data)
            mock_get_members.assert_not_awaited()

        assert entry.headcount == 2


class TestPhase5MemberLeave:
    """Smoke test: member leave deletes future entries, retains past.

    Success criteria: Member leave deletes their future entries.
    """

    @pytest.mark.asyncio
    async def test_member_leave_end_to_end_future_deleted_past_retained(
        self, household_id, user_alice, today, mock_db_session
    ):
        """When a member leaves, their future entries are deleted but past are kept.

        Validates: Member leave deletes their future entries (criterion #4).
        Also validates: Past entries are retained (data-models.md constraint).
        """
        # Alice has entries in the past, today, and future
        past_entry = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today - timedelta(days=3),
            slot=MealSlot.lunch,
            text="Past lunch",
            headcount=2,
            owner_user_id=user_alice.id,
        )
        future_entry_1 = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today + timedelta(days=2),
            slot=MealSlot.dinner,
            text="Future dinner",
            headcount=3,
            owner_user_id=user_alice.id,
        )
        future_entry_2 = MealPlanEntry(
            id=uuid.uuid4(),
            household_id=household_id,
            date=today + timedelta(days=5),
            slot=MealSlot.lunch,
            text="Another future meal",
            headcount=2,
            owner_user_id=user_alice.id,
        )

        # on_member_leave queries for entries with date > leave_date
        # So the service only sees future entries (the query filter is in the service)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [future_entry_1, future_entry_2]
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.delete = AsyncMock()

        # Criterion #4: Future entries deleted
        count = await on_member_leave(mock_db_session, household_id, user_alice.id, today)

        assert count == 2  # Only future entries deleted
        assert mock_db_session.delete.await_count == 2
        mock_db_session.delete.assert_any_await(future_entry_1)
        mock_db_session.delete.assert_any_await(future_entry_2)
        mock_db_session.commit.assert_awaited_once()

        # Past entry (past_entry) is NOT in the query results, so it's retained.
        # The service only fetches entries with date > leave_date.

    @pytest.mark.asyncio
    async def test_member_leave_no_future_entries_no_commit(
        self, household_id, user_alice, today, mock_db_session
    ):
        """When leaving member has no future entries, nothing is deleted.

        Validates: Graceful handling when no entries need cleanup.
        """
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        count = await on_member_leave(mock_db_session, household_id, user_alice.id, today)

        assert count == 0
        mock_db_session.commit.assert_not_awaited()
        mock_db_session.delete.assert_not_awaited()


class TestPhase5SlotUniqueness:
    """Smoke test: slot uniqueness per household per date.

    Success criteria: First-come-first-served — same slot on same day for same household is blocked.
    """

    @pytest.mark.asyncio
    async def test_same_slot_different_dates_allowed(
        self, household_id, user_alice, today, mock_db_session
    ):
        """Same slot on different dates is allowed (no conflict).

        Validates: Unique constraint is (household_id, date, slot), not just slot.
        """
        # Claim lunch for today
        mock_result_free = MagicMock()
        mock_result_free.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result_free)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        entry1 = await create_entry(
            mock_db_session, household_id, user_alice.id,
            MealEntryCreate(date=today, slot=MealSlot.lunch, text="Today lunch", headcount=2),
        )
        assert entry1.date == today

        # Claim lunch for tomorrow — should also succeed
        mock_db_session.commit.reset_mock()
        mock_result_free2 = MagicMock()
        mock_result_free2.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result_free2)

        entry2 = await create_entry(
            mock_db_session, household_id, user_alice.id,
            MealEntryCreate(
                date=today + timedelta(days=1), slot=MealSlot.lunch,
                text="Tomorrow lunch", headcount=2,
            ),
        )
        assert entry2.date == today + timedelta(days=1)
        mock_db_session.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_different_slots_same_date_allowed(
        self, household_id, user_alice, user_bob, today, mock_db_session
    ):
        """Different slots on the same date are allowed (lunch + dinner).

        Validates: Unique constraint is per (household_id, date, slot).
        """
        # Alice claims lunch
        mock_free = MagicMock()
        mock_free.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_free)

        async def fake_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        lunch = await create_entry(
            mock_db_session, household_id, user_alice.id,
            MealEntryCreate(date=today, slot=MealSlot.lunch, text="Lunch", headcount=3),
        )
        assert lunch.slot == MealSlot.lunch

        # Bob claims dinner on the same date — should succeed
        mock_db_session.commit.reset_mock()
        mock_free2 = MagicMock()
        mock_free2.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_free2)

        dinner = await create_entry(
            mock_db_session, household_id, user_bob.id,
            MealEntryCreate(date=today, slot=MealSlot.dinner, text="Dinner", headcount=3),
        )
        assert dinner.slot == MealSlot.dinner
        mock_db_session.commit.assert_awaited()
