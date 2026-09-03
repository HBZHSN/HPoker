"""Shared test isolation for process-global poker services."""

import pytest

from backend.app.services.room_manager import room_manager
from backend.app.services.timeout_manager import timeout_manager


@pytest.fixture(autouse=True)
def isolate_persisted_rooms():
    """Keep test rooms out of the production room checkpoint file."""
    original_storage_path = room_manager.storage_path
    original_rooms = room_manager._rooms
    room_manager.storage_path = ":memory:"
    room_manager._rooms = {}

    yield

    for room_id in tuple(room_manager._rooms):
        timeout_manager.cancel_all_timers(room_id)
    room_manager._rooms = original_rooms
    room_manager.storage_path = original_storage_path
