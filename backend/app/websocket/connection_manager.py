"""WebSocket Connection Manager for managing real-time poker game sessions."""

from __future__ import annotations
import json
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket

from backend.app.websocket.protocol import EventType, make_message
from backend.app.models.room import Room

logger = logging.getLogger("poker.ws")


class ConnectionManager:
    """Manages active WebSockets by room and user."""

    def __init__(self):
        # room_id -> set of active WebSockets
        self.room_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> (room_id, user_id)
        self.socket_info: Dict[WebSocket, tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, room_id: str, user_id: str) -> None:
        await websocket.accept()
        if room_id not in self.room_connections:
            self.room_connections[room_id] = set()
        self.room_connections[room_id].add(websocket)
        self.socket_info[websocket] = (room_id, user_id)
        logger.info(f"User {user_id} connected to room {room_id}")

    def get_room_connections(self, room_id: str) -> Set[WebSocket]:
        """Return the set of active WebSockets for a room."""
        return set(self.room_connections.get(room_id, set()))

    def get_room_connection_count(self, room_id: str) -> int:
        """Return number of active WebSocket connections in a room."""
        return len(self.room_connections.get(room_id, set()))

    def has_connections(self, room_id: str) -> bool:
        """Check if a room currently has any connected clients."""
        return self.get_room_connection_count(room_id) > 0

    async def close_room_connections(self, room_id: str, reason: str = "Room deleted") -> None:
        """Close all WebSocket connections associated with a room."""
        sockets = list(self.room_connections.get(room_id, set()))
        for ws in sockets:
            self.socket_info.pop(ws, None)
            try:
                await ws.close(reason=reason)
            except Exception:
                pass
        self.room_connections.pop(room_id, None)

    def disconnect(self, websocket: WebSocket) -> tuple[Optional[str], Optional[str]]:
        info = self.socket_info.pop(websocket, None)
        if info:
            room_id, user_id = info
            if room_id in self.room_connections:
                self.room_connections[room_id].discard(websocket)
                if not self.room_connections[room_id]:
                    del self.room_connections[room_id]
            logger.info(f"User {user_id} disconnected from room {room_id}")
            return room_id, user_id
        return None, None

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")

    async def broadcast_room_state(self, room: Room) -> None:
        """Broadcast customized room snapshots to each connected client in the room."""
        # Every state-changing WebSocket route finishes with a broadcast,
        # including automated timeout and bot actions.
        from backend.app.services.room_manager import room_manager
        room_manager.checkpoint_room(room)

        room_id = room.room_id
        sockets = self.room_connections.get(room_id, set())
        for ws in list(sockets):
            info = self.socket_info.get(ws)
            if not info:
                continue
            _, user_id = info
            state_data = room.to_dict(viewer_player_id=user_id)
            msg = make_message(EventType.ROOM_STATE, state_data, room_id=room_id)
            try:
                await ws.send_text(json.dumps(msg))
            except Exception as e:
                logger.warning(f"Failed to send state to user {user_id}: {e}")

    async def broadcast_sound(self, room_id: str, sound_name: str, payload: Optional[dict] = None) -> None:
        """Broadcast sound effect cue (e.g., 'deal', 'check', 'call', 'raise', 'fold', 'allin', 'win_pot')."""
        sockets = self.room_connections.get(room_id, set())
        msg = make_message(EventType.SOUND_EFFECT, {
            "sound": sound_name,
            **(payload or {})
        }, room_id=room_id)
        raw = json.dumps(msg)
        for ws in list(sockets):
            try:
                await ws.send_text(raw)
            except Exception as e:
                logger.warning(f"Failed to send sound to socket: {e}")


# Global singleton
ws_manager = ConnectionManager()
