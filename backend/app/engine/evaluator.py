"""Texas Hold'em 7-Card Hand Evaluator & Hand Ranker.

Evaluates 5-to-7 card poker hands with 100% standard rules:
- 10 hand categories: High Card -> Royal Flush
- Precise tie-breakers (kickers, high/low pairs, wheel straights A-2-3-4-5)
- Best 5-card extraction for visual display and showdown highlighting
"""

from __future__ import annotations
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Sequence, Tuple, Optional
from collections import Counter
import itertools

from backend.app.engine.card import Card, Rank, Suit


class HandCategory(IntEnum):
    HIGH_CARD = 1           # 高牌
    ONE_PAIR = 2            # 一对
    TWO_PAIR = 3            # 两对
    THREE_OF_A_KIND = 4     # 三条
    STRAIGHT = 5            # 顺子
    FLUSH = 6               # 同花
    FULL_HOUSE = 7          # 葫芦
    FOUR_OF_A_KIND = 8      # 四条 (金刚)
    STRAIGHT_FLUSH = 9      # 同花顺
    ROYAL_FLUSH = 10        # 皇家同花顺

    @property
    def display_name(self) -> str:
        names = {
            HandCategory.HIGH_CARD: "高牌",
            HandCategory.ONE_PAIR: "一对",
            HandCategory.TWO_PAIR: "两对",
            HandCategory.THREE_OF_A_KIND: "三条",
            HandCategory.STRAIGHT: "顺子",
            HandCategory.FLUSH: "同花",
            HandCategory.FULL_HOUSE: "葫芦",
            HandCategory.FOUR_OF_A_KIND: "四条",
            HandCategory.STRAIGHT_FLUSH: "同花顺",
            HandCategory.ROYAL_FLUSH: "皇家同花顺",
        }
        return names[self]


@dataclass(frozen=True)
class HandEvaluation:
    category: HandCategory
    score_vector: Tuple[int, ...]
    best_cards: Tuple[Card, Card, Card, Card, Card]
    description: str

    def __lt__(self, other: HandEvaluation) -> bool:
        if not isinstance(other, HandEvaluation):
            return NotImplemented
        return self.score_vector < other.score_vector

    def __gt__(self, other: HandEvaluation) -> bool:
        if not isinstance(other, HandEvaluation):
            return NotImplemented
        return self.score_vector > other.score_vector

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandEvaluation):
            return False
        return self.score_vector == other.score_vector

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "category_name": self.category.display_name,
            "description": self.description,
            "best_cards": [c.to_dict() for c in self.best_cards],
            "score_vector": list(self.score_vector),
        }


def _check_straight(ranks_desc: Sequence[int]) -> Optional[int]:
    """Check if distinct descending ranks form a straight.
    
    Returns the highest rank in the straight, or None.
    Handles standard straights (e.g., 14,13,12,11,10 -> 14)
    and Wheel straight (A-2-3-4-5 -> returns 5).
    """
    unique_ranks = sorted(set(ranks_desc), reverse=True)
    if len(unique_ranks) < 5:
        return None

    # Standard straight check
    for i in range(len(unique_ranks) - 4):
        window = unique_ranks[i:i+5]
        if window[0] - window[4] == 4:
            return window[0]

    # Wheel straight check (A-5-4-3-2)
    if {14, 5, 4, 3, 2}.issubset(unique_ranks):
        return 5

    return None


