import pytest
from backend.app.engine.state_machine import TableStateMachine, Street, ActionType


def test_sit_down_and_stand_up():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    assert table.sit_down("p1", "Alice", seat_index=0, chips=100) is True
    assert table.sit_down("p2", "Bob", seat_index=1, chips=100) is True

    # Cannot sit on occupied seat
    assert table.sit_down("p3", "Charlie", seat_index=0, chips=100) is False
    # Cannot sit twice
    assert table.sit_down("p1", "Alice", seat_index=2, chips=100) is False

    assert len(table.active_seated_players) == 2

    # Stand up
    player = table.stand_up(0)
    assert player is not None
    assert player.name == "Alice"
    assert len(table.active_seated_players) == 1


def test_two_player_heads_up_flow():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    # Start hand
    assert table.start_new_hand() is True
    assert table.street == Street.PREFLOP
    assert table.hand_number == 1

    # In Heads-up: Dealer is SB (seat 0), other is BB (seat 1)
    assert table.dealer_seat == 0
    assert table.sb_seat == 0
    assert table.bb_seat == 1

    # Chips after blinds: p1 has 99, p2 has 98
    assert table.seats[0].chips == 99
    assert table.seats[1].chips == 98
    assert table.pot_manager.total_pot_amount == 3

    # Preflop: Action starts on SB (p1) in heads-up
    assert table.current_turn_seat == 0
    legal_p1 = table.get_legal_actions("p1")
    assert legal_p1.can_call is True
    assert legal_p1.call_amount == 1
    assert legal_p1.can_raise is True

    # P1 calls (limps to 2)
    assert table.handle_action("p1", ActionType.CALL) is True
    assert table.seats[0].chips == 98
    assert table.pot_manager.total_pot_amount == 4

    # Now turn is on BB (p2)
    assert table.current_turn_seat == 1
    legal_p2 = table.get_legal_actions("p2")
    assert legal_p2.can_check is True

    # P2 checks -> Round ends -> Deal Flop
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.street == Street.FLOP
    assert len(table.board_cards) == 3

    # Flop: Postflop action starts with BB in heads-up (seat 1)
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.CHECK) is True

    # Deal Turn
    assert table.street == Street.TURN
    assert len(table.board_cards) == 4

    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.handle_action("p1", ActionType.CHECK) is True

    # Deal River
    assert table.street == Street.RIVER
    assert len(table.board_cards) == 5

    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.handle_action("p1", ActionType.CHECK) is True

    # Showdown & Hand End
    assert table.street == Street.HAND_END
    assert len(table.payouts) >= 1
    # Total chips in game must remain conserved (100 + 100 = 200)
    total_chips = sum(p.chips for p in table.active_seated_players)
    assert total_chips == 200


def test_uncontested_fold_win():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # P1 raises to 10
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=10) is True
    assert table.seats[0].chips == 90

    # P2 folds
    assert table.handle_action("p2", ActionType.FOLD) is True
    assert table.street == Street.HAND_END

    # Alice should win uncontested (original 100 + Bob's 2 BB = 102)
    assert table.seats[0].chips == 102
    assert table.seats[1].chips == 98
    assert table.payouts[0].player_id == "p1"


def test_allin_fast_forward():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=50)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # P1 goes all-in
    assert table.handle_action("p1", ActionType.ALL_IN) is True
    # P2 calls
    assert table.handle_action("p2", ActionType.CALL) is True

    # Fast forward: all 5 board cards dealt and reached HAND_END
    assert table.street == Street.HAND_END
    assert len(table.board_cards) == 5
    assert sum(p.chips for p in table.active_seated_players) == 150


def test_show_card_feature():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    table.handle_action("p1", ActionType.RAISE, raise_total_amount=10)
    table.handle_action("p2", ActionType.FOLD)

    # Show single card 0
    assert table.show_card("p1", card_index=0) is True
    assert len(table.seats[0].shown_cards) == 1

    # Show all cards
    assert table.show_card("p1", show_all=True) is True
    assert len(table.seats[0].shown_cards) == 2


def test_three_player_multiway_flow():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)
    table.sit_down("p3", "Charlie", seat_index=2, chips=100)

    assert table.start_new_hand() is True
    # In 3-player: Dealer=0 (Alice), SB=1 (Bob), BB=2 (Charlie)
    assert table.dealer_seat == 0
    assert table.sb_seat == 1
    assert table.bb_seat == 2

    # UTG is seat 0 (Alice)
    assert table.current_turn_seat == 0
    # Alice raises to 6
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=6) is True
    # Bob (SB) calls 5 more (total 6)
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CALL) is True
    # Charlie (BB) calls 4 more (total 6)
    assert table.current_turn_seat == 2
    assert table.handle_action("p3", ActionType.CALL) is True

    # Flop dealt!
    assert table.street == Street.FLOP
    assert len(table.board_cards) == 3
    assert table.pot_manager.total_pot_amount == 18

    # Post-flop action starts with first active after button -> seat 1 (Bob)
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 2
    assert table.handle_action("p3", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.BET, raise_total_amount=10) is True

    # Bob folds, Charlie calls 10
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.FOLD) is True
    assert table.current_turn_seat == 2
    assert table.handle_action("p3", ActionType.CALL) is True

    # Turn dealt!
    assert table.street == Street.TURN
    assert len(table.board_cards) == 4

