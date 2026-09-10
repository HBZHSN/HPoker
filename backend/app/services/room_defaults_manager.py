"""Durable administrator-managed defaults for newly created rooms."""

from __future__ import annotations

from typing import Any, Optional

from backend.app.database import SQLiteDatabase
from backend.app.models.room_defaults import RoomDefaultConfig


class RoomDefaultsManager:
    """Read and update the singleton room-creation defaults."""

    def __init__(self, database_path: Optional[str] = None):
        self._database = SQLiteDatabase(database_path)
        self.storage_path = self._database.path

    def get_config(self) -> RoomDefaultConfig:
        stored = self._database.load_room_defaults()
        if not stored:
            return RoomDefaultConfig.default()
        return RoomDefaultConfig.from_values(
            buyin_chips=stored["buyin_chips"],
            cash_value=stored["cash_value"],
            small_blind=stored["small_blind"],
            action_timeout=stored["action_timeout"],
            max_seats=stored["max_seats"],
            assistant_win_ratio=stored["assistant_win_ratio"],
        )

    def update_config(
        self,
        *,
        buyin_chips: Any,
        cash_value: Any,
        small_blind: Any,
        action_timeout: Any,
        max_seats: Any,
        assistant_win_ratio: Any,
        updated_by: Optional[str],
    ) -> RoomDefaultConfig:
        config = RoomDefaultConfig.from_values(
            buyin_chips=buyin_chips,
            cash_value=cash_value,
            small_blind=small_blind,
            action_timeout=action_timeout,
            max_seats=max_seats,
            assistant_win_ratio=assistant_win_ratio,
        )
        self._database.save_room_defaults(config.to_dict(), updated_by=updated_by)
        return config

    def reset_to_defaults(self) -> RoomDefaultConfig:
        config = RoomDefaultConfig.default()
        self._database.save_room_defaults(config.to_dict(), updated_by=None)
        return config


room_defaults_manager = RoomDefaultsManager()
