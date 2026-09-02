import asyncio

import pytest
from backend.app.engine.state_machine import TableStateMachine, Street, ActionType
from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.evaluator import evaluate_hand
from backend.app.engine.pot import PotManager
from backend.app.services.timeout_manager import TimeoutManager


def test_rit_veto_rule():
    """Verify that a one-vote veto waits for every contender before runout."""
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)
    table.sit_down("p3", "Charlie", seat_index=2, chips=100)

    table.start_new_hand()
    table.handle_action("p1", ActionType.ALL_IN)
    table.handle_action("p2", ActionType.ALL_IN)
    table.handle_action("p3", ActionType.ALL_IN)

    assert table.street == Street.RIT_DECISION
    assert len(table.rit_voters) == 3

    # Player 1 votes 2 (twice) -> WAITING
    status1, is_tw1 = table.vote_rit("p1", 2)
    assert status1 == "WAITING"
    assert is_tw1 is False

    # Player 2 votes 1 (once) -> still waiting for Player 3.
    status2, is_tw2 = table.vote_rit("p2", 1)
    assert status2 == "WAITING"
    assert is_tw2 is False
    assert table.street == Street.RIT_DECISION
    assert table.rit_enabled is False
    assert table.rit_status == "VOTING"

    status3, is_tw3 = table.vote_rit("p3", 2)
    assert status3 == "FINALIZED"
    assert is_tw3 is False
    assert table.rit_status == "AGREED_ONCE"


def test_rit_unanimous_rule():
    """Verify that only if ALL players vote 2, Run It Twice is enabled."""
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    table.handle_action("p1", ActionType.ALL_IN)
    table.handle_action("p2", ActionType.CALL)

    assert table.street == Street.RIT_DECISION

    # p1 votes 2 -> WAITING
    status1, _ = table.vote_rit("p1", 2)
    assert status1 == "WAITING"

    # p2 votes 2 -> FINALIZED as Run It Twice!
    status2, is_tw = table.vote_rit("p2", 2)
    assert status2 == "FINALIZED"
    assert is_tw is True
    assert table.rit_enabled is True
    assert table.rit_status == "AGREED_TWICE"


def test_rit_does_not_timeout_before_all_votes():
    """Verify that an incomplete vote remains open without a timeout fallback."""
    table = TableStateMachine(max_seats=6, small_blind=1, big_blind=2)
    table.sit_down("p1", "Alice", seat_index=0, chips=100)
    table.sit_down("p2", "Bob", seat_index=1, chips=100)

    table.start_new_hand()
    table.handle_action("p1", ActionType.ALL_IN)
    table.handle_action("p2", ActionType.CALL)

    table.vote_rit("p1", 2)
    # p2 did not vote; the compatibility hook must not finalize the hand.
    assert table.timeout_rit() is False
    assert table.rit_enabled is False
    assert table.rit_status == "VOTING"
    assert table.street == Street.RIT_DECISION


@pytest.mark.asyncio
async def test_rit_timer_is_disabled():
    """Verify that the legacy RIT timer API cannot start a countdown task."""
    manager = TimeoutManager()
    timed_out = False

    async def on_timeout(_room_id):
        nonlocal timed_out
        timed_out = True

    manager.start_rit_timer("room-1", 0, on_timeout)
    await asyncio.sleep(0)

    assert "room-1" not in manager._rit_tasks
    assert timed_out is False


def test_rit_pot_split_math():
    """Verify that PotManager splits pots accurately for Run It Twice."""
    pot_mgr = PotManager()
    pot_mgr.record_bet("p1", 100)
    pot_mgr.record_bet("p2", 100)

    # p1 has higher hand on board 1, p2 has higher hand on board 2
    b1_cards = [Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.DIAMONDS), Card(Rank.EIGHT, Suit.CLUBS), Card(Rank.FOUR, Suit.SPADES), Card(Rank.THREE, Suit.HEARTS)]
    b2_cards = [Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.DIAMONDS), Card(Rank.EIGHT, Suit.CLUBS), Card(Rank.FOUR, Suit.SPADES), Card(Rank.THREE, Suit.HEARTS)]

    p1_hole = [Card(Rank.ACE, Suit.CLUBS), Card(Rank.TWO, Suit.HEARTS)]  # Set of Aces on b1, One Pair on b2
    p2_hole = [Card(Rank.KING, Suit.SPADES), Card(Rank.TWO, Suit.DIAMONDS)]  # Set of Kings on b2, One Pair on b1

    eval1_p1 = evaluate_hand(p1_hole + b1_cards)
    eval1_p2 = evaluate_hand(p2_hole + b1_cards)

    eval2_p1 = evaluate_hand(p1_hole + b2_cards)
    eval2_p2 = evaluate_hand(p2_hole + b2_cards)

    p1_payouts, p2_payouts, combined = pot_mgr.resolve_showdown_twice(
        hand_evaluations_1={"p1": eval1_p1, "p2": eval1_p2},
        hand_evaluations_2={"p1": eval2_p1, "p2": eval2_p2},
        seat_order_from_sb=["p1", "p2"]
    )

    # Board 1: 100 chips to p1
    assert len(p1_payouts) == 1
    assert p1_payouts[0].player_id == "p1"
    assert p1_payouts[0].amount == 100

    # Board 2: 100 chips to p2
    assert len(p2_payouts) == 1
    assert p2_payouts[0].player_id == "p2"
    assert p2_payouts[0].amount == 100

    # Total combined: 200 chips split evenly between p1 and p2 (100 each)
    p1_total = sum(p.amount for p in combined if p.player_id == "p1")
    p2_total = sum(p.amount for p in combined if p.player_id == "p2")
    assert p1_total == 100
    assert p2_total == 100
