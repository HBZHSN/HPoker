"""Shared test isolation for process-global poker services."""

import pytest

from backend.app.services.room_manager import room_manager
from backend.app.services.balance_manager import balance_manager
from backend.app.services.user_manager import user_manager
from backend.app.services.timeout_manager import timeout_manager


@pytest.fixture(autouse=True)
def isolate_persisted_storage():
    """Keep test data out of production files (rooms, balance ledger, users)."""
    original_room_path = room_manager.storage_path
    original_rooms = room_manager._rooms

    original_bal_path = balance_manager.storage_path
    original_bal_entries = dict(balance_manager._entries)
    original_bal_batches = dict(balance_manager._batches)

    original_user_path = user_manager.storage_path
    original_users = dict(user_manager._users)
    original_tokens = dict(user_manager._tokens)

    room_manager.storage_path = ":memory:"
    room_manager._rooms = {}

    balance_manager.storage_path = ":memory:"
    balance_manager._entries = {}
    balance_manager._batches = {}

    user_manager.storage_path = ":memory:"
    user_manager._users = dict(original_users)
    user_manager._tokens = dict(original_tokens)

    yield

    for room_id in tuple(room_manager._rooms):
        timeout_manager.cancel_all_timers(room_id)

    room_manager._rooms = original_rooms
    room_manager.storage_path = original_room_path

    balance_manager.storage_path = original_bal_path
    balance_manager._entries = original_bal_entries
    balance_manager._batches = original_bal_batches

    user_manager.storage_path = original_user_path
    user_manager._users = original_users
    user_manager._tokens = original_tokens
