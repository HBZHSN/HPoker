"""Unit and integration tests for table-level VPIP (Voluntarily Put in Pot) tracking."""

import pytest
from backend.app.engine.card import Card
from backend.app.engine.state_machine import (
    TableStateMachine,
    Street,
    ActionType,
    PlayerSeat,
)
from backend.app.models.room import Room, RoomConfig


def test_player_seat_vpip_calculation():
    """Verify vpip property returns rounded percentage or 0 when no hands played."""
    seat = PlayerSeat(
        player_id="p1",
        name="Alice",
        seat_index=0,
        chips=1000,
        hands_played=0,
        vpip_hands=0,
    )
    assert seat.vpip == 0

    data = seat.to_dict()
    assert data["vpip"] == 0
    assert data["vpip_hands"] == 0
    assert data["time_bank_cards"] == 3

    # 10 hands played, 3 entered voluntarily -> 30%
    seat.hands_played = 10
    seat.vpip_hands = 3
    assert seat.vpip == 30
    assert seat.to_dict()["vpip"] == 30

    # 3 hands played, 1 entered voluntarily -> 33% (rounded)
    seat.hands_played = 3
    seat.vpip_hands = 1
    assert seat.vpip == 33

    # 4 hands played, 3 entered voluntarily -> 75%
    seat.hands_played = 4
    seat.vpip_hands = 3
    assert seat.vpip == 75


def test_preflop_actions_set_vpip_this_hand():
    """Verify preflop calls, bets, raises, and all-ins mark vpip_this_hand, while checks and folds do not."""
    table = TableStateMachine(max_seats=6, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 1000) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True
    assert table.sit_down("p3", "Player 3", 2, 1000) is True

    # Hand 1: p1 is Dealer/SB, p2 is BB, p3 is UTG (first to act preflop)
    assert table.start_new_hand() is True
    assert table.street == Street.PREFLOP

    p1 = table.seats[0]
    p2 = table.seats[1]
    p3 = table.seats[2]

    # Blinds are posted automatically; neither SB nor BB has vpip_this_hand yet
    assert p1.vpip_this_hand is False
    assert p2.vpip_this_hand is False
    assert p3.vpip_this_hand is False

    # p1 is first to act (current_turn_seat)
    first_actor = table.seats[table.current_turn_seat]
    assert first_actor.player_id == "p1"
    assert table.handle_action("p1", ActionType.RAISE, 30) is True
    assert p1.vpip_this_hand is True

    # Next actor folds
    second_actor = table.seats[table.current_turn_seat]
    assert table.handle_action(second_actor.player_id, ActionType.FOLD) is True
    assert second_actor.vpip_this_hand is False

    # Third actor calls 30
    third_actor = table.seats[table.current_turn_seat]
    assert table.handle_action(third_actor.player_id, ActionType.CALL) is True
    assert third_actor.vpip_this_hand is True

    # Flop dealt
    assert table.street == Street.FLOP

    # End hand by having third actor check and first actor bet, third actor fold
    acting = table.seats[table.current_turn_seat]
    other = first_actor if acting.player_id != first_actor.player_id else third_actor
    assert table.handle_action(acting.player_id, ActionType.CHECK) is True
    assert table.handle_action(other.player_id, ActionType.BET, 10) is True
    assert table.handle_action(acting.player_id, ActionType.FOLD) is True
    assert table.street == Street.HAND_END

    # Check stats after Hand 1
    assert first_actor.hands_played == 1
    assert first_actor.vpip_hands == 1
    assert first_actor.vpip == 100

    assert second_actor.hands_played == 1
    assert second_actor.vpip_hands == 0
    assert second_actor.vpip == 0

    assert third_actor.hands_played == 1
    assert third_actor.vpip_hands == 1
    assert third_actor.vpip == 100


def test_bb_check_preflop_and_postflop_bet_is_not_vpip():
    """Verify BB checking preflop does not count as VPIP even if BB bets on flop."""
    table = TableStateMachine(max_seats=2, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 1000) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True

    # Heads up: dealer is p1 (SB), p2 is BB
    assert table.start_new_hand() is True
    p1 = table.seats[0]
    p2 = table.seats[1]

    # p1 (SB) limps (calls 5 to complete BB 10) -> voluntary preflop action
    assert table.handle_action("p1", ActionType.CALL) is True
    assert p1.vpip_this_hand is True

    # p2 (BB) checks option -> not voluntary money in pot
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert p2.vpip_this_hand is False

    # Flop dealt
    assert table.street == Street.FLOP

    # On flop, p2 bets -> postflop bet should NOT count as preflop VPIP
    assert table.handle_action("p2", ActionType.BET, 10) is True
    assert p2.vpip_this_hand is False

    # p1 folds -> hand ends
    assert table.handle_action("p1", ActionType.FOLD) is True
    assert table.street == Street.HAND_END

    assert p1.hands_played == 1
    assert p1.vpip_hands == 1
    assert p1.vpip == 100

    assert p2.hands_played == 1
    assert p2.vpip_hands == 0
    assert p2.vpip == 0


