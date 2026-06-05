"""Smoke test: Phase 1 — Database & Auth end-to-end.

Validates Phase 1 success criteria from implementation-plan-v1.md:
  - POST /auth/verify with a valid Firebase token returns user profile
  - Invalid tokens return 401
  - Alembic migration structure is correct
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hausly.auth.router import router as auth_router
from hausly.database import get_db
from hausly.modules.users.models import User


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(auth_router)
    return test_app


class TestPhase1EndToEnd:
    """End-to-end smoke test for Phase 1: Database & Auth."""

    @pytest.mark.asyncio
    async def test_auth_verify_end_to_end_existing_user(self, app):
        """Full auth flow: token verified → existing user looked up → profile returned.

        Success criteria: POST /auth/verify with valid token returns user profile.
        """
        existing_user = User(
            id=uuid.uuid4(),
            firebase_uid="uid-existing-user",
            display_name="Jane Doe",
            email="jane@example.com",
            avatar_url="https://example.com/avatar.jpg",
        )
        firebase_claims = {
            "uid": "uid-existing-user",
            "name": "Jane Doe",
            "email": "jane@example.com",
            "picture": "https://example.com/avatar.jpg",
        }

        async def override_get_db():
            session = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = existing_user
            session.execute.return_value = result
            yield session

        app.dependency_overrides[get_db] = override_get_db

        with patch("hausly.auth.firebase.verify_firebase_token", return_value=firebase_claims):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer a-valid-firebase-jwt"},
                )

        # Success criteria: returns user profile
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(existing_user.id)
        assert data["display_name"] == "Jane Doe"
        assert data["email"] == "jane@example.com"
        assert data["avatar_url"] == "https://example.com/avatar.jpg"
        # Households empty (Phase 2 adds membership lookup)
        assert data["households"] == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_auth_verify_end_to_end_new_user_creation(self, app):
        """Full auth flow: token verified → user not found → auto-created → profile returned.

        Success criteria: POST /auth/verify creates user row on first call.
        """
        firebase_claims = {
            "uid": "uid-brand-new-user",
            "name": "New User",
            "email": "new@example.com",
            "picture": None,
        }

        db_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # User doesn't exist yet
        db_session.execute.return_value = result
        db_session.commit = AsyncMock()
        db_session.refresh = AsyncMock()

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("hausly.auth.firebase.verify_firebase_token", return_value=firebase_claims):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer a-valid-firebase-jwt"},
                )

        # Success criteria: user is auto-created and profile returned
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "New User"
        assert data["email"] == "new@example.com"

        # Verify the DB operations: add was called with a User instance
        db_session.add.assert_called_once()
        created_user = db_session.add.call_args[0][0]
        assert isinstance(created_user, User)
        assert created_user.firebase_uid == "uid-brand-new-user"
        assert created_user.display_name == "New User"
        assert created_user.email == "new@example.com"

        # Verify commit was called (persist the new user)
        db_session.commit.assert_awaited_once()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_auth_verify_end_to_end_invalid_token_rejected(self, app):
        """Invalid Firebase token is rejected with 401.

        Success criteria: Invalid tokens return 401.
        """
        from fastapi import HTTPException

        with patch(
            "hausly.auth.firebase.verify_firebase_token",
            side_effect=HTTPException(status_code=401, detail="Invalid or expired token"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer expired-or-tampered-token"},
                )

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_auth_verify_end_to_end_missing_auth_header(self, app):
        """Missing Authorization header is rejected.

        Success criteria: Invalid tokens return 401 (no token = invalid).
        """
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/verify")

        assert response.status_code == 401

    def test_migration_001_structure_correct(self):
        """Alembic migration creates users table with correct schema.

        Success criteria: Alembic migration runs cleanly against a fresh DB.
        (We validate structure here; actual DB run requires a live PG instance.)
        """
        import importlib

        migration = importlib.import_module("migrations.versions.001_initial")

        assert migration.revision == "001_initial"
        assert migration.down_revision is None

        # Verify upgrade/downgrade are callable (structural soundness)
        assert callable(migration.upgrade)
        assert callable(migration.downgrade)

    def test_user_model_has_required_fields(self):
        """User model has all fields specified in data-models.md.

        Validates: id (UUID), firebase_uid, display_name, email, avatar_url, created_at.
        """
        user = User(
            firebase_uid="test-uid",
            display_name="Test",
            email="test@test.com",
        )

        # UUID auto-generated
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)

        # created_at auto-generated
        assert user.created_at is not None

        # Required fields set
        assert user.firebase_uid == "test-uid"
        assert user.display_name == "Test"
        assert user.email == "test@test.com"

        # Optional field defaults to None
        assert user.avatar_url is None

    def test_user_model_table_name(self):
        """User model maps to 'users' table."""
        assert User.__tablename__ == "users"
