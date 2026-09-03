"""Room Manager service with durable, atomic room checkpoints."""

from __future__ import annotations
import json
import logging
import os
import threading
from typing import Dict, List, Optional
from backend.app.models.room import Room, RoomConfig

logger = logging.getLogger("poker.rooms")
DEFAULT_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "rooms.json",
)


class RoomManager:
    """Manage active poker rooms and atomically persist safe checkpoints."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = (
            storage_path
            if storage_path is not None
            else os.environ.get("ROOMS_DATA_FILE", DEFAULT_STORAGE_FILE)
        )
        self._rooms: Dict[str, Room] = {}
        self._storage_lock = threading.RLock()
        self.load_from_storage()

    def load_from_storage(self) -> None:
        """Load all un-settled rooms from the durable checkpoint file."""
        self._rooms.clear()
        if (
            not self.storage_path
            or self.storage_path == ":memory:"
            or not os.path.exists(self.storage_path)
        ):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as storage_file:
                payload = json.load(storage_file)
            for room_data in payload.get("rooms", []):
                room = Room.from_checkpoint_dict(room_data)
                self._rooms[room.room_id] = room
        except Exception:
            logger.exception("Failed to load room checkpoints from %s", self.storage_path)

    def save_to_storage(self) -> None:
        """Atomically flush all un-settled room checkpoints to disk."""
        if not self.storage_path or self.storage_path == ":memory:":
            return
        with self._storage_lock:
            try:
                storage_dir = os.path.dirname(os.path.abspath(self.storage_path))
                os.makedirs(storage_dir, exist_ok=True)
                payload = {
                    "version": 1,
                    "rooms": [
                        room.to_checkpoint_dict()
                        for room in self._rooms.values()
                        if not room.is_ended
                    ],
                }
                tmp_path = f"{self.storage_path}.tmp"
                with open(tmp_path, "w", encoding="utf-8") as storage_file:
                    json.dump(payload, storage_file, ensure_ascii=False, indent=2)
                    storage_file.flush()
                    os.fsync(storage_file.fileno())
                os.replace(tmp_path, self.storage_path)
            except Exception:
                logger.exception("Failed to save room checkpoints to %s", self.storage_path)

    def checkpoint_room(self, room: Room) -> None:
        """Record a completed hand if needed, then flush a safe checkpoint."""
        room.record_completed_hand()
        self.save_to_storage()

    def create_room(self, host_player_id: str, config: RoomConfig, room_id: Optional[str] = None) -> Room:
        room = Room(host_player_id=host_player_id, config=config, room_id=room_id)
        self._rooms[room.room_id] = room
        self.save_to_storage()
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
            self.save_to_storage()
            return True
        return False


# Global instance
room_manager = RoomManager()
