import pytest
from backend.app.engine.state_machine import TableStateMachine, Street, ActionType


def test_sit_down_validation():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    assert table.sit_down("p1", "Alice", seat_index=0, chips=100) is True
    assert table.sit_down("p2", "Bob", seat_index=1, chips=100) is True

    # Cannot sit on occupied seat
    assert table.sit_down("p3", "Charlie", seat_index=0, chips=100) is False
    # Cannot sit twice
    assert table.sit_down("p1", "Alice", seat_index=2, chips=100) is False

    assert len(table.active_seated_players) == 2


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
    assert table.turn_count == 1
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
    assert table.turn_count == 2
    legal_p2 = table.get_legal_actions("p2")
    assert legal_p2.can_check is True

    # P2 checks -> Round ends -> Deal Flop
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.street == Street.FLOP
    assert len(table.board_cards) == 3

    # Flop: Postflop action starts with BB in heads-up (seat 1) -> P2 acts again consecutively!
    assert table.current_turn_seat == 1
    assert table.turn_count == 3  # turn_count incremented even though seat is still 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.turn_count == 4
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


def test_uncontested_hand_can_reveal_reserved_final_board():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    table.handle_action("p1", ActionType.RAISE, raise_total_amount=10)
    table.handle_action("p2", ActionType.FOLD)

    hidden_state = table.get_table_state(viewer_player_id="p1")
    assert table.street == Street.HAND_END
    assert hidden_state["board_cards"] == []
    assert hidden_state["board_cards_full"] == []
    assert hidden_state["board_cards_revealed"] is False

    assert table.reveal_board_cards() is True
    revealed_state = table.get_table_state(viewer_player_id="p1")
    final_cards = revealed_state["board_cards_full"]
    assert len(final_cards) == 5
    assert revealed_state["board_cards_revealed"] is True
    assert len({card["notation"] for card in final_cards}) == 5


def test_allin_fast_forward():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=50)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # P1 goes all-in
    assert table.handle_action("p1", ActionType.ALL_IN) is True
    # P2 calls
    assert table.handle_action("p2", ActionType.CALL) is True

    # Triggers RIT decision
    assert table.street == Street.RIT_DECISION
    assert table.rit_status == "VOTING"
    assert table.is_all_in_runout is True
    # Contenders have hole cards revealed
    assert len(table.seats[0].shown_cards) == 2
    assert len(table.seats[1].shown_cards) == 2
    voting_state = table.get_table_state(viewer_player_id="p1")
    assert len(voting_state["seats"][0]["shown_cards"]) == 2
    assert len(voting_state["seats"][1]["shown_cards"]) == 2
    assert voting_state["seats"][1]["hole_cards"] == []

    # One vote cannot start the runout while the other contender is undecided.
    status, is_tw = table.vote_rit("p1", 1)
    assert status == "WAITING"
    assert is_tw is False
    assert table.rit_enabled is False
    assert table.street == Street.RIT_DECISION

    status, is_tw = table.vote_rit("p2", 1)
    assert status == "FINALIZED"
    assert is_tw is False

    # Deal step by step
    step1 = table.deal_all_in_next_step()
    assert step1 == "FLOP"
    assert len(table.board_cards) == 3

    step2 = table.deal_all_in_next_step()
    assert step2 == "TURN"
    assert len(table.board_cards) == 4

    step3 = table.deal_all_in_next_step()
    assert step3 == "RIVER"
    assert len(table.board_cards) == 5

    step4 = table.deal_all_in_next_step()
    assert step4 == "SHOWDOWN"

    table.enter_showdown()
    assert table.street == Street.HAND_END
    assert len(table.board_cards) == 5
    assert sum(p.chips for p in table.active_seated_players) == 150


def test_run_it_twice_flow():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # P1 all-in 100, P2 calls 100
    assert table.handle_action("p1", ActionType.ALL_IN) is True
    assert table.handle_action("p2", ActionType.CALL) is True
    assert table.street == Street.RIT_DECISION

    # P1 votes 2 (twice) -> WAITING
    status1, _ = table.vote_rit("p1", 2)
    assert status1 == "WAITING"
    assert table.rit_enabled is False

    # P2 votes 2 (twice) -> FINALIZED
    status2, is_tw = table.vote_rit("p2", 2)
    assert status2 == "FINALIZED"
    assert is_tw is True
    assert table.rit_enabled is True

    # Fast forward to showdown
    table.fast_forward_to_showdown()
    assert table.street == Street.HAND_END
    assert len(table.board_cards) == 5
    assert len(table.board_cards_2) == 5
    assert sum(p.chips for p in table.active_seated_players) == 200

    # Verify table state export contains both boards and payouts
    state = table.get_table_state("p1")
    assert state["rit_enabled"] is True
    assert len(state["board_cards"]) == 5
    assert len(state["board_cards_2"]) == 5
    assert len(state["hand_results"]) == 2
    assert state["hand_results"][0]["hand_desc_2"] is not None


