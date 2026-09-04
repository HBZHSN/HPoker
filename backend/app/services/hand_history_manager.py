"""Durable, private per-user poker hand history queries."""

from __future__ import annotations

from typing import Optional

from backend.app.database import SQLiteDatabase


class HandHistoryManager:
    def __init__(self, database_path: Optional[str] = None):
        self._database = SQLiteDatabase(database_path)
        self.storage_path = self._database.path

    def record_hand(self, hand: dict) -> bool:
        return self._database.save_hand_history(hand)

    def list_user_hands(self, user_id: str, **filters) -> dict:
        hands = self._database.query_user_hand_history(user_id, **filters)
        all_hands = self._database.query_user_hand_history(
            user_id,
            outcome=filters.get("outcome"),
            room_id=filters.get("room_id"),
            started_at=filters.get("started_at"),
            ended_at=filters.get("ended_at"),
            sort_by="ended_at",
            order="desc",
            limit=100_000,
            offset=0,
        )
        biggest_win = max(all_hands, key=lambda item: item["net_chips"], default=None)
        biggest_loss = min(all_hands, key=lambda item: item["net_chips"], default=None)
        if biggest_win and biggest_win["net_chips"] <= 0:
            biggest_win = None
        if biggest_loss and biggest_loss["net_chips"] >= 0:
            biggest_loss = None
        return {
            "hands": hands,
            "total": len(all_hands),
            "summary": {
                "net_chips": sum(item["net_chips"] for item in all_hands),
                "net_cash": round(sum(item["net_cash"] for item in all_hands), 2),
                "biggest_win": biggest_win,
                "biggest_loss": biggest_loss,
            },
        }

    def clear_all(self) -> int:
        return self._database.clear_hand_histories()


hand_history_manager = HandHistoryManager()
