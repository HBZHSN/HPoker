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

    def get_lifetime_net_cash(self, user_id: str) -> float:
        """Sum completed hands in cents, independently of wallet transfers or paging."""
        with self._database.connection() as connection:
            cents = connection.execute(
                "SELECT COALESCE(SUM(net_cash_cents), 0) FROM poker_hand_players WHERE player_id=?",
                (user_id,),
            ).fetchone()[0]
        return cents / 100.0

    def list_user_tables(self, user_id: str, limit: int = 20, offset: int = 0) -> dict:
        """Group all completed hands by durable room ID, including deleted rooms."""
        with self._database.connection() as connection:
            total = connection.execute('''SELECT COUNT(DISTINCT h.room_id)
                FROM poker_hands h JOIN poker_hand_players p ON p.hand_id=h.hand_id
                WHERE p.player_id=?''', (user_id,)).fetchone()[0]
            rows = connection.execute('''SELECT h.room_id,
                MIN(h.ended_at) AS first_hand_at, MAX(h.ended_at) AS last_hand_at,
                COUNT(*) AS hands, SUM(p.net_chips) AS net_chips,
                SUM(p.net_cash_cents) / 100.0 AS net_cash,
                SUM(p.net_chips > 0) AS winning_hands,
                MAX(p.net_chips) AS biggest_win, MIN(p.net_chips) AS biggest_loss,
                SUM(p.contributed_chips) AS contributed_chips,
                SUM(p.payout_chips) AS payout_chips
                FROM poker_hands h JOIN poker_hand_players p ON p.hand_id=h.hand_id
                WHERE p.player_id=? GROUP BY h.room_id
                ORDER BY last_hand_at DESC, h.room_id LIMIT ? OFFSET ?''',
                (user_id, max(1, min(limit, 100)), max(0, offset))).fetchall()
            tables = []
            for row in rows:
                item = dict(row)
                latest = connection.execute('''SELECT h.room_name, h.small_blind,
                    h.big_blind, h.money_mode FROM poker_hands h
                    JOIN poker_hand_players p ON p.hand_id=h.hand_id
                    WHERE h.room_id=? AND p.player_id=?
                    ORDER BY h.ended_at DESC, h.hand_id DESC LIMIT 1''',
                    (item['room_id'], user_id)).fetchone()
                item.update(dict(latest))
                tables.append(item)
        return {'tables': tables, 'total': total}


hand_history_manager = HandHistoryManager()