def test_show_card_feature():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100, avatar="🦊")
    table.sit_down("p2", "Bob", seat_index=1, chips=100, avatar="🐼")

    table.start_new_hand()
    table.handle_action("p1", ActionType.RAISE, raise_total_amount=10)
    table.handle_action("p2", ActionType.FOLD)

    # Initial state at HAND_END (uncontested): shown_cards should be empty
    assert len(table.seats[0].shown_cards) == 0
    p2_view = table.get_table_state(viewer_player_id="p2")
    # p2 should not see p1's private hole cards or any shown cards
    assert p2_view["seats"][0]["hole_cards"] == []
    assert p2_view["seats"][0]["shown_cards"] == []
    assert p2_view["hand_results"][0]["hole_cards"] == []
    assert p2_view["hand_results"][0]["shown_cards"] == []
    avatars = {result["player_id"]: result["avatar"] for result in p2_view["hand_results"]}
    assert avatars == {"p1": "🦊", "p2": "🐼"}

    # Show single card 0
    assert table.show_card("p1", card_index=0) is True
    assert len(table.seats[0].shown_cards) == 1

    # Check opponent p2 view: p2 should ONLY see the 1 shown card, NOT both hole cards!
    p2_view = table.get_table_state(viewer_player_id="p2")
    assert p2_view["seats"][0]["hole_cards"] == []
    assert len(p2_view["seats"][0]["shown_cards"]) == 1
    assert p2_view["hand_results"][0]["hole_cards"] == []
    assert len(p2_view["hand_results"][0]["shown_cards"]) == 1

    # Check self p1 view: p1 can see both hole cards, and shown_cards has length 1
    p1_view = table.get_table_state(viewer_player_id="p1")
    assert len(p1_view["seats"][0]["hole_cards"]) == 2
    assert len(p1_view["seats"][0]["shown_cards"]) == 1
    assert len(p1_view["hand_results"][0]["hole_cards"]) == 2
    assert len(p1_view["hand_results"][0]["shown_cards"]) == 1

    # Toggle card 1 to also show card 1 (now both cards shown)
    assert table.show_card("p1", toggle_index=1) is True
    assert len(table.seats[0].shown_cards) == 2

    # Toggle card 0 off (now only card 1 shown)
    assert table.show_card("p1", toggle_index=0) is True
    assert len(table.seats[0].shown_cards) == 1
    assert table.seats[0].shown_cards[0] == table.seats[0].hole_cards[1]

    # Hide all
    assert table.show_card("p1", hide_all=True) is True
    assert len(table.seats[0].shown_cards) == 0

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


def test_raise_fallback_and_clamping():
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # P1 calls
    table.handle_action("p1", ActionType.CALL)

    # P2 cannot raise to 3 (< 2 * 2 = 4)
    assert table.handle_action("p2", ActionType.RAISE, raise_total_amount=3) is False

    # P2 raises with 0 amount -> should default to min raise 2x (4) and succeed
    assert table.handle_action("p2", ActionType.RAISE, raise_total_amount=0) is True
    assert table.current_round_highest_bet == 4
    assert table.seats[1].chips == 96

    # P1 cannot raise below 2x (e.g. 5, 6, 7) when highest_bet is 4
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=5) is False
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=6) is False
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=7) is False

    # P1 re-raises with amount=0 -> should default to min raise 2x (8) and succeed
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=0) is True
    assert table.current_round_highest_bet == 8
    assert table.seats[0].chips == 92


def test_raise_allin_exception_when_less_than_two_times():
    # Player with chips less than 2x highest_bet can still all-in
    table = TableStateMachine(max_seats=6, small_blind=10, big_blind=20)
    table.sit_down("p1", "Alice", seat_index=0, chips=30)  # short stack
    table.sit_down("p2", "Bob", seat_index=1, chips=200)

    table.start_new_hand()
    # Alice posted SB 10, remaining chips = 20. Total contribution = 30.
    # Facing BB 20, 2x would be 40. Alice only has 30 total.
    legal = table.get_legal_actions("p1")
    assert legal.can_raise is True
    assert legal.min_raise_to == 30  # Capped at all-in stack
    assert legal.max_raise_to == 30

    # Alice cannot raise to 25 (not all-in and < 40)
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=25) is False

    # Alice can all-in with her remaining chips (30)
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=30) is True
    assert table.seats[0].is_all_in is True
    assert table.seats[0].chips == 0
    assert table.current_round_highest_bet == 30


