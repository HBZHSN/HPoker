"""SQLite schema, persistence, migration, and test-isolation tests."""

import json
from pathlib import Path
import sqlite3

import pytest

from backend.app.database import DEFAULT_DATABASE_PATH, SQLiteDatabase
from backend.app.models.room import RoomConfig
from backend.app.services.balance_manager import BalanceManager
from backend.app.services.room_manager import RoomManager
from backend.app.services.settlement import SettlementEngine
from backend.app.services.user_manager import UserManager


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TEST_DATABASE_PATH = DATA_DIR / "poker_test.sqlite3"
PRODUCTION_DATABASE_PATH = DATA_DIR / "poker.sqlite3"


EXPECTED_TABLES = {
    "schema_migrations",
    "data_migrations",
    "users",
    "auth_tokens",
    "rooms",
    "ledger_entries",
    "ledger_participants",
    "ledger_transactions",
    "settlement_batches",
    "settlement_batch_entries",
    "settlement_batch_users",
    "settlement_batch_transactions",
}


def test_schema_uses_normalized_tables_constraints_and_foreign_keys(tmp_path):
    database_path = tmp_path / "schema_test.sqlite3"
    database = SQLiteDatabase(str(database_path))

    with database.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        participant_foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(ledger_participants)"
        ).fetchall()
        participant_indexes = connection.execute(
            "PRAGMA index_list(ledger_participants)"
        ).fetchall()
        ledger_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(ledger_entries)")
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]

    assert EXPECTED_TABLES <= tables
    assert any(row["table"] == "ledger_entries" for row in participant_foreign_keys)
    assert any(
        row["name"] == "idx_ledger_participants_player_id"
        for row in participant_indexes
    )
    assert "cash_value_cents" in ledger_columns
    assert "payload_json" not in ledger_columns
    assert user_version == 1

    with pytest.raises(sqlite3.IntegrityError):
        with database.connection(write=True) as connection:
            connection.execute(
                """INSERT INTO users(
                       user_id, username, nickname, avatar, is_admin, is_test,
                       password_hash, created_at
                   ) VALUES ('invalid', 'invalid', 'invalid', 'x', 2, 0, 'x', 0)"""
            )


def test_test_environment_rejects_production_database_path():
    assert Path(DEFAULT_DATABASE_PATH) == PRODUCTION_DATABASE_PATH
    with pytest.raises(RuntimeError, match="production SQLite database"):
        SQLiteDatabase(str(PRODUCTION_DATABASE_PATH))


def test_global_services_use_only_dedicated_test_sqlite():
    assert TEST_DATABASE_PATH.exists()
    assert TEST_DATABASE_PATH != PRODUCTION_DATABASE_PATH

    with sqlite3.connect(TEST_DATABASE_PATH) as connection:
        stored_test_users = connection.execute(
            "SELECT username FROM users ORDER BY username"
        ).fetchall()
    assert stored_test_users == [("test1",), ("test2",), ("test3",)]


def test_user_data_persists_across_manager_instances(tmp_path):
    database_path = tmp_path / "users_persistence_test.sqlite3"
    first = UserManager(database_path=str(database_path))
    first.update_profile("u_test1", nickname="持久化昵称", avatar="♠")
    _, token = first.authenticate("test1", "123")

    restored = UserManager(database_path=str(database_path))
    assert restored.get_user("u_test1").nickname == "持久化昵称"
    assert restored.get_user_by_token(token).user_id == "u_test1"


def test_balance_data_persists_in_normalized_rows(tmp_path):
    database_path = tmp_path / "balance_persistence_test.sqlite3"
    user_manager = UserManager(database_path=str(database_path))
    manager = BalanceManager(database_path=str(database_path))
    report = SettlementEngine.calculate_room_settlement(
        room_id="sqlite-room",
        room_name="SQLite 测试桌",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=[
            {
                "player_id": "u_test1",
                "player_name": "test1",
                "total_buyin_chips": 1000,
                "final_chips": 1300,
            },
            {
                "player_id": "u_test2",
                "player_name": "test2",
                "total_buyin_chips": 1000,
                "final_chips": 700,
            },
        ],
    )
    entry = manager.record_settlement(report, u_mgr=user_manager)

    restored = BalanceManager(database_path=str(database_path))
    assert restored.get_user_records("u_test1")[0]["entry_id"] == entry.entry_id
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM ledger_participants").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM ledger_transactions").fetchone()[0] == 1


def test_legacy_json_is_migrated_once(tmp_path):
    database_path = tmp_path / "migration_test.sqlite3"
    legacy_users_path = tmp_path / "users.json"
    legacy_rooms_path = tmp_path / "rooms.json"
    legacy_balance_path = tmp_path / "balance_ledger.json"

    source_users = UserManager(database_path=str(tmp_path / "source_users.sqlite3"))
    user_payload = {
        "users": [user.to_storage_dict() for user in source_users._users.values()],
        "tokens": {},
    }
    legacy_users_path.write_text(
        json.dumps(user_payload, ensure_ascii=False), encoding="utf-8"
    )

    source_rooms = RoomManager(database_path=str(tmp_path / "source_rooms.sqlite3"))
    source_room = source_rooms.create_room(
        host_player_id="u_test1",
        config=RoomConfig(room_name="待迁移房间"),
        room_id="legacy-room",
    )
    legacy_rooms_path.write_text(
        json.dumps({"version": 1, "rooms": [source_room.to_checkpoint_dict()]}),
        encoding="utf-8",
    )

    source_balance = BalanceManager(
        database_path=str(tmp_path / "source_balance.sqlite3")
    )
    migration_report = SettlementEngine.calculate_room_settlement(
        room_id="legacy-ledger-room",
        room_name="历史账本",
        buyin_chips=100,
        cash_value=10.0,
        player_data_list=[
            {
                "player_id": "u_test1",
                "player_name": "test1",
                "total_buyin_chips": 100,
                "final_chips": 120,
            },
            {
                "player_id": "u_test2",
                "player_name": "test2",
                "total_buyin_chips": 100,
                "final_chips": 80,
            },
        ],
    )
    source_entry = source_balance.record_settlement(
        migration_report, u_mgr=source_users
    )
    legacy_balance_path.write_text(
        json.dumps(
            {"entries": [source_entry.to_dict()], "batches": []},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    migrated_users = UserManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_users_path),
    )
    migrated_rooms = RoomManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_rooms_path),
    )
    migrated_balance = BalanceManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_balance_path),
    )
    assert migrated_users.get_user("u_test1") is not None
    assert migrated_rooms.get_room("legacy-room") is not None
    assert migrated_balance.get_user_records("u_test1")[0]["room_id"] == "legacy-ledger-room"

    legacy_users_path.write_text("{broken", encoding="utf-8")
    legacy_rooms_path.write_text("{broken", encoding="utf-8")
    legacy_balance_path.write_text("{broken", encoding="utf-8")
    assert UserManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_users_path),
    ).get_user("u_test1") is not None
    assert RoomManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_rooms_path),
    ).get_room("legacy-room") is not None
    assert BalanceManager(
        database_path=str(database_path),
        legacy_storage_path=str(legacy_balance_path),
    ).get_user_records("u_test1")[0]["room_id"] == "legacy-ledger-room"
