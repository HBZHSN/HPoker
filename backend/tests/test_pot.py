import pytest
from backend.app.engine.card import Card
from backend.app.engine.evaluator import evaluate_hand
from backend.app.engine.pot import PotManager, PotPayout


def cards(card_strings: str) -> list[Card]:
    return [Card.from_str(s) for s in card_strings.strip().split()]


def test_two_player_simple_pot():
    pm = PotManager()
    pm.record_bet("p1", 100)
    pm.record_bet("p2", 100)

    pots, refunds = pm.calculate_pots()
    assert len(pots) == 1
    assert pots[0].name == "主池"
    assert pots[0].amount == 200
    assert pots[0].eligible_players == {"p1", "p2"}
    assert refunds == {}

    # Showdown: p1 has Pair of Aces, p2 has Pair of Kings
    eval_p1 = evaluate_hand(cards("Ah Ad 2c 3d 4s"))
    eval_p2 = evaluate_hand(cards("Kh Kd 2c 3d 4s"))

    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2},
        seat_order_from_sb=["p1", "p2"]
    )
    assert len(payouts) == 1
    assert payouts[0].player_id == "p1"
    assert payouts[0].amount == 200


def test_three_player_one_allin_side_pot():
    # P1 has 50 (all-in)
    # P2 has 100 (calls)
    # P3 has 100 (calls)
    pm = PotManager()
    pm.record_bet("p1", 50)
    pm.record_bet("p2", 100)
    pm.record_bet("p3", 100)

    pots, refunds = pm.calculate_pots()
    assert len(pots) == 2
    # Main pot: 50 * 3 = 150 (eligible: p1, p2, p3)
    assert pots[0].name == "主池"
    assert pots[0].amount == 150
    assert pots[0].eligible_players == {"p1", "p2", "p3"}

    # Side pot: 50 * 2 = 100 (eligible: p2, p3)
    assert pots[1].name == "边池 1"
    assert pots[1].amount == 100
    assert pots[1].eligible_players == {"p2", "p3"}

    # Case A: P1 has Flush (beats everyone), P2 has Straight (beats P3)
    eval_p1 = evaluate_hand(cards("Ah Kh Qh Jh 9h"))   # Flush
    eval_p2 = evaluate_hand(cards("Th 9d 8c 7s 6h"))   # Straight
    eval_p3 = evaluate_hand(cards("2h 3d 4c 5s 7h"))   # High card

    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2, "p3": eval_p3},
        seat_order_from_sb=["p1", "p2", "p3"]
    )
    payout_dict = {pid: 0 for pid in ["p1", "p2", "p3"]}
    for p in payouts:
        payout_dict[p.player_id] += p.amount

    assert payout_dict["p1"] == 150  # P1 wins Main Pot
    assert payout_dict["p2"] == 100  # P2 wins Side Pot
    assert payout_dict["p3"] == 0


def test_four_player_multiple_allin_side_pots():
    # P1: 20 allin
    # P2: 50 allin
    # P3: 100 allin
    # P4: 100 call
    pm = PotManager()
    pm.record_bet("p1", 20)
    pm.record_bet("p2", 50)
    pm.record_bet("p3", 100)
    pm.record_bet("p4", 100)

    pots, refunds = pm.calculate_pots()
    assert len(pots) == 3
    # Main pot: 20 * 4 = 80 (eligible: p1, p2, p3, p4)
    assert pots[0].amount == 80
    assert pots[0].eligible_players == {"p1", "p2", "p3", "p4"}

    # Side pot 1: (50-20) * 3 = 90 (eligible: p2, p3, p4)
    assert pots[1].amount == 90
    assert pots[1].eligible_players == {"p2", "p3", "p4"}

    # Side pot 2: (100-50) * 2 = 100 (eligible: p3, p4)
    assert pots[2].amount == 100
    assert pots[2].eligible_players == {"p3", "p4"}


def test_uncalled_bet_refund():
    # P1 bets 50 (all-in)
    # P2 raises to 150
    # P3 folds after contributing 20
    pm = PotManager()
    pm.record_bet("p1", 50)
    pm.record_bet("p2", 150)
    pm.record_bet("p3", 20)
    pm.record_fold("p3")

    pots, refunds = pm.calculate_pots()
    # P2 bet 150, but max active competitor P1 only has 50.
    # So P2 should be refunded 100 uncalled chips!
    assert refunds == {"p2": 100}

    # Total pot remaining: 50(p1) + 50(p2) + 20(p3) = 120
    assert len(pots) == 1
    assert pots[0].amount == 120
    assert pots[0].eligible_players == {"p1", "p2"}


def test_tie_split_and_odd_chips():
    pm = PotManager()
    pm.record_bet("p1", 50)
    pm.record_bet("p2", 50)
    pm.record_bet("p3", 1)  # Dead money from folded player
    pm.record_fold("p3")

    eval_p1 = evaluate_hand(cards("Ah Kd Qc Js 9h"))
    eval_p2 = evaluate_hand(cards("Ac Kh Qd Jc 9d"))  # Identical hands (Tie)

    # Seat order: p1 is SB, p2 is BB
    payouts = pm.resolve_showdown(
        hand_evaluations={"p1": eval_p1, "p2": eval_p2},
        seat_order_from_sb=["p1", "p2"]
    )
    # 101 chips split: 50 each + 1 odd chip to SB (p1)
    payout_dict = {pid: 0 for pid in ["p1", "p2"]}
    for p in payouts:
        payout_dict[p.player_id] += p.amount

    assert payout_dict["p1"] == 51
    assert payout_dict["p2"] == 50