def test_bet_and_raise_amounts_use_small_blind_as_unit():
    table = TableStateMachine(max_seats=6, small_blind=10, big_blind=20)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # 45 is a legal min-raise by chip amount, but not a multiple of SB 10.
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=45) is False
    assert table.current_round_highest_bet == 20
    assert table.seats[0].chips == 90

    # A multiple of the configured small blind is accepted.
    assert table.handle_action("p1", ActionType.RAISE, raise_total_amount=50) is True
    assert table.current_round_highest_bet == 50


def test_equity_assistant_status_and_reset():
    table = TableStateMachine(max_seats=6, small_blind=10, big_blind=20)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    # Initially False
    assert table.seats[0].using_assistant is False
    assert table.seats[1].using_assistant is False

    # Mark p1 as using assistant
    assert table.set_player_using_assistant("p1", True) is True
    assert table.seats[0].using_assistant is True
    assert table.seats[1].using_assistant is False

    # Check serialized state contains using_assistant
    state = table.get_table_state("p2")
    assert state["seats"][0]["using_assistant"] is True
    assert state["seats"][1]["using_assistant"] is False

    # Fast forward or fold to end hand
    table.handle_action("p1", ActionType.RAISE, raise_total_amount=50)
    table.handle_action("p2", ActionType.FOLD)
    assert table.street == Street.HAND_END

    # In HAND_END summary, using_assistant is preserved
    state_end = table.get_table_state("p2")
    p1_summary = next(r for r in state_end["hand_results"] if r["player_id"] == "p1")
    assert p1_summary["using_assistant"] is True

    # Start new hand -> using_assistant resets to False
    table.start_new_hand()
    assert table.seats[0].using_assistant is False
    assert table.seats[1].using_assistant is False


def test_player_joining_mid_hand_cannot_act_until_next_hand():
    table = TableStateMachine(max_seats=6, small_blind=10, big_blind=20)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    assert table.start_new_hand() is True
    assert table.street == Street.PREFLOP

    # p3 sits down while hand is in progress
    assert table.sit_down("p3", "Charlie", seat_index=2, chips=100) is True
    seat_p3 = table.seats[2]
    assert seat_p3 is not None
    assert len(seat_p3.hole_cards) == 0

    # p3 cannot perform any legal actions
    legal_p3 = table.get_legal_actions("p3")
    assert legal_p3.can_check is False
    assert legal_p3.can_call is False
    assert legal_p3.can_bet is False
    assert legal_p3.can_raise is False
    assert legal_p3.can_fold is False
    assert legal_p3.can_all_in is False

    # p3 cannot execute any actions
    assert table.handle_action("p3", ActionType.CHECK) is False
    assert table.handle_action("p3", ActionType.CALL) is False
    assert table.handle_action("p3", ActionType.RAISE, 40) is False
    assert table.handle_action("p3", ActionType.FOLD) is False
    assert table.handle_action("p3", ActionType.ALL_IN) is False

    # Table state for p3 shows no cards and no legal actions
    state_p3 = table.get_table_state("p3")
    assert state_p3["current_turn_seat"] != 2
    assert state_p3["legal_actions"]["can_check"] is False
    assert state_p3["legal_actions"]["can_raise"] is False
    assert state_p3["legal_actions"]["can_fold"] is False
    assert state_p3["seats"][2]["has_cards"] is False

    # Play out current hand with p1 and p2
    # In Heads-up: Dealer is SB (seat 0, p1), other is BB (seat 1, p2)
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.CALL) is True
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True

    # Flop: turn goes to p2 (seat 1), not p3 (seat 2)
    assert table.street == Street.FLOP
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.CHECK) is True

    # Turn: turn goes to p2 (seat 1), not p3
    assert table.street == Street.TURN
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.CHECK) is True

    # River
    assert table.street == Street.RIVER
    assert table.current_turn_seat == 1
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.current_turn_seat == 0
    assert table.handle_action("p1", ActionType.CHECK) is True

    # Showdown / Hand End
    assert table.street == Street.HAND_END

    # Start next hand (hand 2): p3 is now dealt cards and participates
    assert table.start_new_hand() is True
    assert table.hand_number == 2
    assert len(table.seats[0].hole_cards) == 2
    assert len(table.seats[1].hole_cards) == 2
    assert len(table.seats[2].hole_cards) == 2

    # In 3-player hand: dealer is seat 1, SB is seat 2 (p3), BB is seat 0 (p1), UTG is seat 2 (p3) or seat 1 (p2)
    # The active turn is on one of the players with cards
    assert table.current_turn_seat is not None
    active_player_id = table.seats[table.current_turn_seat].player_id
    legal_active = table.get_legal_actions(active_player_id)
    assert legal_active.can_fold is True
    assert (legal_active.can_call or legal_active.can_check) is True

