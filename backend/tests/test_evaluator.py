import pytest
from backend.app.engine.card import Card
from backend.app.engine.evaluator import evaluate_hand, HandCategory


def cards(card_strings: str) -> list[Card]:
    """Helper to parse a whitespace-separated string of card notations."""
    return [Card.from_str(s) for s in card_strings.strip().split()]


def test_royal_flush():
    hand = cards("As Ks Qs Js Ts")
    result = evaluate_hand(hand)
    assert result.category == HandCategory.ROYAL_FLUSH
    assert result.score_vector == (10, 14)


def test_straight_flush_and_wheel():
    # Regular Straight Flush (9 high)
    sf1 = evaluate_hand(cards("9h 8h 7h 6h 5h"))
    assert sf1.category == HandCategory.STRAIGHT_FLUSH
    assert sf1.score_vector == (9, 9)

    # Wheel Straight Flush (5 high with Ace)
    sf_wheel = evaluate_hand(cards("Ah 2h 3h 4h 5h"))
    assert sf_wheel.category == HandCategory.STRAIGHT_FLUSH
    assert sf_wheel.score_vector == (9, 5)

    assert sf1 > sf_wheel


def test_four_of_a_kind():
    quads_k = evaluate_hand(cards("Kd Kh Kc Ks 2d"))
    quads_q = evaluate_hand(cards("Qd Qh Qc Qs Ad"))
    quads_k_lower_kicker = evaluate_hand(cards("Kd Kh Kc Ks 3d"))

    assert quads_k.category == HandCategory.FOUR_OF_A_KIND
    assert quads_k > quads_q
    assert quads_k_lower_kicker > quads_k  # 3 kicker > 2 kicker


def test_full_house():
    fh_kings_full = evaluate_hand(cards("Kh Kd Kc As Ah"))
    fh_aces_full = evaluate_hand(cards("Ah Ad Ac Ks Kh"))
    fh_kings_jacks = evaluate_hand(cards("Kh Kd Kc Js Jh"))

    assert fh_kings_full.category == HandCategory.FULL_HOUSE
    assert fh_aces_full > fh_kings_full
    assert fh_kings_full > fh_kings_jacks


def test_flush():
    flush_a = evaluate_hand(cards("Ah Jh 9h 6h 2h"))
    flush_k = evaluate_hand(cards("Kh Qh Jh 9h 7h"))
    flush_a_low = evaluate_hand(cards("Ah Th 9h 6h 2h"))

    assert flush_a.category == HandCategory.FLUSH
    assert flush_a > flush_k
    assert flush_a > flush_a_low


def test_straight_and_wheel():
    straight_broadway = evaluate_hand(cards("Ah Kd Qc Js Th"))
    straight_9 = evaluate_hand(cards("9h 8d 7c 6s 5h"))
    straight_wheel = evaluate_hand(cards("Ah 2d 3c 4s 5h"))

    assert straight_broadway.category == HandCategory.STRAIGHT
    assert straight_broadway.score_vector == (5, 14)
    assert straight_wheel.category == HandCategory.STRAIGHT
    assert straight_wheel.score_vector == (5, 5)

    assert straight_broadway > straight_9
    assert straight_9 > straight_wheel


def test_three_of_a_kind():
    trips_a = evaluate_hand(cards("Ah Ad Ac Kd Qs"))
    trips_k = evaluate_hand(cards("Kh Kd Kc Ah Qs"))
    trips_a_low = evaluate_hand(cards("Ah Ad Ac Kd Js"))

    assert trips_a.category == HandCategory.THREE_OF_A_KIND
    assert trips_a > trips_k
    assert trips_a > trips_a_low


def test_two_pair():
    tp_ak = evaluate_hand(cards("Ah Ad Kh Kd Qs"))
    tp_aq = evaluate_hand(cards("Ah Ad Qh Qd Ks"))
    tp_ak_low = evaluate_hand(cards("Ah Ad Kh Kd Js"))

    assert tp_ak.category == HandCategory.TWO_PAIR
    assert tp_ak > tp_aq
    assert tp_ak > tp_ak_low


def test_one_pair():
    p_a = evaluate_hand(cards("Ah Ad Kd Qs Js"))
    p_k = evaluate_hand(cards("Kh Kd Ah Qs Js"))
    p_a_low = evaluate_hand(cards("Ah Ad Kd Qs Ts"))

    assert p_a.category == HandCategory.ONE_PAIR
    assert p_a > p_k
    assert p_a > p_a_low


def test_high_card():
    hc_a = evaluate_hand(cards("Ah Kd Qs Js 9c"))
    hc_k = evaluate_hand(cards("Kh Qd Js 9s 8c"))
    hc_a_low = evaluate_hand(cards("Ah Kd Qs Js 8c"))

    assert hc_a.category == HandCategory.HIGH_CARD
    assert hc_a > hc_k
    assert hc_a > hc_a_low


def test_7_cards_evaluation():
    # Hole cards: As Ks, Board: Qs Js Ts 2c 3d -> Royal flush extracted
    hand = cards("As Ks Qs Js Ts 2c 3d")
    result = evaluate_hand(hand)
    assert result.category == HandCategory.ROYAL_FLUSH
    assert len(result.best_cards) == 5

    # 3 pairs on 7 cards -> Best two pair chosen
    hand2 = cards("Ah Ad Kh Kd Qh Qd 2c")
    result2 = evaluate_hand(hand2)
    assert result2.category == HandCategory.TWO_PAIR
    assert result2.score_vector == (HandCategory.TWO_PAIR.value, 14, 13, 12)


def test_tie_hands():
    # Identical 5 cards with different suits on high card / straight
    h1 = evaluate_hand(cards("Ah Kd Qc Js 9h"))
    h2 = evaluate_hand(cards("Ac Kh Qd Jc 9d"))
    assert h1 == h2
