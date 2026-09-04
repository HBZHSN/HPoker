"""Room Manager service with durable, atomic room checkpoints."""

from __future__ import annotations
import json
import logging
import os
import threading
from typing import Dict, List, Optional

from backend.app.database import DEFAULT_DATABASE_PATH, SQLiteDatabase
from backend.app.models.room import Room, RoomConfig
from backend.app.services.hand_history_manager import HandHistoryManager

logger = logging.getLogger("poker.rooms")
LEGACY_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "rooms.json",
)


class RoomManager:
    """Manage active poker rooms and persist safe checkpoints in SQLite."""

    def __init__(
        self,
        database_path: Optional[str] = None,
        *,
        storage_path: Optional[str] = None,
        legacy_storage_path: Optional[str] = None,
    ):
        if database_path is not None and storage_path is not None:
            raise ValueError("database_path and storage_path cannot both be set")
        selected_path = database_path if database_path is not None else storage_path
        self._database = SQLiteDatabase(selected_path)
        self.storage_path = self._database.path
        self.legacy_storage_path = legacy_storage_path
        if (
            legacy_storage_path is None
            and self.storage_path == os.path.realpath(DEFAULT_DATABASE_PATH)
        ):
            self.legacy_storage_path = LEGACY_STORAGE_FILE
        self._rooms: Dict[str, Room] = {}
        self.hand_history_manager = HandHistoryManager(database_path=self.storage_path)
        self._storage_lock = threading.RLock()
        self.load_from_storage()

    def _migrate_legacy_json(self) -> None:
        """Import rooms.json exactly once when creating the production DB."""
        migration_name = "rooms_json_v1"
        if self._database.migration_applied(migration_name):
            return
        if self._database.load_rooms():
            self._database.mark_migration_applied(migration_name)
            return

        legacy_path = self.legacy_storage_path
        if legacy_path and os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as storage_file:
                    payload = json.load(storage_file)
                self._database.replace_rooms(payload.get("rooms", []))
            except (OSError, ValueError, KeyError):
                logger.exception("Failed to migrate room checkpoints from %s", legacy_path)
                raise
        self._database.mark_migration_applied(migration_name)

    def load_from_storage(self) -> None:
        """Load all unsettled rooms from durable SQLite checkpoints."""
        self._rooms.clear()
        self._migrate_legacy_json()
        for room_data in self._database.load_rooms():
            room = Room.from_checkpoint_dict(room_data)
            self._rooms[room.room_id] = room

    def save_to_storage(self) -> None:
        """Atomically flush all unsettled room checkpoints to SQLite."""
        with self._storage_lock:
            self._database.replace_rooms(
                [
                    room.to_checkpoint_dict()
                    for room in self._rooms.values()
                    if not room.is_ended
                ]
            )

    def checkpoint_room(self, room: Room) -> None:
        """Record a completed hand if needed, then flush a safe checkpoint."""
        completed_hand = room.record_completed_hand()
        if completed_hand:
            self.hand_history_manager.record_hand(completed_hand)
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
            if r.is_ended:
                continue
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
                "assistant_win_ratio": r.config.assistant_win_ratio,
                "assistant_win_pct": int(round(r.config.assistant_win_ratio * 100)),
                "is_ended": r.is_ended,
            })
        return rooms_info

    def delete_room(self, room_id: str, reason: str = "room_deleted") -> bool:
        room = self._rooms.get(room_id)
        if room is not None:
            # Deletion is also a cash-out boundary. Calling this after
            # ``Room.end_room`` is harmless because that method empties seats.
            room.cash_out_all_players(reason=reason)
            room.is_ended = True
            del self._rooms[room_id]
            self.save_to_storage()
            return True
        return False


# Global instance
room_manager = RoomManager()
