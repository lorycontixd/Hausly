"""Tests for auth module."""

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


@pytest.fixture
def mock_db():
    """Mock async database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def sample_user():
    return User(
        id=uuid.uuid4(),
        firebase_uid="test-firebase-uid-123",
        display_name="Test User",
        email="test@example.com",
        avatar_url=None,
    )


@pytest.fixture
def mock_firebase_token():
    return {
        "uid": "test-firebase-uid-123",
        "name": "Test User",
        "email": "test@example.com",
        "picture": None,
    }


class TestVerifyEndpoint:
    """Tests for POST /api/v1/auth/verify."""

    @pytest.mark.asyncio
    async def test_verify_returns_user_profile(self, app, sample_user, mock_firebase_token):
        """Valid Firebase token returns user profile."""

        async def override_get_db():
            session = AsyncMock()
            # Simulate user found
            result = MagicMock()
            result.scalar_one_or_none.return_value = sample_user
            session.execute.return_value = result
            yield session

        app.dependency_overrides[get_db] = override_get_db

        with patch("hausly.auth.firebase.verify_firebase_token", return_value=mock_firebase_token):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer valid-token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Test User"
        assert data["email"] == "test@example.com"
        assert data["households"] == []

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_creates_user_on_first_call(self, app, mock_firebase_token):
        """First auth verification creates a new user row."""

        async def override_get_db():
            session = AsyncMock()
            # Simulate user NOT found (first call)
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            session.execute.return_value = result
            # After add+commit+refresh, user exists
            session.refresh = AsyncMock()
            yield session

        app.dependency_overrides[get_db] = override_get_db

        with patch("hausly.auth.firebase.verify_firebase_token", return_value=mock_firebase_token):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer valid-token"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Test User"
        assert data["email"] == "test@example.com"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_verify_returns_401_without_token(self, app):
        """Missing Authorization header returns 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/verify")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_returns_401_with_invalid_token(self, app):
        """Invalid Firebase token returns 401."""
        with patch(
            "hausly.auth.firebase.verify_firebase_token",
            side_effect=__import__("fastapi").HTTPException(
                status_code=401, detail="Invalid or expired token"
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/auth/verify",
                    headers={"Authorization": "Bearer invalid-token"},
                )

        assert response.status_code == 401
