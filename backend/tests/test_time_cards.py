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
        player_id="u_test1",
        name="test1",
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
    assert state["turn_started_at"] is not None


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
    room = room_manager.create_room(host_player_id="u_test1", config=config)
    room.sit_down_player("u_test1", "test1", 0)
    room.sit_down_player("u_test2", "test2", 1)

    assert room.table.start_new_hand() is True
    turn_seat = room.table.current_turn_seat
    curr_player = room.table.seats[turn_seat]
    assert curr_player.time_bank_cards == 3
    initial_turn_started_at = room.table.turn_started_at

    # Turn timer fires after 1s
    await trigger_room_turn_timer(room.room_id)
    await asyncio.sleep(1.2)

    # First time card consumed (3 -> 2), granted 30s
    assert curr_player.time_bank_cards == 2
    assert room.table.is_using_time_bank is True
    assert room.table.current_turn_seat == turn_seat
    assert room.table.turn_started_at > initial_turn_started_at

    timeout_manager.cancel_all_timers(room.room_id)


def test_player_earns_time_card_every_15_hands():
    """Verify that playing 15 hands rewards 1 time card up to the cap."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 10000) is True
    assert table.sit_down("p2", "Player 2", 1, 10000) is True

    p1 = table.seats[0]
    p2 = table.seats[1]
    assert p1.time_bank_cards == 3
    assert p1.hands_played == 0
    assert p2.time_bank_cards == 3
    assert p2.hands_played == 0

    # Play 14 hands
    for i in range(14):
        assert table.start_new_hand() is True
        # Current turn player folds to quickly finish hand
        curr_turn = table.seats[table.current_turn_seat]
        assert table.handle_action(curr_turn.player_id, "FOLD") is True
        assert table.street == Street.HAND_END
        assert p1.hands_played == i + 1
        assert p2.hands_played == i + 1
        assert p1.time_bank_cards == 3
        assert p2.time_bank_cards == 3
        assert len(table.time_card_rewarded_players) == 0

    # Play the 15th hand
    assert table.start_new_hand() is True
    curr_turn = table.seats[table.current_turn_seat]
    assert table.handle_action(curr_turn.player_id, "FOLD") is True
    assert table.street == Street.HAND_END

    # Both players played 15 hands -> both earn +1 time card (3 -> 4)
    assert p1.hands_played == 15
    assert p2.hands_played == 15
    assert p1.time_bank_cards == 4
    assert p2.time_bank_cards == 4
    assert set(table.time_card_rewarded_players) == {"p1", "p2"}

    # Starting 16th hand clears time_card_rewarded_players
    assert table.start_new_hand() is True
    assert len(table.time_card_rewarded_players) == 0
    curr_turn = table.seats[table.current_turn_seat]
    assert table.handle_action(curr_turn.player_id, "FOLD") is True

    # Fast forward through hand 30
    for _ in range(14):
        assert table.start_new_hand() is True
        curr_turn = table.seats[table.current_turn_seat]
        assert table.handle_action(curr_turn.player_id, "FOLD") is True

    assert p1.hands_played == 30
    assert p1.time_bank_cards == 5  # 4 -> 5 at hand 30
    assert p2.hands_played == 30
    assert p2.time_bank_cards == 5


def test_hands_played_cap_at_max_time_cards():
    """Verify time cards don't exceed max_time_cards (5) when earning at 15 hands."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10)
    table.sit_down("p1", "Player 1", 0, 10000, time_bank_cards=5)
    table.sit_down("p2", "Player 2", 1, 10000, time_bank_cards=5)

    p1 = table.seats[0]
    p2 = table.seats[1]
    assert p1.time_bank_cards == 5

    # Play 15 hands
    for _ in range(15):
        assert table.start_new_hand() is True
        curr_turn = table.seats[table.current_turn_seat]
        assert table.handle_action(curr_turn.player_id, "FOLD") is True

    assert p1.hands_played == 15
    assert p1.time_bank_cards == 5  # Capped at 5
    assert p2.time_bank_cards == 5
    assert len(table.time_card_rewarded_players) == 0  # Neither added because already maxed


def test_folded_player_gets_hand_credit_sitting_out_does_not():
    """Verify folding counts as playing the hand, but sitting out does not."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10)
    table.sit_down("p1", "Player 1", 0, 10000)
    table.sit_down("p2", "Player 2", 1, 10000)
    table.sit_down("p3", "Player 3", 2, 10000)

    p1 = table.seats[0]
    p2 = table.seats[1]
    p3 = table.seats[2]

    # p3 sits out
    p3.is_sitting_out = True

    assert table.start_new_hand() is True
    # p1 and p2 have cards, p3 does not
    assert len(p1.hole_cards) == 2
    assert len(p2.hole_cards) == 2
    assert len(p3.hole_cards) == 0

    curr_turn = table.seats[table.current_turn_seat]
    table.handle_action(curr_turn.player_id, "FOLD")
    assert table.street == Street.HAND_END

    # p1 and p2 played 1 hand, p3 played 0
    assert p1.hands_played == 1
    assert p2.hands_played == 1
    assert p3.hands_played == 0


def test_aborted_hand_does_not_increment_hands_played():
    """Verify aborting a hand does not count towards hands played."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10)
    table.sit_down("p1", "Player 1", 0, 10000)
    table.sit_down("p2", "Player 2", 1, 10000)

    assert table.start_new_hand() is True
    table.refund_unsettled_hand()
    assert table.street == Street.HAND_END

    p1 = table.seats[0]
    p2 = table.seats[1]
    assert p1.hands_played == 0
    assert p2.hands_played == 0


def test_room_checkpoint_and_sit_down_preserves_hands_played():
    """Verify Room checkpoints and re-sitting preserve hands_played and time_bank_cards."""
    config = RoomConfig(
        room_name="Hands Played Room",
        buyin_chips=1000,
        cash_value=100.0,
        small_blind=5,
        max_seats=6
    )
    room = room_manager.create_room(host_player_id="u_test1", config=config)
    room.sit_down_player("u_test1", "test1", 0)
    room.sit_down_player("u_test2", "test2", 1)

    p1 = room.table.seats[0]
    p1.hands_played = 14
    p1.time_bank_cards = 3

    # Checkpoint serialization and deserialization
    ckpt = room.to_checkpoint_dict()
    assert ckpt["table"]["seats"][0]["hands_played"] == 14
    assert ckpt["table"]["seats"][0]["time_bank_cards"] == 3

    restored_room = Room.from_checkpoint_dict(ckpt)
    restored_p1 = restored_room.table.seats[0]
    assert restored_p1.hands_played == 14
    assert restored_p1.time_bank_cards == 3

    # Stand up and re-sit preserves historical hands_played
    room.stand_up_player(0)
    assert "u_test1" in room.historical_players
    assert room.historical_players["u_test1"]["hands_played"] == 14

    # Re-sit
    assert room.sit_down_player("u_test1", "test1", 2) is True
    new_seat = room.table.seats[2]
    assert new_seat.hands_played == 14
    assert new_seat.time_bank_cards == 3

