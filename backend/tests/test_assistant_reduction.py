import pytest
from backend.app.engine.card import Card
from backend.app.engine.evaluator import evaluate_hand
from backend.app.engine.pot import PotManager, PotPayout
from backend.app.engine.state_machine import TableStateMachine, PlayerSeat, Street, ActionType
from backend.app.models.room import RoomConfig, Room


def cards(card_strings: str) -> list[Card]:
    return [Card.from_str(s) for s in card_strings.strip().split()]


def test_room_config_assistant_win_ratio():
    # Default is 0.70
    cfg = RoomConfig()
    assert cfg.assistant_win_ratio == 0.70
    assert cfg.to_dict()["assistant_win_ratio"] == 0.70
    assert cfg.to_dict()["assistant_win_pct"] == 70

    # Custom valid ratio
    cfg2 = RoomConfig(assistant_win_ratio=0.85)
    assert cfg2.assistant_win_ratio == 0.85
    assert cfg2.to_dict()["assistant_win_pct"] == 85

    # Out of range bounds
    with pytest.raises(ValueError):
        RoomConfig(assistant_win_ratio=0.05)
    with pytest.raises(ValueError):
        RoomConfig(assistant_win_ratio=1.05)


def test_pot_showdown_assistant_win_reduction():
    """Assistant keeps principal and 70% of the positive profit."""
    pm = PotManager()
    # 2 players contribute 100 each -> pot = 200
    pm.record_bet("p1", 100)
    pm.record_bet("p2", 100)

    eval_p1 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))  # Pair of Aces (Winner)
    eval_p2 = evaluate_hand(cards("Kh Kd 2c 3d 4s"))  # Pair of Kings (Runner-up)

    # p1 used assistant, win ratio is 0.70, SB is 10
    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2},
        seat_order_from_sb=["p1", "p2"],
        assistant_players={"p1"},
        assistant_win_ratio=0.70,
        small_blind=10,
    )

    # p1's principal is 100, so its profit is 200 - 100 = 100.
    # p1 keeps 100 + 100 * 0.70 = 170; p2 receives the remaining 30.
    payout_dict = {p.player_id: p.amount for p in payouts}
    assert payout_dict["p1"] == 170
    assert payout_dict["p2"] == 30
    assert sum(p.amount for p in payouts) == 200


def test_two_player_allin_call_assistant_uses_profit_only():
    """Heads-up All-in/Call returns principal before applying the assistant ratio."""
    table = TableStateMachine(small_blind=10, big_blind=20, assistant_win_ratio=0.70)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)
    assert table.start_new_hand() is True

    table.seats[0].using_assistant = True
    assert table.handle_action("p1", ActionType.ALL_IN) is True
    assert table.handle_action("p2", ActionType.CALL) is True
    assert table.street == Street.RIT_DECISION

    table.board_cards = cards("2c 3d 4s 7h 9c")
    table.seats[0].hole_cards = cards("Ah Ad")
    table.seats[1].hole_cards = cards("Kh Kd")
    table.enter_showdown()

    payout_dict = {}
    for payout in table.payouts:
        payout_dict[payout.player_id] = payout_dict.get(payout.player_id, 0) + payout.amount

    # Both players contributed 100; p1 wins the 200-chip pot.
    assert payout_dict["p1"] == 170
    assert payout_dict["p2"] == 30
    assert table.seats[0].chips == 170
    assert table.seats[1].chips == 30


def test_pot_showdown_small_blind_quantization():
    """Verify that when 70% produces non-multiples of small_blind, chips are rounded to SB and conserved."""
    pm = PotManager()
    # Total contributions are 125 chips, small_blind = 10.
    pm.record_bet("p1", 65)
    pm.record_bet("p2", 60)

    eval_p1 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))  # Winner
    eval_p2 = evaluate_hand(cards("Kh Kd 2c 3d 4s"))  # Runner-up

    # Total pot = 120, refunds: p1 = 5
    pots, refunds = pm.calculate_pots()
    assert refunds == {"p1": 5}
    assert pots[0].amount == 120

    # p1's principal in the pot is 60 and its profit is 60.
    # 60 * 0.70 = 42 -> 40 chips after SB quantization; p1 gets 100 from
    # the pot, plus its separate 5-chip refund.  The 20-chip deduction goes
    # to p2.
    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2},
        seat_order_from_sb=["p1", "p2"],
        assistant_players={"p1"},
        assistant_win_ratio=0.70,
        small_blind=10,
    )

    # Check refund was issued
    refund_p1 = sum(p.amount for p in payouts if p.player_id == "p1" and p.pot_name == "多余下注退回")
    assert refund_p1 == 5

    # Check pot payouts
    pot_payout_p1 = sum(p.amount for p in payouts if p.player_id == "p1" and p.pot_name != "多余下注退回")
    pot_payout_p2 = sum(p.amount for p in payouts if p.player_id == "p2")
    assert pot_payout_p1 == 100
    assert pot_payout_p2 == 20
    # Strict chip conservation: 125 total bet == sum of all payouts
    assert sum(p.amount for p in payouts) == 125


