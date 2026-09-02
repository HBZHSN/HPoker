"""HTTP API Client for Poker CLI."""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import httpx


class PokerApiClient:
    """Handles REST API communication with the Poker backend."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0, trust_env=False)

    async def close(self):
        """Close HTTP client session."""
        await self.client.aclose()

    async def list_users(self) -> List[Dict[str, Any]]:
        """Fetch all registered/preset users."""
        resp = await self.client.get("/api/users")
        resp.raise_for_status()
        return resp.json()

    async def login(self, username: str, password: str = "123") -> Dict[str, Any]:
        """Login and get user data with auth token."""
        resp = await self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_me(self, token: str) -> Dict[str, Any]:
        """Verify token and get current user info."""
        resp = await self.client.get(f"/api/auth/me?token={token}")
        resp.raise_for_status()
        return resp.json().get("user")

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """Fetch all active rooms."""
        resp = await self.client.get("/api/rooms")
        resp.raise_for_status()
        return resp.json()

    async def create_room(
        self,
        host_player_id: str,
        room_name: str = "HPoker 现金桌",
        buyin_chips: int = 1000,
        cash_value: float = 100.0,
        small_blind: int = 10,
        action_timeout: int = 15,
        max_seats: int = 6,
    ) -> Dict[str, Any]:
        """Create a new poker room."""
        payload = {
            "host_player_id": host_player_id,
            "room_name": room_name,
            "buyin_chips": buyin_chips,
            "cash_value": cash_value,
            "small_blind": small_blind,
            "action_timeout": action_timeout,
            "max_seats": max_seats,
        }
        resp = await self.client.post("/api/rooms", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_room(self, room_id: str, viewer_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch room details."""
        url = f"/api/rooms/{room_id}"
        if viewer_id:
            url += f"?viewer_id={viewer_id}"
        resp = await self.client.get(url)
        resp.raise_for_status()
        return resp.json()

    async def end_room(self, room_id: str, requester_id: str) -> Dict[str, Any]:
        """End room and get settlement report."""
        resp = await self.client.post(
            f"/api/rooms/{room_id}/end?requester_id={requester_id}"
        )
        resp.raise_for_status()
        return resp.json()