def evaluate_5_cards(cards: Sequence[Card]) -> HandEvaluation:
    """Evaluate exactly 5 cards and return HandEvaluation."""
    if len(cards) != 5:
        raise ValueError(f"evaluate_5_cards requires exactly 5 cards, got {len(cards)}")

    # Sort cards descending by rank value
    sorted_cards = sorted(cards, key=lambda c: c.rank.value, reverse=True)
    ranks = [c.rank.value for c in sorted_cards]
    suits = [c.suit for c in sorted_cards]

    is_flush = len(set(suits)) == 1
    straight_top = _check_straight(ranks)
    is_straight = straight_top is not None

    # Count rank frequencies
    rank_counts = Counter(ranks)
    # Sort by frequency descending, then rank descending
    freq_sorted = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    # 1. Royal Flush / Straight Flush
    if is_flush and is_straight:
        if straight_top == 14 and 10 in ranks:
            # Royal Flush
            return HandEvaluation(
                category=HandCategory.ROYAL_FLUSH,
                score_vector=(HandCategory.ROYAL_FLUSH.value, 14),
                best_cards=tuple(sorted_cards),
                description=f"皇家同花顺 ({sorted_cards[0].suit.display_name})"
            )
        else:
            # Straight Flush
            if straight_top == 5:
                # Wheel straight flush: 5-4-3-2-A
                wheel_sorted = sorted(sorted_cards, key=lambda c: (1 if c.rank == Rank.ACE else c.rank.value), reverse=True)
                return HandEvaluation(
                    category=HandCategory.STRAIGHT_FLUSH,
                    score_vector=(HandCategory.STRAIGHT_FLUSH.value, 5),
                    best_cards=tuple(wheel_sorted),
                    description=f"同花顺 (5高, {sorted_cards[0].suit.display_name})"
                )
            return HandEvaluation(
                category=HandCategory.STRAIGHT_FLUSH,
                score_vector=(HandCategory.STRAIGHT_FLUSH.value, straight_top),
                best_cards=tuple(sorted_cards),
                description=f"同花顺 ({Rank(straight_top).display_name}高, {sorted_cards[0].suit.display_name})"
            )

    # 2. Four of a Kind (四条)
    if freq_sorted[0][1] == 4:
        quad_rank = freq_sorted[0][0]
        kicker = freq_sorted[1][0]
        # Sort best_cards with quad first, then kicker
        quad_cards = [c for c in sorted_cards if c.rank.value == quad_rank]
        kicker_cards = [c for c in sorted_cards if c.rank.value == kicker]
        return HandEvaluation(
            category=HandCategory.FOUR_OF_A_KIND,
            score_vector=(HandCategory.FOUR_OF_A_KIND.value, quad_rank, kicker),
            best_cards=tuple(quad_cards + kicker_cards),
            description=f"四条 ({Rank(quad_rank).display_name}, 踢脚 {Rank(kicker).display_name})"
        )

    # 3. Full House (葫芦)
    if freq_sorted[0][1] == 3 and freq_sorted[1][1] == 2:
        trips_rank = freq_sorted[0][0]
        pair_rank = freq_sorted[1][0]
        trips_cards = [c for c in sorted_cards if c.rank.value == trips_rank]
        pair_cards = [c for c in sorted_cards if c.rank.value == pair_rank]
        return HandEvaluation(
            category=HandCategory.FULL_HOUSE,
            score_vector=(HandCategory.FULL_HOUSE.value, trips_rank, pair_rank),
            best_cards=tuple(trips_cards + pair_cards),
            description=f"葫芦 ({Rank(trips_rank).display_name}带{Rank(pair_rank).display_name})"
        )

    # 4. Flush (同花)
    if is_flush:
        return HandEvaluation(
            category=HandCategory.FLUSH,
            score_vector=(HandCategory.FLUSH.value, *ranks),
            best_cards=tuple(sorted_cards),
            description=f"同花 ({sorted_cards[0].suit.display_name}, {Rank(ranks[0]).display_name}高)"
        )

    # 5. Straight (顺子)
    if is_straight:
        if straight_top == 5:
            wheel_sorted = sorted(sorted_cards, key=lambda c: (1 if c.rank == Rank.ACE else c.rank.value), reverse=True)
            return HandEvaluation(
                category=HandCategory.STRAIGHT,
                score_vector=(HandCategory.STRAIGHT.value, 5),
                best_cards=tuple(wheel_sorted),
                description="顺子 (A-2-3-4-5, 5高)"
            )
        return HandEvaluation(
            category=HandCategory.STRAIGHT,
            score_vector=(HandCategory.STRAIGHT.value, straight_top),
            best_cards=tuple(sorted_cards),
            description=f"顺子 ({Rank(straight_top).display_name}高)"
        )

    # 6. Three of a Kind (三条)
    if freq_sorted[0][1] == 3:
        trips_rank = freq_sorted[0][0]
        kickers = [r for r, _ in freq_sorted[1:]]
        trips_cards = [c for c in sorted_cards if c.rank.value == trips_rank]
        kicker_cards = [c for c in sorted_cards if c.rank.value != trips_rank]
        return HandEvaluation(
            category=HandCategory.THREE_OF_A_KIND,
            score_vector=(HandCategory.THREE_OF_A_KIND.value, trips_rank, *kickers),
            best_cards=tuple(trips_cards + kicker_cards),
            description=f"三条 ({Rank(trips_rank).display_name})"
        )

    # 7. Two Pair (两对)
    if freq_sorted[0][1] == 2 and freq_sorted[1][1] == 2:
        high_pair = max(freq_sorted[0][0], freq_sorted[1][0])
        low_pair = min(freq_sorted[0][0], freq_sorted[1][0])
        kicker = freq_sorted[2][0]
        hp_cards = [c for c in sorted_cards if c.rank.value == high_pair]
        lp_cards = [c for c in sorted_cards if c.rank.value == low_pair]
        kicker_cards = [c for c in sorted_cards if c.rank.value == kicker]
        return HandEvaluation(
            category=HandCategory.TWO_PAIR,
            score_vector=(HandCategory.TWO_PAIR.value, high_pair, low_pair, kicker),
            best_cards=tuple(hp_cards + lp_cards + kicker_cards),
            description=f"两对 ({Rank(high_pair).display_name}与{Rank(low_pair).display_name}, 踢脚 {Rank(kicker).display_name})"
        )

    # 8. One Pair (一对)
    if freq_sorted[0][1] == 2:
        pair_rank = freq_sorted[0][0]
        kickers = [r for r, _ in freq_sorted[1:]]
        pair_cards = [c for c in sorted_cards if c.rank.value == pair_rank]
        kicker_cards = [c for c in sorted_cards if c.rank.value != pair_rank]
        return HandEvaluation(
            category=HandCategory.ONE_PAIR,
            score_vector=(HandCategory.ONE_PAIR.value, pair_rank, *kickers),
            best_cards=tuple(pair_cards + kicker_cards),
            description=f"一对 ({Rank(pair_rank).display_name})"
        )

    # 9. High Card (高牌)
    return HandEvaluation(
        category=HandCategory.HIGH_CARD,
        score_vector=(HandCategory.HIGH_CARD.value, *ranks),
        best_cards=tuple(sorted_cards),
        description=f"高牌 ({Rank(ranks[0]).display_name}高)"
    )


def evaluate_hand(cards: Sequence[Card]) -> HandEvaluation:
    """Evaluate 5, 6, or 7 cards and find the best 5-card HandEvaluation.
    
    Exhausts all C(n, 5) combinations to guarantee optimal hand evaluation.
    """
    card_count = len(cards)
    if card_count < 5:
        raise ValueError(f"Hand evaluation requires at least 5 cards, got {card_count}")
    if card_count == 5:
        return evaluate_5_cards(cards)

    best_eval: Optional[HandEvaluation] = None
    for combo in itertools.combinations(cards, 5):
        current_eval = evaluate_5_cards(combo)
        if best_eval is None or current_eval > best_eval:
            best_eval = current_eval

    return best_eval
