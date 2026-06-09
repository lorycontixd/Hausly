import secrets
import uuid
from datetime import UTC, datetime

from hausly.modules.chores.models import AssignmentStatus, ChoreAssignment
from hausly.modules.household.models import (Household, HouseholdMembership,
                                             HouseholdSettings, MemberRole,
                                             SubscriptionTier)
from hausly.modules.household.schemas import (HouseholdCreate,
                                              HouseholdSettingsUpdate,
                                              HouseholdUpdate, LeaveResponse)
from hausly.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select


class HouseholdError(Exception):
    def __init__(self, code: str, detail: str, status_code: int = 400):
        self.code = code
        self.detail = detail
        self.status_code = status_code


VALID_MODULES = {"grocery", "expense", "meal", "chores", "pinboard"}
FREE_TIER_MODULES = {"grocery", "expense", "meal", "chores"}


async def create_household(
    db: AsyncSession, user: User, data: HouseholdCreate
) -> Household:
    # Check single-membership constraint
    active = await _get_active_membership(db, user.id)
    if active is not None:
        raise HouseholdError(
            code="ALREADY_IN_HOUSEHOLD",
            detail="User already has an active household membership",
            status_code=409,
        )

    household = Household(
        name=data.name,
        type=data.type,
        subscription_owner_id=user.id,
    )
    db.add(household)
    await db.flush()

    settings = HouseholdSettings(household_id=household.id)
    db.add(settings)

    membership = HouseholdMembership(
        household_id=household.id,
        user_id=user.id,
        role=MemberRole.admin,
    )
    db.add(membership)

    await db.commit()
    await db.refresh(household)
    return household


async def get_household(db: AsyncSession, household_id: uuid.UUID) -> Household:
    result = await db.execute(
        select(Household).where(Household.id == household_id)
    )
    household = result.scalar_one_or_none()
    if household is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Household not found", status_code=404
        )
    return household


async def get_household_settings(
    db: AsyncSession, household_id: uuid.UUID
) -> HouseholdSettings:
    result = await db.execute(
        select(HouseholdSettings).where(
            HouseholdSettings.household_id == household_id
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Household settings not found", status_code=404
        )
    return settings


async def get_active_members(
    db: AsyncSession, household_id: uuid.UUID
) -> list[tuple[HouseholdMembership, User]]:
    result = await db.execute(
        select(HouseholdMembership, User)
        .join(User, HouseholdMembership.user_id == User.id)
        .where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
        )
    )
    return list(result.all())


async def update_household(
    db: AsyncSession, household_id: uuid.UUID, data: HouseholdUpdate
) -> Household:
    household = await get_household(db, household_id)
    if data.name is not None:
        household.name = data.name
    if data.type is not None:
        household.type = data.type
    db.add(household)
    await db.commit()
    await db.refresh(household)
    return household


async def update_settings(
    db: AsyncSession, household_id: uuid.UUID, data: HouseholdSettingsUpdate
) -> HouseholdSettings:
    settings = await get_household_settings(db, household_id)
    household = await get_household(db, household_id)

    if data.enabled_modules is not None:
        # Validate modules
        invalid = set(data.enabled_modules) - VALID_MODULES
        if invalid:
            raise HouseholdError(
                code="INVALID_MODULES",
                detail=f"Invalid modules: {invalid}",
                status_code=400,
            )
        # Enforce tier limits
        if household.subscription_tier == SubscriptionTier.free:
            paid_only = set(data.enabled_modules) - FREE_TIER_MODULES
            if paid_only:
                raise HouseholdError(
                    code="TIER_LIMIT",
                    detail=f"Modules require paid tier: {paid_only}",
                    status_code=403,
                )
        settings.enabled_modules = data.enabled_modules

    if data.default_currency is not None:
        settings.default_currency = data.default_currency
    if data.notification_level is not None:
        settings.notification_level = data.notification_level

    settings.updated_at = datetime.now(UTC)
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


async def preview_invite(db: AsyncSession, code: str) -> dict:
    result = await db.execute(
        select(Household).where(Household.invite_code == code)
    )
    household = result.scalar_one_or_none()
    if household is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Invalid invite code", status_code=404
        )

    members = await get_active_members(db, household.id)
    return {
        "household_name": household.name,
        "member_count": len(members),
        "type": household.type,
    }


