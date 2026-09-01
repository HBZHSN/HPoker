"""Room Manager service for creating, retrieving, and listing rooms."""

from __future__ import annotations
from typing import Dict, List, Optional
from backend.app.models.room import Room, RoomConfig


class RoomManager:
    """Singleton-style in-memory manager for active poker rooms."""

    def __init__(self):
        self._rooms: Dict[str, Room] = {}

    def create_room(self, host_player_id: str, config: RoomConfig, room_id: Optional[str] = None) -> Room:
        room = Room(host_player_id=host_player_id, config=config, room_id=room_id)
        self._rooms[room.room_id] = room
        return room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self._rooms.get(room_id)

    def list_rooms(self) -> List[dict]:
        rooms_info = []
        for r in self._rooms.values():
            rooms_info.append({
                "room_id": r.room_id,
                "room_name": r.config.room_name,
                "host_player_id": r.host_player_id,
                "seated_count": len(r.table.active_seated_players),
                "max_seats": r.config.max_seats,
                "small_blind": r.config.small_blind,
                "big_blind": r.config.big_blind,
                "buyin_chips": r.config.buyin_chips,
                "cash_value": r.config.cash_value,
                "is_ended": r.is_ended,
            })
        return rooms_info

    def delete_room(self, room_id: str) -> bool:
        if room_id in self._rooms:
            del self._rooms[room_id]
            return True
        return False


# Global instance
room_manager = RoomManager()