def test_pot_showdown_multiple_runner_ups():
    """Multiple players tied for runner-up receive deducted chips split by SB units."""
    pm = PotManager()
    pm.record_bet("p1", 100)
    pm.record_bet("p2", 100)
    pm.record_bet("p3", 100)

    # p1: Straight Flush
    # p2: Pair of Aces
    # p3: Pair of Aces (identical runner-up hand)
    eval_p1 = evaluate_hand(cards("9h 8h 7h 6h 5h"))
    eval_p2 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))
    eval_p3 = evaluate_hand(cards("Ac As 2h 3c 4d"))

    # Pot = 300, SB = 10, ratio = 0.70
    # p1's principal is 100 and its profit is 200.
    # p1 gets 100 + 200 * 0.70 = 240; the 60-chip deduction is split equally
    # between the two runner-ups.
    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2, "p3": eval_p3},
        seat_order_from_sb=["p2", "p3", "p1"],
        assistant_players={"p1"},
        assistant_win_ratio=0.70,
        small_blind=10,
    )

    payout_dict = {}
    for p in payouts:
        payout_dict[p.player_id] = payout_dict.get(p.player_id, 0) + p.amount

    assert payout_dict["p1"] == 240
    assert payout_dict["p2"] == 30
    assert payout_dict["p3"] == 30
    assert sum(payout_dict.values()) == 300


def test_side_pot_assistant_reduction_returns_principal_per_pot():
    """A winner's principal is tracked separately for each side-pot tier."""
    pm = PotManager()
    pm.record_bet("p1", 100)
    pm.record_bet("p2", 200)
    pm.record_bet("p3", 200)

    pots, refunds = pm.calculate_pots()
    assert refunds == {}
    assert [(pot.amount, pot.eligible_players) for pot in pots] == [
        (300, {"p1", "p2", "p3"}),
        (200, {"p2", "p3"}),
    ]

    eval_p1 = evaluate_hand(cards("9h 8h 7h 6h 5h"))  # Wins the main pot
    eval_p2 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))  # Wins the side pot
    eval_p3 = evaluate_hand(cards("Kh Kd 2c 3d 4s"))

    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2, "p3": eval_p3},
        seat_order_from_sb=["p1", "p2", "p3"],
        assistant_players={"p1"},
        assistant_win_ratio=0.70,
        small_blind=10,
    )

    payout_dict = {}
    for payout in payouts:
        payout_dict[payout.player_id] = payout_dict.get(payout.player_id, 0) + payout.amount

    # Main pot: p1 contributed 100, so it keeps 100 + (300 - 100) * 70% = 240.
    # The 60 deduction goes to p2, who also wins the 200-chip side pot.
    assert payout_dict == {"p1": 240, "p2": 260}
    assert sum(payout_dict.values()) == 500


def test_pot_showdown_non_assistant_winner_no_deduction():
    """Winner did NOT use assistant -> 100% of pot to winner."""
    pm = PotManager()
    pm.record_bet("p1", 100)
    pm.record_bet("p2", 100)

    eval_p1 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))
    eval_p2 = evaluate_hand(cards("Kh Kd 2c 3d 4s"))

    # p2 used assistant, but p1 won
    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2},
        seat_order_from_sb=["p1", "p2"],
        assistant_players={"p2"},
        assistant_win_ratio=0.70,
        small_blind=10,
    )

    payout_dict = {p.player_id: p.amount for p in payouts}
    assert payout_dict["p1"] == 200
    assert "p2" not in payout_dict