async def join_household(
    db: AsyncSession, user: User, invite_code: str
) -> HouseholdMembership:
    # Check single-membership constraint
    active = await _get_active_membership(db, user.id)
    if active is not None:
        raise HouseholdError(
            code="ALREADY_IN_HOUSEHOLD",
            detail="User already has an active household membership",
            status_code=409,
        )

    result = await db.execute(
        select(Household).where(Household.invite_code == invite_code)
    )
    household = result.scalar_one_or_none()
    if household is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Invalid invite code", status_code=404
        )

    membership = HouseholdMembership(
        household_id=household.id,
        user_id=user.id,
        role=MemberRole.member,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def leave_household(
    db: AsyncSession, user: User, household_id: uuid.UUID
) -> LeaveResponse:
    membership = await _get_membership(db, household_id, user.id)
    if membership is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Membership not found", status_code=404
        )

    # Check if user is the last admin
    if membership.role == MemberRole.admin:
        admins = await db.execute(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == MemberRole.admin,
                HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
            )
        )
        admin_list = admins.scalars().all()
        if len(admin_list) == 1:
            # Check if there are other members
            all_members = await get_active_members(db, household_id)
            if len(all_members) > 1:
                raise HouseholdError(
                    code="LAST_ADMIN",
                    detail="Cannot leave: you are the last admin. Transfer admin role first.",
                    status_code=400,
                )

    # Query pending chore assignments for the leaving user
    chore_stmt = select(ChoreAssignment).where(
        ChoreAssignment.household_id == household_id,
        ChoreAssignment.assigned_to_user_id == user.id,
        ChoreAssignment.status == AssignmentStatus.pending,
    )
    chore_result = await db.execute(chore_stmt)
    pending_chore_rows = list(chore_result.scalars().all())
    pending_chores = [
        {"assignment_id": str(a.id), "chore_id": str(a.chore_id), "due_date": str(a.due_date)}
        for a in pending_chore_rows
    ]

    # TODO: Query unsettled expenses in expense module integration
    unsettled_expenses: list[dict] = []

    membership.left_at = datetime.now(UTC)
    db.add(membership)

    # Archive household if no active members remain
    remaining = await get_active_members(db, household_id)
    # Exclude the leaving user (their left_at is set but not committed yet)
    remaining_active = [
        (m, u) for m, u in remaining if m.user_id != user.id
    ]
    if not remaining_active:
        household = await get_household(db, household_id)
        household.archived_at = datetime.now(UTC)
        db.add(household)

    # Trigger module-level cleanup for the leaving member
    from hausly.modules.chores.service import \
        on_member_leave as chores_on_member_leave
    from hausly.modules.meal.service import \
        on_member_leave as meal_on_member_leave

    await chores_on_member_leave(db, household_id, user.id)
    await meal_on_member_leave(db, household_id, user.id, datetime.now(UTC).date())

    await db.commit()
    return LeaveResponse(
        unsettled_expenses=unsettled_expenses,
        pending_chores=pending_chores,
    )


async def remove_member(
    db: AsyncSession, household_id: uuid.UUID, target_user_id: uuid.UUID
) -> None:
    membership = await _get_membership(db, household_id, target_user_id)
    if membership is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Member not found", status_code=404
        )
    membership.left_at = datetime.now(UTC)
    db.add(membership)
    await db.commit()


async def change_role(
    db: AsyncSession,
    household_id: uuid.UUID,
    target_user_id: uuid.UUID,
    new_role: MemberRole,
) -> HouseholdMembership:
    membership = await _get_membership(db, household_id, target_user_id)
    if membership is None:
        raise HouseholdError(
            code="NOT_FOUND", detail="Member not found", status_code=404
        )

    # Prevent removing last admin
    if membership.role == MemberRole.admin and new_role == MemberRole.member:
        admins = await db.execute(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.role == MemberRole.admin,
                HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
            )
        )
        if len(admins.scalars().all()) == 1:
            raise HouseholdError(
                code="LAST_ADMIN",
                detail="Cannot demote: household must have at least one admin",
                status_code=400,
            )

    membership.role = new_role
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


async def regenerate_invite_code(
    db: AsyncSession, household_id: uuid.UUID
) -> str:
    household = await get_household(db, household_id)
    household.invite_code = secrets.token_urlsafe(6)
    db.add(household)
    await db.commit()
    await db.refresh(household)
    return household.invite_code


# --- Private helpers ---


async def _get_active_membership(
    db: AsyncSession, user_id: uuid.UUID
) -> HouseholdMembership | None:
    result = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.user_id == user_id,
            HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
        )
    )
    return result.scalar_one_or_none()


async def get_active_membership(
    db: AsyncSession, user_id: uuid.UUID
) -> HouseholdMembership | None:
    """Public wrapper — used by negotiate endpoint."""
    return await _get_active_membership(db, user_id)


async def _get_membership(
    db: AsyncSession, household_id: uuid.UUID, user_id: uuid.UUID
) -> HouseholdMembership | None:
    result = await db.execute(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user_id,
            HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
        )
    )
    return result.scalar_one_or_none()
