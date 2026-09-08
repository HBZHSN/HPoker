"""Small, predictable REST client used by the terminal UI."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class PokerApiError(RuntimeError):
    """User-facing API failure with the HTTP status retained for callers."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class PokerApiClient:
    """Handles REST API communication for authentication and room lifecycle."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            trust_env=False,
        )
        self.auth_token: Optional[str] = None

    def _auth_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        active_token = token or self.auth_token
        return {"Authorization": f"Bearer {active_token}"} if active_token else {}

    async def close(self) -> None:
        """Close the underlying HTTP session; safe to call more than once."""

        if not self.client.is_closed:
            await self.client.aclose()

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Extract FastAPI's detail field without assuming a JSON response."""

        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("message")
            if detail:
                if isinstance(detail, list):
                    return "; ".join(str(item.get("msg", item)) for item in detail)
                return str(detail)
        return response.text or f"HTTP {response.status_code}"

    @classmethod
    def _raise_for_status(cls, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = cls._error_detail(response)
            raise PokerApiError(detail, response.status_code) from exc

    async def list_users(self, token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch users via admin endpoint."""
        response = await self.client.get(
            "/api/admin/users",
            headers=self._auth_headers(token),
        )
        self._raise_for_status(response)
        payload = response.json()
        return payload if isinstance(payload, list) else []

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login and get user data with auth token."""

        response = await self.client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        self._raise_for_status(response)
        payload = response.json()
        if isinstance(payload, dict):
            self.auth_token = payload.get("token")
        return payload

    async def get_me(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a token and return the current user."""

        response = await self.client.get(
            "/api/auth/me",
            headers=self._auth_headers(token),
        )
        self._raise_for_status(response)
        payload = response.json()
        return payload.get("user") if isinstance(payload, dict) else None

    async def list_rooms(self, include_ended: bool = False) -> List[Dict[str, Any]]:
        """Fetch rooms, hiding ended rooms from the lobby by default."""

        response = await self.client.get("/api/rooms")
        self._raise_for_status(response)
        payload = response.json()
        rooms = payload if isinstance(payload, list) else []
        if include_ended:
            return rooms
        return [room for room in rooms if not room.get("is_ended", False)]

    async def create_room(
        self,
        room_name: str = "HPoker 现金桌",
        buyin_chips: int = 1000,
        cash_value: float = 100.0,
        small_blind: int = 10,
        action_timeout: int = 15,
        max_seats: int = 6,
    ) -> Dict[str, Any]:
        """Create a new poker room."""

        payload = {
            "room_name": room_name,
            "buyin_chips": buyin_chips,
            "cash_value": cash_value,
            "small_blind": small_blind,
            "action_timeout": action_timeout,
            "max_seats": max_seats,
        }
        response = await self.client.post(
            "/api/rooms",
            headers=self._auth_headers(),
            json=payload,
        )
        self._raise_for_status(response)
        return response.json()

    async def get_room(
        self,
        room_id: str,
    ) -> Dict[str, Any]:
        """Fetch a room snapshot through REST."""

        response = await self.client.get(
            f"/api/rooms/{room_id}",
            headers=self._auth_headers(),
        )
        self._raise_for_status(response)
        return response.json()

    async def end_room(
        self,
        room_id: str,
        settlement_type: str = "balance",
    ) -> Dict[str, Any]:
        """End a room and return its settlement report."""

        response = await self.client.post(
            f"/api/rooms/{room_id}/end",
            headers=self._auth_headers(),
            params={"settlement_type": settlement_type},
        )
        self._raise_for_status(response)
        return response.json()

    async def delete_room(
        self,
        room_id: str,
    ) -> Dict[str, Any]:
        """Delete a room as its host or an administrator."""

        response = await self.client.delete(
            f"/api/rooms/{room_id}",
            headers=self._auth_headers(),
        )
        self._raise_for_status(response)
        return response.json()

    async def add_test_bot(
        self,
        room_id: str,
        seat_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Add a virtual test bot to the room through REST."""

        params: Dict[str, Any] = {}
        if seat_index is not None:
            params["seat_index"] = seat_index
        response = await self.client.post(
            f"/api/rooms/{room_id}/test-bots",
            headers=self._auth_headers(),
            params=params,
        )
        self._raise_for_status(response)
        return response.json()
