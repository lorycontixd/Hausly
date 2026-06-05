from fastapi import APIRouter, Depends
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.modules.household.models import HouseholdMembership
from hausly.modules.users.models import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class HouseholdMembershipResponse(BaseModel):
    id: str
    name: str
    role: str


class VerifyResponse(BaseModel):
    user_id: str
    display_name: str
    email: str
    avatar_url: str | None = None
    households: list[HouseholdMembershipResponse] = []


@router.post("/verify", response_model=VerifyResponse)
async def verify_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    """Verify Firebase token and return Hausly user profile + active households."""
    from hausly.modules.household.models import Household

    result = await db.execute(
        select(HouseholdMembership, Household)
        .join(Household, HouseholdMembership.household_id == Household.id)
        .where(
            HouseholdMembership.user_id == current_user.id,
            HouseholdMembership.left_at.is_(None),  # type: ignore[union-attr]
        )
    )
    memberships = result.all()

    return VerifyResponse(
        user_id=str(current_user.id),
        display_name=current_user.display_name,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
        households=[
            HouseholdMembershipResponse(
                id=str(m.household_id),
                name=h.name,
                role=m.role,
            )
            for m, h in memberships
        ],
    )

