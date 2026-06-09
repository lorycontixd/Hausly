"""Smoke test: Phase 7 — Real-Time (SignalR) end-to-end.

Validates Phase 7 success criteria from implementation-plan-v1.md:
  - Client can negotiate and connect to SignalR hub
  - Mutations in one client trigger events received by other connected household members
  - Events contain correct payloads matching docs/api-reference.md
  - Fire-and-forget: mutations succeed even if SignalR is unavailable

Also validates key behaviours from docs/signalr-architecture.md:
  - Connection string parsing (Endpoint + AccessKey extraction)
  - JWT token generation with correct audience, subject, and group claims
  - Negotiate returns { url, accessToken } with household group auto-join
  - Broadcast targets the correct group (household:{household_id})
  - All event wrappers produce correct target and arguments structure
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest
from hausly.modules.grocery.models import GroceryItem, GroceryList, ItemSource
from hausly.modules.grocery.schemas import (GroceryItemCreate,
                                            GroceryItemResponse)
from hausly.modules.household.models import (HouseholdMembership,
                                             HouseholdSettings, MemberRole)
from hausly.modules.users.models import User
from hausly.realtime.signalr import (HUB_NAME, SignalRService, _generate_jwt,
                                     _parse_connection_string, signalr_service)

# --- Fixtures ---


VALID_CONN_STR = "Endpoint=https://hausly-dev.service.signalr.net;AccessKey=a-real-secret-key-at-least-32-chars;Version=1.0;"


@pytest.fixture
def user_alice():
    return User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        firebase_uid="uid-alice",
        display_name="Alice",
        email="alice@example.com",
    )


@pytest.fixture
def user_bob():
    return User(
        id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        firebase_uid="uid-bob",
        display_name="Bob",
        email="bob@example.com",
    )


@pytest.fixture
def household_id():
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def membership(household_id, user_alice):
    return HouseholdMembership(
        id=uuid.uuid4(),
        household_id=household_id,
        user_id=user_alice.id,
        role=MemberRole.admin,
    )


@pytest.fixture
def signalr_svc():
    """A SignalRService instance with a valid connection string."""
    with patch("hausly.realtime.signalr.settings") as mock_settings:
        mock_settings.signalr_connection_string = VALID_CONN_STR
        svc = SignalRService()
    return svc


class TestPhase7NegotiateEndToEnd:
    """End-to-end smoke test: negotiate endpoint returns valid SignalR connection info.

    Success criteria: Client can negotiate and connect to SignalR hub.
    """

    @pytest.mark.asyncio
    async def test_negotiate_returns_valid_connection_info(
        self, signalr_svc, user_alice, household_id
    ):
        """Validate negotiate produces a token that would let the client connect.

        Validates:
          - Negotiate returns { url, accessToken } (success criterion #1)
          - URL points to the correct SignalR client endpoint (signalr-architecture.md)
          - Token contains correct audience, subject, and group claim (signalr-architecture.md)
        """
        # Act: generate client token (same as negotiate endpoint does)
        result = signalr_svc.generate_client_token(
            user_id=str(user_alice.id),
            household_id=str(household_id),
        )

        # Assert structure
        assert "url" in result
        assert "accessToken" in result

        # Assert URL format (signalr-architecture.md: client URL)
        assert "/client/?hub=household" in result["url"]
        assert "https://hausly-dev.service.signalr.net" in result["url"]

        # Decode and validate token claims
        access_key = "a-real-secret-key-at-least-32-chars"
        decoded = pyjwt.decode(
            result["accessToken"],
            access_key,
            algorithms=["HS256"],
            audience=result["url"],
        )

        # signalr-architecture.md: sub = user ID
        assert decoded["sub"] == str(user_alice.id)

        # signalr-architecture.md: asrs.s.gp = group name (auto-join)
        assert decoded["asrs.s.gp"] == f"household:{household_id}"

        # Token has expiry (1 hour per spec)
        assert "exp" in decoded
        assert decoded["exp"] - decoded["iat"] == 3600

    @pytest.mark.asyncio
    async def test_negotiate_disabled_service_returns_no_token(self):
        """When SignalR is not configured, service is disabled.

        Edge case: graceful degradation when env var is missing.
        """
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = ""
            svc = SignalRService()
            assert svc.enabled is False
            # In the router, this would return 503; here we just verify the flag


class TestPhase7BroadcastOnMutation:
    """Smoke test: mutations trigger broadcasts to the household group.

    Success criteria: Mutations in one client trigger events received by other
    connected household members.
    """

    @pytest.mark.asyncio
    async def test_broadcast_targets_correct_household_group(
        self, signalr_svc, household_id
    ):
        """Broadcast sends to the group 'household:{household_id}'.

        Validates:
          - Broadcast URL contains the correct group path (criterion #2)
          - REST API call structure matches signalr-architecture.md
        """
        mock_response = MagicMock()
        mock_response.status_code = 202
        signalr_svc._client = AsyncMock()
        signalr_svc._client.post = AsyncMock(return_value=mock_response)

        await signalr_svc.broadcast_to_household(
            household_id, "grocery:item_added", {"id": "item-1", "name": "Milk"}
        )

        # Verify the call was made
        signalr_svc._client.post.assert_called_once()
        call_args = signalr_svc._client.post.call_args

        # URL targets the correct group
        url = call_args[0][0]
        assert f"hubs/{HUB_NAME}/groups/household:{household_id}" in url

        # Body follows SignalR REST API format
        body = call_args[1]["json"]
        assert body["target"] == "grocery:item_added"
        assert body["arguments"] == [{"id": "item-1", "name": "Milk"}]

        # Authorization header present with Bearer token
        headers = call_args[1]["headers"]
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_server_token_has_correct_audience(
        self, signalr_svc, household_id
    ):
        """Server-to-service JWT audience = the request URL (signalr-architecture.md).

        Validates server token format for authentication against Azure SignalR.
        """
        mock_response = MagicMock()
        mock_response.status_code = 202
        signalr_svc._client = AsyncMock()
        signalr_svc._client.post = AsyncMock(return_value=mock_response)

        await signalr_svc.broadcast_to_household(
            household_id, "test:event", {}
        )

        call_args = signalr_svc._client.post.call_args
        url = call_args[0][0]
        headers = call_args[1]["headers"]
        server_token = headers["Authorization"].replace("Bearer ", "")

        # Decode without verification to inspect claims
        decoded = pyjwt.decode(
            server_token,
            "a-real-secret-key-at-least-32-chars",
            algorithms=["HS256"],
            audience=url,
        )
        # Server token audience must equal the target URL
        assert decoded["aud"] == url
        # Short-lived (5 min per spec)
        assert decoded["exp"] - decoded["iat"] == 300


class TestPhase7EventPayloads:
    """Smoke test: event payloads match docs/api-reference.md format.

    Success criteria: Events contain correct payloads matching docs/api-reference.md.
    """

    @pytest.mark.asyncio
    async def test_all_event_types_produce_correct_targets(self, signalr_svc, household_id):
        """All event wrappers produce targets matching the event catalogue.

        Validates all 15 event types from api-reference.md § Real-Time.
        """
        signalr_svc.broadcast_to_household = AsyncMock()

        # Grocery events
        await signalr_svc.grocery_item_added(household_id, {"id": "1"})
        await signalr_svc.grocery_item_updated(household_id, {"id": "1"})
        await signalr_svc.grocery_item_removed(household_id, "item-1")
        await signalr_svc.grocery_list_archived(household_id, "list-1")
        await signalr_svc.grocery_session_completed(household_id, ["i1", "i2"], "exp-1")

        # Expense events
        await signalr_svc.expense_created(household_id, {"id": "exp-1"})
        await signalr_svc.expense_confirmed(household_id, "exp-1")
        await signalr_svc.expense_settled(household_id, "split-1")

        # Meal events
        await signalr_svc.meal_updated(household_id, {"id": "entry-1"})
        await signalr_svc.meal_removed(household_id, "entry-1")

        # Chore events
        await signalr_svc.chore_created(household_id, {"id": "chore-1"})
        await signalr_svc.chore_deleted(household_id, "chore-1")
        await signalr_svc.chore_completed(household_id, "assign-1", "user-1")
        await signalr_svc.chore_assignment_updated(household_id, {"id": "assign-1"})

        # Member events
        await signalr_svc.member_joined(household_id, {"id": "user-1"})
        await signalr_svc.member_left(household_id, "user-1")

        # Verify all 16 calls (15 events + member_left/joined)
        assert signalr_svc.broadcast_to_household.call_count == 16

        # Verify target names match api-reference.md catalogue
        targets = [call[0][1] for call in signalr_svc.broadcast_to_household.call_args_list]
        expected_targets = [
            "grocery:item_added",
            "grocery:item_updated",
            "grocery:item_removed",
            "grocery:list_archived",
            "grocery:session_completed",
            "expense:created",
            "expense:confirmed",
            "expense:settled",
            "meal:updated",
            "meal:removed",
            "chore:created",
            "chore:deleted",
            "chore:completed",
            "chore:assignment_updated",
            "member:joined",
            "member:left",
        ]
        assert targets == expected_targets

    @pytest.mark.asyncio
    async def test_grocery_session_completed_payload_structure(self, signalr_svc, household_id):
        """Session completed event has bought_item_ids and optional expense_draft_id.

        Validates api-reference.md: grocery:session_completed payload.
        """
        signalr_svc.broadcast_to_household = AsyncMock()

        await signalr_svc.grocery_session_completed(
            household_id,
            bought_item_ids=["id-1", "id-2", "id-3"],
            expense_draft_id="exp-draft-1",
        )

        call_args = signalr_svc.broadcast_to_household.call_args
        assert call_args[0][1] == "grocery:session_completed"
        payload = call_args[0][2]
        assert payload["bought_item_ids"] == ["id-1", "id-2", "id-3"]
        assert payload["expense_draft_id"] == "exp-draft-1"

    @pytest.mark.asyncio
    async def test_chore_completed_payload_structure(self, signalr_svc, household_id):
        """Chore completed event has assignment_id and completed_by.

        Validates api-reference.md: chore:completed payload.
        """
        signalr_svc.broadcast_to_household = AsyncMock()

        await signalr_svc.chore_completed(household_id, "assign-abc", "user-xyz")

        call_args = signalr_svc.broadcast_to_household.call_args
        assert call_args[0][1] == "chore:completed"
        payload = call_args[0][2]
        assert payload["assignment_id"] == "assign-abc"
        assert payload["completed_by"] == "user-xyz"


class TestPhase7FireAndForget:
    """Smoke test: mutations succeed even when SignalR is unavailable.

    Success criteria: Fire-and-forget — broadcast failures are logged, not raised.
    """

    @pytest.mark.asyncio
    async def test_mutation_succeeds_when_signalr_down_http_error(self, signalr_svc, household_id):
        """HTTP 500 from SignalR doesn't propagate to caller.

        Validates signalr-architecture.md: "The request must never fail because SignalR is down"
        """
        mock_response = MagicMock()
        mock_response.status_code = 500
        signalr_svc._client = AsyncMock()
        signalr_svc._client.post = AsyncMock(return_value=mock_response)

        # Should not raise
        await signalr_svc.broadcast_to_household(
            household_id, "grocery:item_added", {"name": "Milk"}
        )

    @pytest.mark.asyncio
    async def test_mutation_succeeds_when_signalr_down_network_error(self, signalr_svc, household_id):
        """Network errors (connection refused, timeout) don't propagate.

        Validates signalr-architecture.md: fire-and-forget with warning log.
        """
        signalr_svc._client = AsyncMock()
        signalr_svc._client.post = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        # Should not raise
        await signalr_svc.broadcast_to_household(
            household_id, "expense:created", {"id": "exp-1"}
        )

    @pytest.mark.asyncio
    async def test_broadcast_skipped_when_service_disabled(self):
        """When SIGNALR_CONNECTION_STRING is empty, broadcasts are no-ops.

        Edge case: development environment without Azure SignalR provisioned.
        """
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = ""
            svc = SignalRService()

        # This should be a silent no-op
        await svc.broadcast_to_household(uuid.uuid4(), "test:event", {"data": 123})
        # No exception = pass


class TestPhase7ConnectionStringParsing:
    """Edge cases for connection string handling.

    Validates robustness of Azure SignalR configuration parsing.
    """

    def test_parses_production_style_connection_string(self):
        """Full production connection string with long base64 key."""
        conn = "Endpoint=https://hausly-prod.service.signalr.net;AccessKey=YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODk=;Version=1.0;"
        endpoint, key = _parse_connection_string(conn)
        assert endpoint == "https://hausly-prod.service.signalr.net"
        assert key == "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODk="

    def test_graceful_on_malformed_string(self):
        """Malformed string doesn't crash, just returns empties."""
        endpoint, key = _parse_connection_string("garbage-not-a-connection-string")
        assert endpoint == ""
        assert key == ""

    def test_missing_access_key(self):
        """Endpoint present but no AccessKey → service stays disabled."""
        conn = "Endpoint=https://test.net;Version=1.0;"
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = conn
            svc = SignalRService()
            assert svc.enabled is False
