import uuid

from fastapi import APIRouter, Depends, HTTPException
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.modules.household import service
from hausly.modules.household.models import HouseholdMembership, MemberRole
from hausly.modules.household.schemas import (HouseholdCreate,
                                              HouseholdResponse,
                                              HouseholdSettingsResponse,
                                              HouseholdSettingsUpdate,
                                              HouseholdUpdate,
                                              InvitePreviewResponse,
                                              JoinRequest, LeaveResponse,
                                              MemberResponse,
                                              RoleChangeRequest)
from hausly.modules.household.service import HouseholdError
from hausly.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/households", tags=["households"])
invite_router = APIRouter(prefix="/api/v1/invites", tags=["households"])


async def _get_household_membership(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdMembership:
    membership = await service._get_membership(db, household_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")
    return membership


async def _require_admin(
    membership: HouseholdMembership = Depends(_get_household_membership),
) -> HouseholdMembership:
    if membership.role != MemberRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return membership


def _handle_service_error(e: HouseholdError) -> None:
    raise HTTPException(status_code=e.status_code, detail=e.detail)


async def _build_household_response(
    db: AsyncSession, household_id: uuid.UUID
) -> HouseholdResponse:
    household = await service.get_household(db, household_id)
    settings = await service.get_household_settings(db, household_id)
    members_data = await service.get_active_members(db, household_id)

    return HouseholdResponse(
        id=household.id,
        name=household.name,
        type=household.type,
        invite_code=household.invite_code,
        subscription_tier=household.subscription_tier,
        created_at=household.created_at,
        settings=HouseholdSettingsResponse(
            default_currency=settings.default_currency,
            enabled_modules=settings.enabled_modules,
            notification_level=settings.notification_level,
        ),
        members=[
            MemberResponse(
                user_id=m.user_id,
                display_name=u.display_name,
                email=u.email,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m, u in members_data
        ],
    )


@router.post("", response_model=HouseholdResponse, status_code=201)
async def create_household(
    data: HouseholdCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdResponse:
    try:
        household = await service.create_household(db, user, data)
    except HouseholdError as e:
        _handle_service_error(e)
    return await _build_household_response(db, household.id)


@router.get("/{household_id}", response_model=HouseholdResponse)
async def get_household(
    household_id: uuid.UUID,
    _membership: HouseholdMembership = Depends(_get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> HouseholdResponse:
    try:
        return await _build_household_response(db, household_id)
    except HouseholdError as e:
        _handle_service_error(e)


@router.patch("/{household_id}", response_model=HouseholdResponse)
async def update_household(
    household_id: uuid.UUID,
    data: HouseholdUpdate,
    _admin: HouseholdMembership = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> HouseholdResponse:
    try:
        await service.update_household(db, household_id, data)
    except HouseholdError as e:
        _handle_service_error(e)
    return await _build_household_response(db, household_id)


@router.patch("/{household_id}/settings", response_model=HouseholdSettingsResponse)
async def update_settings(
    household_id: uuid.UUID,
    data: HouseholdSettingsUpdate,
    _admin: HouseholdMembership = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> HouseholdSettingsResponse:
    try:
        settings = await service.update_settings(db, household_id, data)
    except HouseholdError as e:
        _handle_service_error(e)

    from hausly.realtime.signalr import signalr_service
    await signalr_service.household_settings_updated(household_id, {
        "enabled_modules": settings.enabled_modules,
        "default_currency": settings.default_currency,
        "notification_level": settings.notification_level,
    })

    return HouseholdSettingsResponse(
        default_currency=settings.default_currency,
        enabled_modules=settings.enabled_modules,
        notification_level=settings.notification_level,
    )


@invite_router.get("/{code}/preview", response_model=InvitePreviewResponse)
async def preview_invite(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> InvitePreviewResponse:
    try:
        data = await service.preview_invite(db, code)
    except HouseholdError as e:
        _handle_service_error(e)
    return InvitePreviewResponse(**data)


@router.post("/join", status_code=201)
async def join_household(
    data: JoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        membership = await service.join_household(db, user, data.invite_code)
    except HouseholdError as e:
        _handle_service_error(e)
    return {"household_id": str(membership.household_id), "role": membership.role}


@router.post("/{household_id}/leave", response_model=LeaveResponse)
async def leave_household(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeaveResponse:
    try:
        return await service.leave_household(db, user, household_id)
    except HouseholdError as e:
        _handle_service_error(e)


@router.get("/{household_id}/members", response_model=list[MemberResponse])
async def list_members(
    household_id: uuid.UUID,
    _membership: HouseholdMembership = Depends(_get_household_membership),
    db: AsyncSession = Depends(get_db),
) -> list[MemberResponse]:
    members_data = await service.get_active_members(db, household_id)
    return [
        MemberResponse(
            user_id=m.user_id,
            display_name=u.display_name,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m, u in members_data
    ]


@router.delete("/{household_id}/members/{user_id}", status_code=204)
async def remove_member(
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    _admin: HouseholdMembership = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await service.remove_member(db, household_id, user_id)
    except HouseholdError as e:
        _handle_service_error(e)


@router.patch("/{household_id}/members/{user_id}/role")
async def change_role(
    household_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleChangeRequest,
    _admin: HouseholdMembership = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        membership = await service.change_role(db, household_id, user_id, data.role)
    except HouseholdError as e:
        _handle_service_error(e)
    return {"user_id": str(membership.user_id), "role": membership.role}


@router.post("/{household_id}/invite-code/regenerate")
async def regenerate_invite_code(
    household_id: uuid.UUID,
    _admin: HouseholdMembership = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        new_code = await service.regenerate_invite_code(db, household_id)
    except HouseholdError as e:
        _handle_service_error(e)
    return {"invite_code": new_code}
