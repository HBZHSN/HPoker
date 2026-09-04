"""Disconnect grace period, automatic cash-out, and empty-room cleanup."""

import asyncio

import pytest

from backend.app.engine.state_machine import Street
from backend.app.models.room import RoomConfig
from backend.app.services.balance_manager import balance_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.timeout_manager import TimeoutManager
from backend.app.websocket.router import handle_disconnected_player_timeout


@pytest.mark.asyncio
async def test_disconnect_timeout_scheduler_can_be_cancelled_on_reconnect():
    manager = TimeoutManager()
    called = []

    async def callback(room_id, user_id):
        called.append((room_id, user_id))

    manager.schedule_disconnect_timeout("room", "user", 0.01, callback)
    manager.cancel_disconnect_timeout("room", "user")
    await asyncio.sleep(0.03)
    assert called == []


@pytest.mark.asyncio
async def test_disconnect_timeout_cashes_out_last_player_and_deletes_room():
    room = room_manager.create_room(
        host_player_id="offline_host",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="offline-room",
    )
    assert room.sit_down_player("offline_host", "Alice", 0, is_test=False)
    room.table.seats[0].chips = 120

    await handle_disconnected_player_timeout(room.room_id, "offline_host")

    assert room_manager.get_room(room.room_id) is None
    balances = balance_manager.get_user_balances()
    assert [(item.user_id, item.net_cash) for item in balances] == [
        ("offline_host", 2.0)
    ]


@pytest.mark.asyncio
async def test_all_in_disconnect_waits_for_hand_end_before_cashout():
    room = room_manager.create_room(
        host_player_id="allin_host",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="allin-offline",
    )
    assert room.sit_down_player("allin_host", "Alice", 0, is_test=False)
    assert room.sit_down_player("allin_guest", "Bob", 1, is_test=False)
    assert room.table.start_new_hand()
    room.table.seats[0].is_all_in = True

    await handle_disconnected_player_timeout(room.room_id, "allin_host")
    assert "allin_host" in room.pending_auto_leave_ids
    assert room.table.seats[0] is not None

    room.table.street = Street.HAND_END
    departed = room.process_pending_auto_leaves()
    assert len(departed) == 1
    assert room.table.seats[0] is None
    assert "allin_host" not in room.pending_auto_leave_ids
