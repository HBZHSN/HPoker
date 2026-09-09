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


@pytest.fixture
def funded_room_players(request):
    """Give legacy room scenarios actual prepaid funds through an admin deposit."""
    import ast
    source = Path(request.module.__file__).read_text()
    ids = {'real1', 'real2', 'real3', 'late-real'}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'sit_down_player':
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                ids.add(node.args[0].value)
    user_manager._users['funding_admin'] = User('funding_admin', 'funding_admin', 'Funding admin', '👤', is_admin=True)
    for uid in ids:
        if uid not in user_manager._users:
            user_manager._users[uid] = User(uid, uid, uid, '👤')
        user = user_manager._users[uid]
        if user.is_test_account or uid.startswith('bot_'):
            continue
        if balance_manager.available_cents(uid) < 1000000:
            balance_manager.admin_wallet_change(
                user_id=uid,
                amount='10000',
                kind='deposit',
                operator_id='funding_admin',
                request_id=f"fund:{uid}:{id(request)}",
            )
