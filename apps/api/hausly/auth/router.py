from fastapi import APIRouter, Depends
from hausly.auth.firebase import get_current_user
from hausly.database import get_db
from hausly.modules.users.models import User
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
    # Phase 2 will add household membership lookup here
    return VerifyResponse(
        user_id=str(current_user.id),
        display_name=current_user.display_name,
        email=current_user.email,
        avatar_url=current_user.avatar_url,
        households=[],
    )
