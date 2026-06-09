"""Tests for SignalR service and negotiate endpoint."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hausly.realtime.signalr import (HUB_NAME, SignalRService, _generate_jwt,
                                     _parse_connection_string, signalr_service)

# --- Unit tests for helpers ---


class TestParseConnectionString:
    def test_parses_valid_connection_string(self):
        conn = "Endpoint=https://test.service.signalr.net;AccessKey=dGVzdGtleQ==;Version=1.0;"
        endpoint, key = _parse_connection_string(conn)
        assert endpoint == "https://test.service.signalr.net"
        assert key == "dGVzdGtleQ=="

    def test_strips_trailing_slash_from_endpoint(self):
        conn = "Endpoint=https://test.service.signalr.net/;AccessKey=abc123;Version=1.0;"
        endpoint, key = _parse_connection_string(conn)
        assert endpoint == "https://test.service.signalr.net"

    def test_returns_empty_on_missing_parts(self):
        endpoint, key = _parse_connection_string("")
        assert endpoint == ""
        assert key == ""

    def test_handles_access_key_with_equals(self):
        conn = "Endpoint=https://x.net;AccessKey=abc123def456==;Version=1.0;"
        endpoint, key = _parse_connection_string(conn)
        assert key == "abc123def456=="


class TestGenerateJwt:
    def test_generates_valid_jwt(self):
        import jwt as pyjwt

        access_key = "test-secret-key-for-signing-tokens"
        token = _generate_jwt("https://test.net/client", access_key, ttl=60)
        decoded = pyjwt.decode(token, access_key, algorithms=["HS256"], audience="https://test.net/client")
        assert decoded["aud"] == "https://test.net/client"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_includes_custom_claims(self):
        import jwt as pyjwt

        access_key = "test-key"
        claims = {"sub": "user-123", "asrs.s.gp": "household:abc"}
        token = _generate_jwt("https://test.net/client", access_key, claims=claims, ttl=3600)
        decoded = pyjwt.decode(token, access_key, algorithms=["HS256"], audience="https://test.net/client")
        assert decoded["sub"] == "user-123"
        assert decoded["asrs.s.gp"] == "household:abc"


# --- SignalRService unit tests ---


class TestSignalRService:
    def test_disabled_when_no_connection_string(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = ""
            svc = SignalRService()
            assert svc.enabled is False

    def test_enabled_with_valid_connection_string(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=dGVzdGtleQ==;Version=1.0;"
            )
            svc = SignalRService()
            assert svc.enabled is True

    def test_generate_client_token_structure(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-secret-key;Version=1.0;"
            )
            svc = SignalRService()
            result = svc.generate_client_token("user-1", "household-1")
            assert "url" in result
            assert "accessToken" in result
            assert result["url"] == "https://test.service.signalr.net/client/?hub=household"

    def test_generate_client_token_contains_claims(self):
        import jwt as pyjwt

        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-secret-key;Version=1.0;"
            )
            svc = SignalRService()
            result = svc.generate_client_token("user-abc", "hh-123")
            decoded = pyjwt.decode(
                result["accessToken"],
                "test-secret-key",
                algorithms=["HS256"],
                audience="https://test.service.signalr.net/client/?hub=household",
            )
            assert decoded["sub"] == "user-abc"
            assert decoded["asrs.s.gp"] == "household:hh-123"

    @pytest.mark.anyio
    async def test_broadcast_noop_when_disabled(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = ""
            svc = SignalRService()
            # Should not raise
            await svc.broadcast_to_household(uuid.uuid4(), "test:event", {"key": "val"})

    @pytest.mark.anyio
    async def test_broadcast_sends_correct_request(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-secret-key;Version=1.0;"
            )
            svc = SignalRService()
            mock_response = MagicMock()
            mock_response.status_code = 202
            svc._client = AsyncMock()
            svc._client.post = AsyncMock(return_value=mock_response)

            hh_id = uuid.uuid4()
            await svc.broadcast_to_household(hh_id, "grocery:item_added", {"name": "Milk"})

            svc._client.post.assert_called_once()
            call_args = svc._client.post.call_args
            url = call_args[0][0]
            assert f"household:{hh_id}" in url
            assert "hubs/household/groups/" in url
            body = call_args[1]["json"]
            assert body["target"] == "grocery:item_added"
            assert body["arguments"] == [{"name": "Milk"}]

    @pytest.mark.anyio
    async def test_broadcast_logs_warning_on_http_error(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-key;Version=1.0;"
            )
            svc = SignalRService()
            mock_response = MagicMock()
            mock_response.status_code = 500
            svc._client = AsyncMock()
            svc._client.post = AsyncMock(return_value=mock_response)

            # Should not raise — fire-and-forget
            await svc.broadcast_to_household(uuid.uuid4(), "test:event", {})

    @pytest.mark.anyio
    async def test_broadcast_logs_warning_on_network_error(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.service.signalr.net;AccessKey=test-key;Version=1.0;"
            )
            svc = SignalRService()
            svc._client = AsyncMock()
            svc._client.post = AsyncMock(side_effect=Exception("Connection refused"))

            # Should not raise — fire-and-forget
            await svc.broadcast_to_household(uuid.uuid4(), "test:event", {})


# --- Event wrapper tests ---


class TestEventWrappers:
    @pytest.mark.anyio
    async def test_grocery_item_added_calls_broadcast(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.net;AccessKey=key;Version=1.0;"
            )
            svc = SignalRService()
            svc.broadcast_to_household = AsyncMock()
            hh_id = uuid.uuid4()
            await svc.grocery_item_added(hh_id, {"id": "item-1", "name": "Bread"})
            svc.broadcast_to_household.assert_called_once_with(
                hh_id, "grocery:item_added", {"id": "item-1", "name": "Bread"}
            )

    @pytest.mark.anyio
    async def test_expense_created_calls_broadcast(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.net;AccessKey=key;Version=1.0;"
            )
            svc = SignalRService()
            svc.broadcast_to_household = AsyncMock()
            hh_id = uuid.uuid4()
            await svc.expense_created(hh_id, {"id": "exp-1", "title": "Groceries"})
            svc.broadcast_to_household.assert_called_once_with(
                hh_id, "expense:created", {"id": "exp-1", "title": "Groceries"}
            )

    @pytest.mark.anyio
    async def test_chore_completed_calls_broadcast(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.net;AccessKey=key;Version=1.0;"
            )
            svc = SignalRService()
            svc.broadcast_to_household = AsyncMock()
            hh_id = uuid.uuid4()
            await svc.chore_completed(hh_id, "assign-1", "user-1")
            svc.broadcast_to_household.assert_called_once_with(
                hh_id,
                "chore:completed",
                {"assignment_id": "assign-1", "completed_by": "user-1"},
            )

    @pytest.mark.anyio
    async def test_meal_removed_calls_broadcast(self):
        with patch("hausly.realtime.signalr.settings") as mock_settings:
            mock_settings.signalr_connection_string = (
                "Endpoint=https://test.net;AccessKey=key;Version=1.0;"
            )
            svc = SignalRService()
            svc.broadcast_to_household = AsyncMock()
            hh_id = uuid.uuid4()
            await svc.meal_removed(hh_id, "entry-1")
            svc.broadcast_to_household.assert_called_once_with(
                hh_id, "meal:removed", {"entry_id": "entry-1"}
            )
