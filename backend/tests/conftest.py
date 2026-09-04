"""Shared pytest isolation backed by a dedicated SQLite database."""

import os
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TEST_DATABASE_PATH = DATA_DIR / "poker_test.sqlite3"
PRODUCTION_DATABASE_PATH = DATA_DIR / "poker.sqlite3"

# These variables must be set before any application service singleton is
# imported.  The database gateway also rejects the production path whenever
# POKER_ENV=test, so a future fixture regression fails closed.
os.environ["POKER_ENV"] = "test"
os.environ["POKER_DATABASE_PATH"] = str(TEST_DATABASE_PATH)

# Start every pytest process with a clean, dedicated on-disk SQLite database.
# WAL sidecars are named deterministically from this exact test-only path.
for database_file in (
    TEST_DATABASE_PATH,
    Path(f"{TEST_DATABASE_PATH}-wal"),
    Path(f"{TEST_DATABASE_PATH}-shm"),
):
    database_file.unlink(missing_ok=True)

import pytest

from backend.app.models.user import User, hash_password
from backend.app.services.balance_manager import balance_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.hand_history_manager import hand_history_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.services.user_manager import user_manager


def _dedicated_test_users() -> dict[str, User]:
    return {
        "u_test1": User(
            user_id="u_test1",
            username="test1",
            nickname="test1",
            avatar="🧪",
            is_test=True,
            password_hash=hash_password("123"),
        ),
        "u_test2": User(
            user_id="u_test2",
            username="test2",
            nickname="test2",
            avatar="🧪",
            is_test=True,
            password_hash=hash_password("123"),
        ),
        "u_test3": User(
            user_id="u_test3",
            username="test3",
            nickname="test3",
            avatar="🧪",
            is_test=True,
            password_hash=hash_password("123"),
        ),
    }


def _reset_test_database_state() -> None:
    room_manager._rooms = {}
    room_manager.save_to_storage()

    balance_manager._entries = {}
    balance_manager._batches = {}
    balance_manager.save_to_storage()
    hand_history_manager.clear_all()

    user_manager._users = _dedicated_test_users()
    user_manager._tokens = {}
    user_manager.save_to_storage()


@pytest.fixture(autouse=True)
def isolate_persisted_storage():
    """Reset every global service table before and after each test."""
    configured_paths = {
        room_manager.storage_path,
        balance_manager.storage_path,
        user_manager.storage_path,
    }
    assert configured_paths == {str(TEST_DATABASE_PATH)}
    assert str(PRODUCTION_DATABASE_PATH) not in configured_paths

    _reset_test_database_state()
    yield

    for room_id in tuple(room_manager._rooms):
        timeout_manager.cancel_all_timers(room_id)
    _reset_test_database_state()
