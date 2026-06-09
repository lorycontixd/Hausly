"""SignalR negotiate endpoint — returns connection info for the client."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.household.service import get_active_membership
from hausly.modules.users.models import User
from hausly.realtime.signalr import signalr_service
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/hubs/household", tags=["realtime"])


class NegotiateResponse(BaseModel):
    url: str
    accessToken: str


@router.post("/negotiate", response_model=NegotiateResponse)
async def negotiate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NegotiateResponse:
    """Return SignalR connection info for the authenticated user's household."""
    if not signalr_service.enabled:
        raise HTTPException(
            status_code=503,
            detail="Real-time service is not configured",
        )

    membership = await get_active_membership(db, user.id)
    if membership is None:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to any household",
        )

    token_data = signalr_service.generate_client_token(
        user_id=str(user.id),
        household_id=str(membership.household_id),
    )
    return NegotiateResponse(**token_data)