def test_allin_preflop_sets_vpip():
    """Verify going all-in preflop counts as VPIP."""
    table = TableStateMachine(max_seats=2, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 50) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True

    assert table.start_new_hand() is True
    p1 = table.seats[0]

    # p1 goes all in preflop
    assert table.handle_action("p1", ActionType.ALL_IN) is True
    assert p1.vpip_this_hand is True

    # p2 calls all in
    assert table.handle_action("p2", ActionType.CALL) is True
    assert table.seats[1].vpip_this_hand is True

    table.fast_forward_to_showdown()
    assert table.street == Street.HAND_END
    assert p1.hands_played == 1
    assert p1.vpip_hands == 1
    assert p1.vpip == 100


def test_aborted_hand_does_not_increment_vpip():
    """Verify refunding an unsettled hand does not increment vpip_hands or hands_played."""
    table = TableStateMachine(max_seats=2, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 1000) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True

    assert table.start_new_hand() is True
    assert table.handle_action("p1", ActionType.CALL) is True
    assert table.seats[0].vpip_this_hand is True

    # Abort
    table.refund_unsettled_hand()
    assert table.seats[0].hands_played == 0
    assert table.seats[0].vpip_hands == 0
    assert table.seats[0].vpip == 0


def test_room_checkpoint_and_standup_preserves_vpip():
    """Verify Room checkpoints and re-sitting preserve vpip_hands and hands_played."""
    from backend.app.services.room_manager import room_manager
    config = RoomConfig(small_blind=5, big_blind=10, buyin_chips=1000)
    room = room_manager.create_room(host_player_id="u_test1", config=config)

    assert room.sit_down_player("u_test1", "User 1", 0) is True
    assert room.sit_down_player("u_test2", "User 2", 1) is True

    p1 = room.table.seats[0]
    p1.hands_played = 20
    p1.vpip_hands = 5
    assert p1.vpip == 25

    # Checkpoint
    ckpt = room.to_checkpoint_dict()
    assert ckpt["table"]["seats"][0]["hands_played"] == 20
    assert ckpt["table"]["seats"][0]["vpip_hands"] == 5
    assert ckpt["table"]["seats"][0]["vpip"] == 25

    # Restore from checkpoint
    restored_room = Room.from_checkpoint_dict(ckpt)
    restored_p1 = restored_room.table.seats[0]
    assert restored_p1.hands_played == 20
    assert restored_p1.vpip_hands == 5
    assert restored_p1.vpip == 25

    # Stand up and re-sit preserves historical vpip_hands
    room.stand_up_player(0)
    assert room.historical_players["u_test1"]["hands_played"] == 20
    assert room.historical_players["u_test1"]["vpip_hands"] == 5

    assert room.sit_down_player("u_test1", "User 1", 2) is True
    new_seat = room.table.seats[2]
    assert new_seat.hands_played == 20
    assert new_seat.vpip_hands == 5
    assert new_seat.vpip == 25


def test_get_table_state_includes_vpip_and_time_bank_cards():
    """Verify get_table_state serializes vpip, vpip_hands, and time_bank_cards for each seat."""
    table = TableStateMachine(max_seats=2, small_blind=5, big_blind=10)
    assert table.sit_down("p1", "Player 1", 0, 1000) is True
    assert table.sit_down("p2", "Player 2", 1, 1000) is True

    p1 = table.seats[0]
    p1.hands_played = 10
    p1.vpip_hands = 4
    p1.time_bank_cards = 2

    state = table.get_table_state(viewer_player_id="p1")
    seat0 = state["seats"][0]
    assert seat0["vpip"] == 40
    assert seat0["vpip_hands"] == 4
    assert seat0["time_bank_cards"] == 2
    assert seat0["hands_played"] == 10

    seat1 = state["seats"][1]
    assert seat1["vpip"] == 0
    assert seat1["vpip_hands"] == 0
    assert seat1["time_bank_cards"] == 3
