"""Test fixtures and configuration."""

import uuid
from unittest.mock import AsyncMock

import pytest
from hausly.modules.users.models import User


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_user():
    """A sample authenticated user for tests."""
    return User(
        id=uuid.uuid4(),
        firebase_uid="test-uid-123",
        display_name="Test User",
        email="test@example.com",
        avatar_url=None,
    )


@pytest.fixture
def mock_db_session():
    """Mock async database session with basic operations."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session