def test_uncontested_fold_assistant_winner_deduction():
    """Single winner takes pot without showdown; if using assistant, discounted pot given and compensation returned."""
    table = TableStateMachine(small_blind=10, big_blind=20, assistant_win_ratio=0.70)
    table.sit_down("p1", "Alice", 0, chips=1000)
    table.sit_down("p2", "Bob", 1, chips=1000)
    assert table.start_new_hand() is True

    # Mark p1 as using assistant
    seat_p1 = table.seats[0]
    seat_p2 = table.seats[1]
    seat_p1.using_assistant = True

    # Preflop: p1 is SB (10), p2 is BB (20)
    # p1 raises to 60 (bet of 60)
    assert table.handle_action("p1", ActionType.RAISE, 60) is True
    # p2 folds (contributed 20)
    assert table.handle_action("p2", ActionType.FOLD) is True

    # Hand ends uncontested.
    # p1's uncalled bet of 40 is refunded.
    # Active pot is 20 + 20 = 40.
    # p1's principal in the contested pot is 20 and its profit is 20.
    # It keeps 20 + (20 * 0.70 rounded to 10) = 30 chips from the pot.
    # The 10-chip deduction is compensated back to p2.
    assert table.street == Street.HAND_END
    p1_refund = sum(p.amount for p in table.payouts if p.player_id == "p1" and p.pot_name == "多余下注退回")
    p1_pot_payout = sum(p.amount for p in table.payouts if p.player_id == "p1" and p.pot_name != "多余下注退回")
    p2_payout = sum(p.amount for p in table.payouts if p.player_id == "p2")

    assert p1_refund == 40
    assert p1_pot_payout == 30
    assert p2_payout == 10
    # Total chips in system strictly conserved: started with 2000, must end with 2000
    assert seat_p1.chips + seat_p2.chips == 2000
    # p1 chips: 1000 - 60 + 40(refund) + 30(pot) = 1010
    # p2 chips: 1000 - 20 + 10(comp) = 990
    assert seat_p1.chips == 1010
    assert seat_p2.chips == 990

    # Verify hand_results shows original vs adjusted profit
    state = table.get_table_state()
    res_p1 = next(r for r in state["hand_results"] if r["player_id"] == "p1")
    res_p2 = next(r for r in state["hand_results"] if r["player_id"] == "p2")

    assert res_p1["original_net_profit"] == 20
    assert res_p1["net_profit"] == 10
    assert res_p1["assistant_adjustment"] == -10
    assert res_p1["using_assistant"] is True

    assert res_p2["original_net_profit"] == -20
    assert res_p2["net_profit"] == -10
    assert res_p2["assistant_adjustment"] == 10
    assert res_p2["using_assistant"] is False


def test_showdown_hand_results_assistant_impact():
    """Verify that showdown hand_results includes original profit and assistant adjustment."""
    table = TableStateMachine(small_blind=10, big_blind=20, assistant_win_ratio=0.70)
    table.sit_down("p1", "Alice", 0, chips=1000)
    table.sit_down("p2", "Bob", 1, chips=1000)
    table.start_new_hand()

    # Both players put in 100
    seat_p1 = table.seats[0]
    seat_p2 = table.seats[1]
    seat_p1.using_assistant = True

    # Preflop: p1 call BB (20), p2 checks -> deals Flop
    assert table.handle_action("p1", ActionType.CALL) is True
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.street == Street.FLOP

    # Force board and hole cards
    table.board_cards = cards("2c 3d 4s")
    table.deck._cards = [Card.from_str("7s"), Card.from_str("8s"), Card.from_str("9s"), Card.from_str("Ts")]
    seat_p1.hole_cards = cards("Ah Ad")  # Pair of Aces
    seat_p2.hole_cards = cards("Kh Kd")  # Pair of Kings

    # Flop: p2 checks, p1 bets 80 (total 100), p2 calls -> deals Turn
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.handle_action("p1", ActionType.BET, 80) is True
    assert table.handle_action("p2", ActionType.CALL) is True
    assert table.street == Street.TURN

    # Turn: both check -> deals River
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.handle_action("p1", ActionType.CHECK) is True
    assert table.street == Street.RIVER

    # River: both check -> showdown
    assert table.handle_action("p2", ActionType.CHECK) is True
    assert table.handle_action("p1", ActionType.CHECK) is True
    assert table.street == Street.HAND_END

    state = table.get_table_state()
    res_p1 = next(r for r in state["hand_results"] if r["player_id"] == "p1")
    res_p2 = next(r for r in state["hand_results"] if r["player_id"] == "p2")

    # Pot = 200, 100 each.
    # Originally: p1 wins 200 (net +100), p2 wins 0 (net -100).
    # With 70% assistant profit sharing:
    # p1 keeps its 100-chip principal plus 70% of its 100-chip profit,
    # receiving 170 (net +70). p2 receives the remaining 30 (net -70).
    # Adjustments: p1 -30, p2 +30.
    assert res_p1["original_payout_amount"] == 200
    assert res_p1["payout_amount"] == 170
    assert res_p1["original_net_profit"] == 100
    assert res_p1["net_profit"] == 70
    assert res_p1["assistant_adjustment"] == -30
    assert res_p1["using_assistant"] is True

    assert res_p2["original_payout_amount"] == 0
    assert res_p2["payout_amount"] == 30
    assert res_p2["original_net_profit"] == -100
    assert res_p2["net_profit"] == -70
    assert res_p2["assistant_adjustment"] == 30
    assert res_p2["using_assistant"] is False
