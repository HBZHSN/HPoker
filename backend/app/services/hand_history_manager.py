"""Durable, private per-user poker hand history queries."""

from __future__ import annotations

from typing import Optional
import json
import time

from backend.app.database import SQLiteDatabase

OVERVIEW_VERSION = 1


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

    def get_user_overview(self, user_id: str) -> dict:
        """Read a departure snapshot; a cache miss never scans hand history."""
        with self._database.connection() as connection:
            row = connection.execute(
                "SELECT overview_json FROM poker_user_overviews WHERE player_id=? AND version=?",
                (user_id, OVERVIEW_VERSION),
            ).fetchone()
        if row:
            return json.loads(row["overview_json"])
        from backend.app.services.player_statistics import summarize
        from backend.app.services.comprehensive_luck import aggregate_luck
        return {
            "total": 0,
            "summary": {"net_chips": 0, "net_cash": 0, "biggest_win": None},
            "statistics": {**summarize([], user_id), **aggregate_luck([])},
            "generated_at": None,
        }

    def refresh_user_overviews(self, user_ids) -> None:
        """Build all affected snapshots, then publish them atomically."""
        from backend.app.services.player_statistics import query_statistics
        snapshots = []
        for user_id in sorted(set(user_ids)):
            payload = {
                **self._calculate_user_overview(user_id),
                "statistics": query_statistics(self._database, user_id),
                "generated_at": time.time(),
            }
            snapshots.append((user_id, OVERVIEW_VERSION, payload["generated_at"], json.dumps(payload)))
        if snapshots:
            with self._database.connection(write=True) as connection:
                connection.executemany(
                    """INSERT INTO poker_user_overviews(player_id, version, generated_at, overview_json)
                       VALUES (?, ?, ?, ?) ON CONFLICT(player_id) DO UPDATE SET
                       version=excluded.version, generated_at=excluded.generated_at,
                       overview_json=excluded.overview_json""", snapshots)

    def backfill_user_overviews(self) -> None:
        """Migrate historical users before serving requests, never on a cache read."""
        with self._database.connection() as connection:
            users = [row[0] for row in connection.execute(
                """SELECT DISTINCT p.player_id FROM poker_hand_players p
                   LEFT JOIN poker_user_overviews c ON c.player_id=p.player_id AND c.version=?
                   WHERE c.player_id IS NULL""", (OVERVIEW_VERSION,))]
        self.refresh_user_overviews(users)

    def _calculate_user_overview(self, user_id: str) -> dict:
        """Aggregate lifetime results without exposing any individual hand."""
        with self._database.connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS total, COALESCE(SUM(net_chips), 0) AS net_chips,
                          COALESCE(SUM(net_cash_cents), 0) AS net_cash_cents,
                          MAX(net_chips) AS biggest_win
                   FROM poker_hand_players WHERE player_id=?""",
                (user_id,),
            ).fetchone()
        return {
            "total": row["total"],
            "summary": {
                "net_chips": row["net_chips"],
                "net_cash": row["net_cash_cents"] / 100,
                "biggest_win": {"net_chips": row["biggest_win"]}
                if row["biggest_win"] is not None and row["biggest_win"] > 0 else None,
            },
        }

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
