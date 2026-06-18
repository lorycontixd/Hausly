"""Azure SignalR serverless integration — broadcasts mutations to household clients."""

import hashlib
import hmac
import json
import logging
import time
import uuid
from base64 import b64decode
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from hausly.config import settings

logger = logging.getLogger(__name__)

HUB_NAME = "household"


def _parse_connection_string(conn_str: str) -> tuple[str, str]:
    """Parse SignalR connection string into (endpoint, access_key)."""
    parts: dict[str, str] = {}
    for segment in conn_str.split(";"):
        segment = segment.strip()
        if "=" in segment:
            key, _, value = segment.partition("=")
            # AccessKey may contain '=' in base64
            if key == "AccessKey":
                value = segment[len("AccessKey="):]
            parts[key] = value
    endpoint = parts.get("Endpoint", "").rstrip("/")
    access_key = parts.get("AccessKey", "")
    return endpoint, access_key


def _generate_jwt(audience: str, access_key: str, claims: dict[str, Any] | None = None, ttl: int = 300) -> str:
    """Generate HS256 JWT for SignalR authentication."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "aud": audience,
        "exp": now + ttl,
        "iat": now,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, access_key, algorithm="HS256")


class SignalRService:
    """Manages Azure SignalR serverless interactions."""

    def __init__(self) -> None:
        self._endpoint: str = ""
        self._access_key: str = ""
        self._enabled: bool = False
        self._client: httpx.AsyncClient | None = None
        self._configure()

    def _configure(self) -> None:
        conn_str = settings.signalr_connection_string
        if not conn_str:
            logger.warning("SIGNALR_CONNECTION_STRING not set — real-time broadcasts disabled")
            return
        self._endpoint, self._access_key = _parse_connection_string(conn_str)
        if not self._endpoint or not self._access_key:
            logger.warning("Invalid SignalR connection string — real-time broadcasts disabled")
            return
        self._enabled = True
        self._client = httpx.AsyncClient(timeout=5.0)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def generate_client_token(self, user_id: str, household_id: str) -> dict[str, str]:
        """Generate negotiate response for client connection."""
        client_url = f"{self._endpoint}/client/?hub={HUB_NAME}"
        group = f"household:{household_id}"
        claims = {
            "sub": user_id,
            "asrs.s.gp": group,
        }
        token = _generate_jwt(client_url, self._access_key, claims=claims, ttl=3600)
        return {"url": client_url, "accessToken": token}

    async def broadcast_to_household(
        self, household_id: uuid.UUID, event_name: str, payload: Any
    ) -> None:
        """Send event to all connections in a household group. Fire-and-forget."""
        if not self._enabled or self._client is None:
            return

        group = f"household:{household_id}"
        url = f"{self._endpoint}/api/hubs/{HUB_NAME}/groups/{group}"

        server_token = _generate_jwt(url, self._access_key, ttl=300)
        headers = {
            "Authorization": f"Bearer {server_token}",
            "Content-Type": "application/json",
        }
        body = {"target": event_name, "arguments": [payload]}

        try:
            resp = await self._client.post(url, headers=headers, json=body)
            if resp.status_code >= 400:
                logger.warning(
                    "SignalR broadcast failed: %s %s -> %d",
                    event_name,
                    group,
                    resp.status_code,
                )
        except Exception:
            logger.warning("SignalR broadcast error for %s %s", event_name, group, exc_info=True)

    # --- Type-safe event wrappers ---

    async def grocery_item_added(self, household_id: uuid.UUID, item: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "grocery_item_added", item)

    async def grocery_item_updated(self, household_id: uuid.UUID, item: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "grocery_item_updated", item)

    async def grocery_item_removed(self, household_id: uuid.UUID, item_id: str) -> None:
        await self.broadcast_to_household(household_id, "grocery_item_removed", {"item_id": item_id})

    async def grocery_list_archived(self, household_id: uuid.UUID, list_id: str) -> None:
        await self.broadcast_to_household(household_id, "grocery_list_archived", {"list_id": list_id})

    async def grocery_session_completed(
        self, household_id: uuid.UUID, bought_item_ids: list[str], expense_draft_id: str | None
    ) -> None:
        await self.broadcast_to_household(
            household_id,
            "grocery_session_completed",
            {"bought_item_ids": bought_item_ids, "expense_draft_id": expense_draft_id},
        )

    async def expense_created(self, household_id: uuid.UUID, expense: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "expense_created", expense)

    async def expense_confirmed(self, household_id: uuid.UUID, expense_id: str) -> None:
        await self.broadcast_to_household(household_id, "expense_confirmed", {"expense_id": expense_id})

    async def expense_settled(self, household_id: uuid.UUID, split_id: str) -> None:
        await self.broadcast_to_household(household_id, "expense_settled", {"split_id": split_id})

    async def meal_entry_created(self, household_id: uuid.UUID, entry: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "meal_entry_created", entry)

    async def meal_entry_updated(self, household_id: uuid.UUID, entry: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "meal_entry_updated", entry)

    async def meal_entry_removed(self, household_id: uuid.UUID, entry_id: str) -> None:
        await self.broadcast_to_household(household_id, "meal_entry_removed", {"entry_id": entry_id})

    async def chore_created(self, household_id: uuid.UUID, chore: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "chore_created", chore)

    async def chore_deleted(self, household_id: uuid.UUID, chore_id: str) -> None:
        await self.broadcast_to_household(household_id, "chore_deleted", {"chore_id": chore_id})

    async def assignment_completed(
        self, household_id: uuid.UUID, assignment_id: str, completed_by: str
    ) -> None:
        await self.broadcast_to_household(
            household_id,
            "assignment_completed",
            {"assignment_id": assignment_id, "completed_by": completed_by},
        )

    async def assignment_updated(self, household_id: uuid.UUID, assignment: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "assignment_updated", assignment)

    async def member_joined(self, household_id: uuid.UUID, user: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "member_joined", user)

    async def member_left(self, household_id: uuid.UUID, user_id: str) -> None:
        await self.broadcast_to_household(household_id, "member_left", {"user_id": user_id})

    async def household_settings_updated(self, household_id: uuid.UUID, settings: dict[str, Any]) -> None:
        await self.broadcast_to_household(household_id, "household_settings_updated", settings)


# Singleton instance
signalr_service = SignalRService()
