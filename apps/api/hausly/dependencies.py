import uuid
from typing import Callable

from fastapi import Depends, HTTPException, Path
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.household.service import (_get_membership,
                                              get_household_settings)
from hausly.modules.users.models import User
from hausly.telemetry import enrich_span
from sqlalchemy.ext.asyncio import AsyncSession


async def get_household_membership(
    household_id: uuid.UUID = Path(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdMembership:
    """Validate user belongs to the household in the path param."""
    membership = await _get_membership(db, household_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")
    enrich_span(household_id=household_id, member_role=membership.role.value)
    return membership


def require_module(module_name: str) -> Callable:
    """Dependency factory: checks module is enabled for the household."""

    async def _check_module(
        household_id: uuid.UUID = Path(),
        db: AsyncSession = Depends(get_db),
        _membership: HouseholdMembership = Depends(get_household_membership),
    ) -> None:
        settings = await get_household_settings(db, household_id)
        if module_name not in settings.enabled_modules:
            raise HTTPException(
                status_code=403,
                detail=f"Module '{module_name}' is not enabled for this household",
            )

    return _check_module


__all__ = ["get_current_user", "get_db", "get_household_membership", "require_module"]
