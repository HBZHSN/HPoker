"""SQLite persistence shared by backend services.

The application uses one database file for users, authentication tokens, active
room checkpoints, ledger entries, and settlement batches.  Each service keeps
its existing in-process cache, while this module provides atomic durable
snapshots and a single configuration boundary for production/test isolation.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Iterator, Optional, Sequence


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = str(BACKEND_DIR / "data" / "poker.sqlite3")
DATABASE_PATH_ENV = "POKER_DATABASE_PATH"
ENVIRONMENT_ENV = "POKER_ENV"


def resolve_database_path(database_path: Optional[str] = None) -> str:
    """Resolve the configured database and reject production writes in tests."""
    resolved = database_path or os.environ.get(DATABASE_PATH_ENV, DEFAULT_DATABASE_PATH)
    if resolved != ":memory:":
        resolved = os.path.realpath(os.path.abspath(resolved))

    if os.environ.get(ENVIRONMENT_ENV, "").lower() == "test":
        production_path = os.path.realpath(os.path.abspath(DEFAULT_DATABASE_PATH))
        if resolved == production_path:
            raise RuntimeError(
                "Test environment cannot use the production SQLite database; "
                f"set {DATABASE_PATH_ENV} to a dedicated test database"
            )
    return resolved


class SQLiteDatabase:
    """Small thread-safe SQLite gateway with explicit transactional writes."""

    def __init__(self, database_path: Optional[str] = None):
        self.path = resolve_database_path(database_path)
        self._lock = threading.RLock()
        self._memory_connection: Optional[sqlite3.Connection] = None

        if self.path == ":memory:":
            self._memory_connection = self._new_connection()
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        if self.path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        """Yield a connection and commit/rollback writes as one transaction."""
        with self._lock:
            connection = self._memory_connection or self._new_connection()
            try:
                if write:
                    connection.execute("BEGIN IMMEDIATE")
                yield connection
                if write:
                    connection.commit()
            except Exception:
                if write:
                    connection.rollback()
                raise
            finally:
                if self._memory_connection is None:
                    connection.close()

    def _initialize_schema(self) -> None:
        with self.connection(write=True) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY CHECK (version > 0),
                    applied_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_migrations (
                    name TEXT PRIMARY KEY,
                    applied_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    nickname TEXT NOT NULL,
                    avatar TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
                    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0, 1)),
                    password_hash TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS rooms (
                    room_id TEXT PRIMARY KEY,
                    host_player_id TEXT NOT NULL,
                    room_name TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rooms_host_player_id
                    ON rooms(host_player_id);

                CREATE TABLE IF NOT EXISTS ledger_entries (
                    entry_id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    room_name TEXT NOT NULL,
                    settlement_type TEXT NOT NULL
                        CHECK (settlement_type IN ('balance', 'immediate')),
                    status TEXT NOT NULL CHECK (status IN ('unsettled', 'settled')),
                    created_at REAL NOT NULL,
                    is_test_game INTEGER NOT NULL DEFAULT 0
                        CHECK (is_test_game IN (0, 1)),
                    chip_to_cash_ratio REAL NOT NULL CHECK (chip_to_cash_ratio >= 0),
                    buyin_chips INTEGER NOT NULL CHECK (buyin_chips >= 0),
                    cash_value_cents INTEGER NOT NULL CHECK (cash_value_cents >= 0),
                    entry_kind TEXT NOT NULL DEFAULT 'settlement',
                    settled_at REAL,
                    settled_by TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_ledger_entries_status
                    ON ledger_entries(status, settlement_type, is_test_game);
                CREATE INDEX IF NOT EXISTS idx_ledger_entries_room_id
                    ON ledger_entries(room_id);

                CREATE TABLE IF NOT EXISTS ledger_participants (
                    entry_id TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    player_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    nickname TEXT NOT NULL,
                    avatar TEXT NOT NULL,
                    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0, 1)),
                    rebuy_count INTEGER NOT NULL CHECK (rebuy_count >= 0),
                    total_buyin_chips INTEGER NOT NULL CHECK (total_buyin_chips >= 0),
                    final_chips INTEGER NOT NULL CHECK (final_chips >= 0),
                    net_chips INTEGER NOT NULL,
                    net_cash_cents INTEGER NOT NULL,
                    PRIMARY KEY (entry_id, position),
                    UNIQUE (entry_id, player_id),
                    FOREIGN KEY (entry_id) REFERENCES ledger_entries(entry_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ledger_participants_player_id
                    ON ledger_participants(player_id, entry_id);

                CREATE TABLE IF NOT EXISTS ledger_transactions (
                    entry_id TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    from_player_id TEXT NOT NULL,
                    from_player_name TEXT NOT NULL,
                    to_player_id TEXT NOT NULL,
                    to_player_name TEXT NOT NULL,
                    amount_cash_cents INTEGER NOT NULL CHECK (amount_cash_cents >= 0),
                    amount_chips INTEGER NOT NULL CHECK (amount_chips >= 0),
                    display_text TEXT NOT NULL,
                    PRIMARY KEY (entry_id, position),
                    FOREIGN KEY (entry_id) REFERENCES ledger_entries(entry_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settlement_batches (
                    batch_id TEXT PRIMARY KEY,
                    created_at REAL NOT NULL,
                    operator_id TEXT NOT NULL,
                    operator_name TEXT NOT NULL,
                    total_transferred_cash_cents INTEGER NOT NULL
                        CHECK (total_transferred_cash_cents >= 0)
                );

                CREATE TABLE IF NOT EXISTS settlement_batch_entries (
                    batch_id TEXT NOT NULL,
                    entry_id TEXT NOT NULL UNIQUE,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    PRIMARY KEY (batch_id, position),
                    FOREIGN KEY (batch_id) REFERENCES settlement_batches(batch_id) ON DELETE CASCADE,
                    FOREIGN KEY (entry_id) REFERENCES ledger_entries(entry_id) ON DELETE RESTRICT
                );

                CREATE TABLE IF NOT EXISTS settlement_batch_users (
                    batch_id TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    user_id TEXT NOT NULL,
                    nickname TEXT NOT NULL,
                    avatar TEXT NOT NULL,
                    is_test INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0, 1)),
                    net_cash_cents INTEGER NOT NULL,
                    net_chips INTEGER NOT NULL,
                    unsettled_games_count INTEGER NOT NULL
                        CHECK (unsettled_games_count >= 0),
                    PRIMARY KEY (batch_id, position),
                    UNIQUE (batch_id, user_id),
                    FOREIGN KEY (batch_id) REFERENCES settlement_batches(batch_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settlement_batch_transactions (
                    batch_id TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    from_player_id TEXT NOT NULL,
                    from_player_name TEXT NOT NULL,
                    to_player_id TEXT NOT NULL,
                    to_player_name TEXT NOT NULL,
                    amount_cash_cents INTEGER NOT NULL CHECK (amount_cash_cents >= 0),
                    amount_chips INTEGER NOT NULL CHECK (amount_chips >= 0),
                    display_text TEXT NOT NULL,
                    PRIMARY KEY (batch_id, position),
                    FOREIGN KEY (batch_id) REFERENCES settlement_batches(batch_id) ON DELETE CASCADE
                );

                INSERT OR IGNORE INTO schema_migrations(version, applied_at)
                    VALUES (1, CAST(strftime('%s', 'now') AS REAL));
                """
            )
            ledger_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(ledger_entries)")
            }
            if "entry_kind" not in ledger_columns:
                connection.execute(
                    "ALTER TABLE ledger_entries "
                    "ADD COLUMN entry_kind TEXT NOT NULL DEFAULT 'settlement'"
                )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, time.time()),
            )
            connection.execute("PRAGMA user_version = 2")

    @staticmethod
    def _encode(payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def migration_applied(self, name: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM data_migrations WHERE name = ?", (name,)
            ).fetchone()
        return row is not None

    def mark_migration_applied(self, name: str) -> None:
        with self.connection(write=True) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO data_migrations(name, applied_at) VALUES (?, ?)",
                (name, time.time()),
            )

    def load_users(self) -> tuple[list[dict], dict[str, str]]:
        with self.connection() as connection:
            user_rows = connection.execute(
                """SELECT user_id, username, nickname, avatar, is_admin, is_test,
                          password_hash, created_at
                   FROM users ORDER BY created_at, user_id"""
            ).fetchall()
            token_rows = connection.execute(
                "SELECT token, user_id FROM auth_tokens"
            ).fetchall()
        users = [
            {
                **dict(row),
                "is_admin": bool(row["is_admin"]),
                "is_test": bool(row["is_test"]),
            }
            for row in user_rows
        ]
        return users, {row["token"]: row["user_id"] for row in token_rows}

    def replace_users(self, users: Sequence[dict], tokens: dict[str, str]) -> None:
        user_ids = {user["user_id"] for user in users}
        with self.connection(write=True) as connection:
            token_created_at = {
                row["token"]: row["created_at"]
                for row in connection.execute(
                    "SELECT token, created_at FROM auth_tokens"
                ).fetchall()
            }
            connection.execute("DELETE FROM auth_tokens")
            connection.execute("DELETE FROM users")
            connection.executemany(
                """INSERT INTO users(
                       user_id, username, nickname, avatar, is_admin, is_test,
                       password_hash, created_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        user["user_id"],
                        user["username"],
                        user.get("nickname", user["username"]),
                        user.get("avatar", "👤"),
                        int(bool(user.get("is_admin", False))),
                        int(bool(user.get("is_test", False))),
                        user["password_hash"],
                        float(user["created_at"]),
                    )
                    for user in users
                ],
            )
            connection.executemany(
                "INSERT INTO auth_tokens(token, user_id, created_at) VALUES (?, ?, ?)",
                [
                    (token, user_id, token_created_at.get(token, time.time()))
                    for token, user_id in tokens.items()
                    if user_id in user_ids
                ],
            )

    def load_rooms(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT checkpoint_json FROM rooms ORDER BY created_at, room_id"
            ).fetchall()
        return [json.loads(row["checkpoint_json"]) for row in rows]

    def replace_rooms(self, rooms: Sequence[dict]) -> None:
        now = time.time()
        with self.connection(write=True) as connection:
            connection.execute("DELETE FROM rooms")
            connection.executemany(
                """INSERT INTO rooms(
                       room_id, host_player_id, room_name, checkpoint_json,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        room["room_id"],
                        room["host_player_id"],
                        room.get("config", {}).get("room_name", "德州对局"),
                        self._encode(room),
                        float(room.get("created_at", now)),
                        now,
                    )
                    for room in rooms
                ],
            )

    def load_ledger(self) -> tuple[list[dict], list[dict]]:
        with self.connection() as connection:
            entry_rows = connection.execute(
                """SELECT entry_id, room_id, room_name, settlement_type, status,
                          created_at, is_test_game, chip_to_cash_ratio, buyin_chips,
                          cash_value_cents, entry_kind, settled_at, settled_by
                   FROM ledger_entries ORDER BY created_at, entry_id"""
            ).fetchall()
            participant_rows = connection.execute(
                """SELECT entry_id, player_id, username, nickname, avatar, is_test,
                          rebuy_count, total_buyin_chips, final_chips, net_chips,
                          net_cash_cents
                   FROM ledger_participants ORDER BY entry_id, position"""
            ).fetchall()
            transaction_rows = connection.execute(
                """SELECT entry_id, from_player_id, from_player_name, to_player_id,
                          to_player_name, amount_cash_cents, amount_chips, display_text
                   FROM ledger_transactions ORDER BY entry_id, position"""
            ).fetchall()
            batch_rows = connection.execute(
                """SELECT batch_id, created_at, operator_id, operator_name,
                          total_transferred_cash_cents
                   FROM settlement_batches ORDER BY created_at, batch_id"""
            ).fetchall()
            batch_entry_rows = connection.execute(
                """SELECT batch_id, entry_id
                   FROM settlement_batch_entries ORDER BY batch_id, position"""
            ).fetchall()
            batch_user_rows = connection.execute(
                """SELECT batch_id, user_id, nickname, avatar, is_test, net_cash_cents,
                          net_chips, unsettled_games_count
                   FROM settlement_batch_users ORDER BY batch_id, position"""
            ).fetchall()
            batch_transaction_rows = connection.execute(
                """SELECT batch_id, from_player_id, from_player_name, to_player_id,
                          to_player_name, amount_cash_cents, amount_chips, display_text
                   FROM settlement_batch_transactions ORDER BY batch_id, position"""
            ).fetchall()

        batch_by_entry = {
            row["entry_id"]: row["batch_id"] for row in batch_entry_rows
        }
        participants_by_entry: dict[str, list[dict]] = {}
        for row in participant_rows:
            participant = dict(row)
            entry_id = participant.pop("entry_id")
            participant["is_test"] = bool(participant["is_test"])
            participant["net_cash"] = participant.pop("net_cash_cents") / 100
            participants_by_entry.setdefault(entry_id, []).append(participant)
        transactions_by_entry: dict[str, list[dict]] = {}
        for row in transaction_rows:
            transaction = dict(row)
            entry_id = transaction.pop("entry_id")
            transaction["amount_cash"] = transaction.pop("amount_cash_cents") / 100
            transaction["display"] = transaction.pop("display_text")
            transactions_by_entry.setdefault(entry_id, []).append(transaction)

        entries = []
        for row in entry_rows:
            entry = dict(row)
            entry_id = entry["entry_id"]
            entry["is_test_game"] = bool(entry["is_test_game"])
            entry["cash_value"] = entry.pop("cash_value_cents") / 100
            entry["participants"] = participants_by_entry.get(entry_id, [])
            entry["transactions"] = transactions_by_entry.get(entry_id, [])
            entry["batch_id"] = batch_by_entry.get(entry_id)
            entries.append(entry)

        entry_ids_by_batch: dict[str, list[str]] = {}
        for row in batch_entry_rows:
            entry_ids_by_batch.setdefault(row["batch_id"], []).append(row["entry_id"])
        users_by_batch: dict[str, list[dict]] = {}
        for row in batch_user_rows:
            user = dict(row)
            batch_id = user.pop("batch_id")
            user["is_test"] = bool(user["is_test"])
            user["net_cash"] = user.pop("net_cash_cents") / 100
            users_by_batch.setdefault(batch_id, []).append(user)
        transactions_by_batch: dict[str, list[dict]] = {}
        for row in batch_transaction_rows:
            transaction = dict(row)
            batch_id = transaction.pop("batch_id")
            transaction["amount_cash"] = transaction.pop("amount_cash_cents") / 100
            transaction["display"] = transaction.pop("display_text")
            transactions_by_batch.setdefault(batch_id, []).append(transaction)

        batches = []
        for row in batch_rows:
            batch = dict(row)
            batch_id = batch["batch_id"]
            batch["total_transferred_cash"] = (
                batch.pop("total_transferred_cash_cents") / 100
            )
            batch["user_summaries"] = users_by_batch.get(batch_id, [])
            batch["transactions"] = transactions_by_batch.get(batch_id, [])
            batch["entry_ids"] = entry_ids_by_batch.get(batch_id, [])
            batches.append(batch)
        return entries, batches

    def replace_ledger(self, entries: Sequence[dict], batches: Sequence[dict]) -> None:
        with self.connection(write=True) as connection:
            connection.execute("DELETE FROM settlement_batch_entries")
            connection.execute("DELETE FROM settlement_batch_users")
            connection.execute("DELETE FROM settlement_batch_transactions")
            connection.execute("DELETE FROM ledger_participants")
            connection.execute("DELETE FROM ledger_transactions")
            connection.execute("DELETE FROM ledger_entries")
            connection.execute("DELETE FROM settlement_batches")
            connection.executemany(
                """INSERT INTO ledger_entries(
                       entry_id, room_id, room_name, settlement_type, status,
                       created_at, is_test_game, chip_to_cash_ratio, buyin_chips,
                       cash_value_cents, entry_kind, settled_at, settled_by
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        entry["entry_id"],
                        entry["room_id"],
                        entry.get("room_name", "德州对局"),
                        entry["settlement_type"],
                        entry["status"],
                        float(entry["created_at"]),
                        int(bool(entry.get("is_test_game", False))),
                        float(entry.get("chip_to_cash_ratio", 0.1)),
                        int(entry.get("buyin_chips", 0)),
                        int(round(float(entry.get("cash_value", 0.0)) * 100)),
                        entry.get("entry_kind", "settlement"),
                        entry.get("settled_at"),
                        entry.get("settled_by"),
                    )
                    for entry in entries
                ],
            )
            connection.executemany(
                """INSERT INTO ledger_participants(
                       entry_id, position, player_id, username, nickname, avatar,
                       is_test, rebuy_count, total_buyin_chips, final_chips,
                       net_chips, net_cash_cents
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        entry["entry_id"],
                        position,
                        participant["player_id"],
                        participant.get("username", participant["player_id"]),
                        participant.get("nickname", participant["player_id"]),
                        participant.get("avatar", "👤"),
                        int(bool(participant.get("is_test", False))),
                        int(participant.get("rebuy_count", 1)),
                        int(participant.get("total_buyin_chips", 0)),
                        int(participant.get("final_chips", 0)),
                        int(participant.get("net_chips", 0)),
                        int(round(float(participant.get("net_cash", 0.0)) * 100)),
                    )
                    for entry in entries
                    for position, participant in enumerate(entry.get("participants", []))
                ],
            )
            connection.executemany(
                """INSERT INTO ledger_transactions(
                       entry_id, position, from_player_id, from_player_name,
                       to_player_id, to_player_name, amount_cash_cents, amount_chips,
                       display_text
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        entry["entry_id"],
                        position,
                        transaction["from_player_id"],
                        transaction["from_player_name"],
                        transaction["to_player_id"],
                        transaction["to_player_name"],
                        int(round(float(transaction["amount_cash"]) * 100)),
                        int(transaction["amount_chips"]),
                        transaction.get("display", ""),
                    )
                    for entry in entries
                    for position, transaction in enumerate(entry.get("transactions", []))
                ],
            )
            connection.executemany(
                """INSERT INTO settlement_batches(
                       batch_id, created_at, operator_id, operator_name,
                       total_transferred_cash_cents
                   ) VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        batch["batch_id"],
                        float(batch["created_at"]),
                        batch.get("operator_id", "admin"),
                        batch.get("operator_name", "管理员"),
                        int(round(float(batch.get("total_transferred_cash", 0.0)) * 100)),
                    )
                    for batch in batches
                ],
            )
            connection.executemany(
                """INSERT INTO settlement_batch_entries(
                       batch_id, entry_id, position
                   ) VALUES (?, ?, ?)""",
                [
                    (batch["batch_id"], entry_id, position)
                    for batch in batches
                    for position, entry_id in enumerate(batch.get("entry_ids", []))
                ],
            )
            connection.executemany(
                """INSERT INTO settlement_batch_users(
                       batch_id, position, user_id, nickname, avatar, is_test,
                       net_cash_cents, net_chips, unsettled_games_count
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        batch["batch_id"],
                        position,
                        user["user_id"],
                        user.get("nickname", user["user_id"]),
                        user.get("avatar", "👤"),
                        int(bool(user.get("is_test", False))),
                        int(round(float(user.get("net_cash", 0.0)) * 100)),
                        int(user.get("net_chips", 0)),
                        int(user.get("unsettled_games_count", 0)),
                    )
                    for batch in batches
                    for position, user in enumerate(batch.get("user_summaries", []))
                ],
            )
            connection.executemany(
                """INSERT INTO settlement_batch_transactions(
                       batch_id, position, from_player_id, from_player_name,
                       to_player_id, to_player_name, amount_cash_cents, amount_chips,
                       display_text
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        batch["batch_id"],
                        position,
                        transaction["from_player_id"],
                        transaction["from_player_name"],
                        transaction["to_player_id"],
                        transaction["to_player_name"],
                        int(round(float(transaction["amount_cash"]) * 100)),
                        int(transaction["amount_chips"]),
                        transaction.get("display", ""),
                    )
                    for batch in batches
                    for position, transaction in enumerate(batch.get("transactions", []))
                ],
            )
