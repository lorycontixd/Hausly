"""Tests for the household module service layer."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.modules.household.models import (Household, HouseholdMembership,
                                             HouseholdSettings, HouseholdType,
                                             MemberRole, NotificationLevel,
                                             SubscriptionTier)
from hausly.modules.household.schemas import (HouseholdCreate,
                                              HouseholdSettingsUpdate,
                                              HouseholdUpdate)
from hausly.modules.household.service import (HouseholdError, change_role,
                                              create_household, join_household,
                                              leave_household, preview_invite,
                                              regenerate_invite_code,
                                              remove_member, update_household,
                                              update_settings)
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


class TestCreateHousehold:
    @pytest.mark.asyncio
    async def test_create_household_success(self, user_a, mock_db_session):
        """Creating a household should succeed when user has no active membership."""
        data = HouseholdCreate(name="Test Home", type=HouseholdType.couple)

        # Mock: no active membership
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        mock_db_session.flush = AsyncMock()

        # Mock refresh to set an id on the household
        async def fake_refresh(obj):
            if isinstance(obj, Household):
                obj.id = uuid.uuid4()
                obj.settings = HouseholdSettings(household_id=obj.id)

        mock_db_session.refresh = AsyncMock(side_effect=fake_refresh)

        result = await create_household(mock_db_session, user_a, data)
        assert result.name == "Test Home"
        assert result.type == HouseholdType.couple
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_household_already_in_household(self, user_a, mock_db_session):
        """Creating a household should fail if user already has active membership."""
        data = HouseholdCreate(name="Test Home", type=HouseholdType.couple)

        existing_membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            user_id=user_a.id,
            role=MemberRole.admin,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_membership
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HouseholdError) as exc_info:
            await create_household(mock_db_session, user_a, data)
        assert exc_info.value.code == "ALREADY_IN_HOUSEHOLD"
        assert exc_info.value.status_code == 409


class TestJoinHousehold:
    @pytest.mark.asyncio
    async def test_join_household_already_member(self, user_b, mock_db_session):
        """Joining should fail if user already has an active membership."""
        existing_membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=uuid.uuid4(),
            user_id=user_b.id,
            role=MemberRole.member,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_membership
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HouseholdError) as exc_info:
            await join_household(mock_db_session, user_b, "some-code")
        assert exc_info.value.code == "ALREADY_IN_HOUSEHOLD"
        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_join_household_invalid_code(self, user_b, mock_db_session):
        """Joining with invalid code should return NOT_FOUND."""
        # First call: no active membership; Second call: no household found
        mock_result_none = MagicMock()
        mock_result_none.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result_none)

        with pytest.raises(HouseholdError) as exc_info:
            await join_household(mock_db_session, user_b, "bad-code")
        assert exc_info.value.code == "NOT_FOUND"


class TestUpdateSettings:
    @pytest.mark.asyncio
    async def test_update_settings_invalid_module(self, mock_db_session, household_id):
        """Setting an invalid module name should fail."""
        settings = HouseholdSettings(
            household_id=household_id,
            enabled_modules=["grocery", "expense"],
        )
        household = Household(
            id=household_id,
            name="Test",
            type=HouseholdType.couple,
            subscription_tier=SubscriptionTier.free,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = settings
            else:
                result.scalar_one_or_none.return_value = household
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = HouseholdSettingsUpdate(enabled_modules=["grocery", "invalid_module"])
        with pytest.raises(HouseholdError) as exc_info:
            await update_settings(mock_db_session, household_id, data)
        assert exc_info.value.code == "INVALID_MODULES"

    @pytest.mark.asyncio
    async def test_update_settings_tier_limit(self, mock_db_session, household_id):
        """Free tier should not be able to enable paid-only modules."""
        settings = HouseholdSettings(
            household_id=household_id,
            enabled_modules=["grocery"],
        )
        household = Household(
            id=household_id,
            name="Test",
            type=HouseholdType.couple,
            subscription_tier=SubscriptionTier.free,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = settings
            else:
                result.scalar_one_or_none.return_value = household
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        data = HouseholdSettingsUpdate(enabled_modules=["grocery", "pinboard"])
        with pytest.raises(HouseholdError) as exc_info:
            await update_settings(mock_db_session, household_id, data)
        assert exc_info.value.code == "TIER_LIMIT"
        assert exc_info.value.status_code == 403


class TestLeaveHousehold:
    @pytest.mark.asyncio
    async def test_leave_last_admin_with_others(self, user_a, mock_db_session, household_id):
        """Last admin cannot leave if other members exist."""
        membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=household_id,
            user_id=user_a.id,
            role=MemberRole.admin,
        )
        other_user = User(
            id=uuid.uuid4(),
            firebase_uid="uid-other",
            display_name="Other",
            email="other@example.com",
        )
        other_membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=household_id,
            user_id=other_user.id,
            role=MemberRole.member,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # _get_membership
                result.scalar_one_or_none.return_value = membership
            elif call_count == 2:
                # admin count query
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = [membership]
                result.scalars.return_value = scalars_mock
            elif call_count == 3:
                # get_active_members (all members including current)
                result.all.return_value = [
                    (membership, user_a),
                    (other_membership, other_user),
                ]
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(HouseholdError) as exc_info:
            await leave_household(mock_db_session, user_a, household_id)
        assert exc_info.value.code == "LAST_ADMIN"


class TestChangeRole:
    @pytest.mark.asyncio
    async def test_change_role_demote_last_admin(self, mock_db_session, household_id):
        """Cannot demote the last admin."""
        user_id = uuid.uuid4()
        membership = HouseholdMembership(
            id=uuid.uuid4(),
            household_id=household_id,
            user_id=user_id,
            role=MemberRole.admin,
        )

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                # _get_membership
                result.scalar_one_or_none.return_value = membership
            elif call_count == 2:
                # admin count
                scalars_mock = MagicMock()
                scalars_mock.all.return_value = [membership]
                result.scalars.return_value = scalars_mock
            return result

        mock_db_session.execute = AsyncMock(side_effect=mock_execute)

        with pytest.raises(HouseholdError) as exc_info:
            await change_role(mock_db_session, household_id, user_id, MemberRole.member)
        assert exc_info.value.code == "LAST_ADMIN"


class TestPreviewInvite:
    @pytest.mark.asyncio
    async def test_preview_invalid_code(self, mock_db_session):
        """Invalid code should return NOT_FOUND."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HouseholdError) as exc_info:
            await preview_invite(mock_db_session, "bad-code")
        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.status_code == 404
