import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from hausly.config import settings
from hausly.database import get_db
from hausly.modules.users.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

_firebase_app: firebase_admin.App | None = None
_bearer_scheme = HTTPBearer()


def _get_firebase_app() -> firebase_admin.App:
    """Initialize Firebase Admin SDK lazily."""
    global _firebase_app
    if _firebase_app is None:
        try:
            cred = credentials.Certificate(settings.firebase_service_account_path)
            _firebase_app = firebase_admin.initialize_app(cred)
        except (FileNotFoundError, ValueError):
            # Fall back to application default credentials (e.g. in CI/testing)
            _firebase_app = firebase_admin.initialize_app()
    return _firebase_app


def verify_firebase_token(token: str) -> dict:
    """Verify a Firebase ID token and return decoded claims."""
    _get_firebase_app()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except (firebase_auth.InvalidIdTokenError, firebase_auth.ExpiredIdTokenError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    return decoded


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: verify token, look up or create User row."""
    decoded = verify_firebase_token(credentials.credentials)
    firebase_uid: str = decoded["uid"]

    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()

    if user is None:
        # Auto-create user on first auth verification
        user = User(
            firebase_uid=firebase_uid,
            display_name=decoded.get("name", ""),
            email=decoded.get("email", ""),
            avatar_url=decoded.get("picture"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
