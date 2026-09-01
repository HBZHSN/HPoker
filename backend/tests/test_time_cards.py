"""Unit and Integration Tests for Texas Hold'em Time Card (时间卡) Mechanism."""

import pytest
import asyncio
from fastapi.testclient import TestClient

from backend.main import app
from backend.app.engine.state_machine import TableStateMachine, Street, PlayerSeat
from backend.app.models.room import Room, RoomConfig
from backend.app.services.room_manager import room_manager
from backend.app.services.timeout_manager import timeout_manager
from backend.app.websocket.router import trigger_room_turn_timer


def test_player_seat_time_cards_defaults():
    """Verify player starts with 3 time cards and has max cap of 5."""
    seat = PlayerSeat(
        player_id="u_test",
        name="Tester",
        seat_index=0,
        chips=1000
    )
    assert seat.time_bank_cards == 3
    data = seat.to_dict()
    assert data["time_bank_cards"] == 3

    # Add time cards up to max 5
    assert seat.add_time_bank_card(1) is True
    assert seat.time_bank_cards == 4

    assert seat.add_time_bank_card(1) is True
    assert seat.time_bank_cards == 5

    # Cannot exceed 5
    assert seat.add_time_bank_card(1) is False
    assert seat.time_bank_cards == 5

    # Use time cards
    assert seat.use_time_bank_card() is True
    assert seat.time_bank_cards == 4


def test_table_sit_down_and_periodic_replenish():
    """Verify sitting down gives 3 time cards, and periodic replenish adds 1 up to 5."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10, action_timeout=15)
    assert table.sit_down("p1", "Player 1", 0, 1000) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True

    p1 = table.seats[0]
    p2 = table.seats[1]
    assert p1.time_bank_cards == 3
    assert p2.time_bank_cards == 3

    # Periodic replenishment
    added = table.add_periodic_time_cards(max_cards=5)
    assert added == 2
    assert p1.time_bank_cards == 4
    assert p2.time_bank_cards == 4

    # Another replenishment
    added = table.add_periodic_time_cards(max_cards=5)
    assert added == 2
    assert p1.time_bank_cards == 5
    assert p2.time_bank_cards == 5

    # Capped at 5
    added = table.add_periodic_time_cards(max_cards=5)
    assert added == 0
    assert p1.time_bank_cards == 5
    assert p2.time_bank_cards == 5


def test_manual_use_time_bank_card_on_table():
    """Verify manual use of time bank card by active player."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10, action_timeout=15)
    table.sit_down("p1", "Player 1", 0, 1000)
    table.sit_down("p2", "Player 2", 1, 1000)

    assert table.start_new_hand() is True
    turn_seat = table.current_turn_seat
    assert turn_seat is not None
    current_p = table.seats[turn_seat]
    assert current_p.time_bank_cards == 3
    assert table.is_using_time_bank is False
    assert table.current_turn_duration == 15

    # Active player uses time card
    ok = table.use_time_bank_for_current_player()
    assert ok is True
    assert current_p.time_bank_cards == 2
    assert table.is_using_time_bank is True
    assert table.current_turn_duration == 30

    state = table.get_table_state(current_p.player_id)
    assert state["is_using_time_bank"] is True
    assert state["current_turn_duration"] == 30


@pytest.mark.asyncio
async def test_time_card_auto_consumption_sequence():
    """Test that time cards auto-consume on timeout sequentially before folding."""
    config = RoomConfig(
        room_name="Auto Time Card Room",
        buyin_chips=1000,
        cash_value=100.0,
        small_blind=5,
        big_blind=10,
        action_timeout=1,
        max_seats=6
    )
    room = room_manager.create_room(host_player_id="u_tom", config=config)
    room.sit_down_player("u_tom", "Tom Dwan", 0)
    room.sit_down_player("u_ivey", "Phil Ivey", 1)

    assert room.table.start_new_hand() is True
    turn_seat = room.table.current_turn_seat
    curr_player = room.table.seats[turn_seat]
    assert curr_player.time_bank_cards == 3

    # Turn timer fires after 1s
    await trigger_room_turn_timer(room.room_id)
    await asyncio.sleep(1.2)

    # First time card consumed (3 -> 2), granted 30s
    assert curr_player.time_bank_cards == 2
    assert room.table.is_using_time_bank is True
    assert room.table.current_turn_seat == turn_seat

    timeout_manager.cancel_all_timers(room.room_id)
