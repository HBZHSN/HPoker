"""Texas Hold'em Equity Calculator.

Strategy:
  - **River 1v1 (5 board cards, 1 opponent)**: EXACT enumeration of all C(45,2)=990
    possible opponent holdings. 100% precise, zero noise, instant.
  - **Turn, Flop, Preflop, and Multi-way River**: True multi-opponent Monte Carlo simulation
    where each opponent is dealt distinct cards from the remaining deck, and hero must
    strictly beat all opponents simultaneously to win.
  - **Outs Analysis**: Rigorous classification of Made-Hand Improvements (Flush draws,
    Open-Ended Straights, Double Gutshots, Gutshots, Sets-to-Boats/Quads) with set-union
    deduplication and exact mathematical hit probabilities.
  - **Pot Odds & Action Recommendation**: Mathematically sound pot odds and break-even equity
    thresholds, rational implied odds considerations, avoiding unconditional call traps.
"""

from __future__ import annotations
import itertools
import random
from typing import List, Optional, Dict, Any, Tuple, Set
from collections import Counter

from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.evaluator import evaluate_hand, HandEvaluation, HandCategory, _check_straight


# ----------------- Helpers -----------------

def _full_deck() -> List[Card]:
    return [Card(rank=r, suit=s) for s in Suit for r in Rank]


def _from_notation(notation: str) -> Card:
    """Parse card notation like 'As', 'Th', '2d'."""
    return Card.from_str(notation)


def _parse_request_cards(cards: List[Dict[str, Any]]) -> List[Card]:
    """Convert JSON-serialized card list (backend to_dict format) back to Card objects."""
    result = []
    for c in cards:
        if isinstance(c, Card):
            result.append(c)
            continue
        notation = c.get("notation")
        if notation:
            result.append(Card.from_str(notation))
        elif "rank" in c and "suit" in c:
            result.append(Card(rank=Rank(c["rank"]), suit=Suit(c["suit"])))
    return result


def suit_symbol(suit: Suit) -> str:
    """Return unicode suit symbol for display."""
    map_sym = {
        "SPADES": "♠",
        "HEARTS": "♥",
        "CLUBS": "♣",
        "DIAMONDS": "♦",
    }
    name = str(suit).split(".")[-1] if "." in str(suit) else str(suit)
    return map_sym.get(name, str(suit))


# ----------------- Core Equity Engines -----------------

def _exact_river_1v1(
    hero_hand: List[Card],
    board: List[Card],
    dead: Set[Tuple[int, Suit]],
) -> Tuple[float, float, float]:
    """Exact enumeration of all C(45, 2) = 990 opponent holdings on the river against 1 opponent.

    Returns (win_rate, tie_rate, lose_rate).
    """
    hero_eval = evaluate_hand(hero_hand + board)
    deck_remaining = [c for c in _full_deck() if (c.rank.value, c.suit) not in dead]

    wins = ties = losses = 0
    total = 0

    for opp_combo in itertools.combinations(deck_remaining, 2):
        opp_eval = evaluate_hand(list(opp_combo) + board)
        if hero_eval.score_vector > opp_eval.score_vector:
            wins += 1
        elif hero_eval.score_vector == opp_eval.score_vector:
            ties += 1
        else:
            losses += 1
        total += 1

    return (wins / total, ties / total, losses / total) if total else (0.0, 0.0, 1.0)


def _mc_equity(
    hero_hand: List[Card],
    board: List[Card],
    num_opponents: int,
    dead: Set[Tuple[int, Suit]],
    iterations: int = 600,
) -> Tuple[float, float, float]:
    """True multi-opponent Monte Carlo simulation.

    In every iteration:
      - Remaining community cards (if any) are dealt.
      - Each of the `num_opponents` opponents is dealt 2 distinct cards from the deck.
      - Hero wins only if hero's evaluation strictly beats all opponents.
      - Hero ties if hero ties with the highest opponent and no opponent beats hero.
      - Otherwise, hero loses.

    Returns (win_rate, tie_rate, lose_rate).
    """
    deck_base = [c for c in _full_deck() if (c.rank.value, c.suit) not in dead]
    remaining_board = 5 - len(board)
    num_opponents = max(1, num_opponents)

    cards_needed = remaining_board + 2 * num_opponents
    if len(deck_base) < cards_needed:
        return (0.0, 0.0, 1.0)

    wins = ties = losses = 0
    deck = list(deck_base)
    rng = random.Random()

    for _ in range(iterations):
        rng.shuffle(deck)
        sim_board = list(board)
        if remaining_board > 0:
            sim_board.extend(deck[:remaining_board])

        hero_eval = evaluate_hand(hero_hand + sim_board)

        hero_best = True
        hero_tied = False
        idx = remaining_board

        for _ in range(num_opponents):
            opp = [deck[idx], deck[idx + 1]]
            idx += 2
            opp_eval = evaluate_hand(opp + sim_board)

            if hero_eval.score_vector < opp_eval.score_vector:
                hero_best = False
                break
            elif hero_eval.score_vector == opp_eval.score_vector:
                hero_tied = True

        if hero_best:
            if hero_tied:
                ties += 1
            else:
                wins += 1
        else:
            losses += 1

    total = wins + ties + losses
    return (wins / total, ties / total, losses / total) if total else (0.0, 0.0, 1.0)


def _draw_probabilities(
    hero_hand: List[Card],
    board: List[Card],
    dead: Set[Tuple[int, Suit]],
    mc_iterations: int = 600,
) -> Dict[int, float]:
    """Compute probability of each hand category at river showdown.

    Uses exact enumeration when remaining_board <= 2 (Turn: 46 combos, Flop: 1081 combos).
    Uses Monte Carlo for Preflop (remaining_board == 5).
    """
    remaining = 5 - len(board)
    total = 0
    category_counts: Counter[int] = Counter()
    deck = [c for c in _full_deck() if (c.rank.value, c.suit) not in dead]

    if remaining == 0:
        ev = evaluate_hand(hero_hand + board)
        category_counts[ev.category.value] += 1
        total = 1
    elif remaining <= 2:
        for extra in itertools.combinations(deck, remaining):
            ev = evaluate_hand(hero_hand + list(board) + list(extra))
            category_counts[ev.category.value] += 1
            total += 1
    else:
        rng = random.Random()
        for _ in range(mc_iterations):
            rng.shuffle(deck)
            sim_board = list(board) + deck[:remaining]
            ev = evaluate_hand(hero_hand + sim_board)
            category_counts[ev.category.value] += 1
            total += 1

    return {cat: count / total for cat, count in category_counts.items()}


def _current_hand_eval(hero_hand: List[Card], board: List[Card]) -> Optional[HandEvaluation]:
    all_cards = hero_hand + board
    if len(all_cards) >= 5:
        return evaluate_hand(all_cards)
    return None


# ----------------- Outs Identification -----------------

def _identify_outs(
    hero_hand: List[Card],
    board: List[Card],
    dead: Set[Tuple[int, Suit]],
) -> Optional[Dict[str, Any]]:
    """Identify hero's drawing outs with rigorous poker rules and set deduplication.

    Applicable on Flop (3 board cards) and Turn (4 board cards).
    Returns None on River.
    """
    board_len = len(board)
    if board_len not in (3, 4):
        return None

    current_eval = evaluate_hand(hero_hand + board)
    deck_remaining = [c for c in _full_deck() if (c.rank.value, c.suit) not in dead]

    cats: List[Dict[str, Any]] = []
    all_out_cards: Set[Card] = set()

    # --- 1. Flush Draw ---
    if current_eval.category < HandCategory.FLUSH:
        for suit in Suit:
            hero_suit_count = sum(1 for c in hero_hand if c.suit == suit)
            board_suit_count = sum(1 for c in board if c.suit == suit)
            if hero_suit_count >= 1 and hero_suit_count + board_suit_count == 4:
                flush_outs = {c for c in deck_remaining if c.suit == suit}
                if flush_outs:
                    cats.append({
                        "name": f"{suit_symbol(suit)} 同花听牌",
                        "outs": len(flush_outs),
                        "desc": f"补任意一张 {suit_symbol(suit)} 即成同花",
                    })
                    all_out_cards |= flush_outs

    # --- 2. Straight Draw ---
    if current_eval.category < HandCategory.STRAIGHT:
        straight_cards: Set[Card] = set()
        straight_ranks: Set[Rank] = set()

        for r in Rank:
            r_cards = [c for c in deck_remaining if c.rank == r]
            if not r_cards:
                continue
            hero_ranks_with_r = [c.rank.value for c in hero_hand + board] + [r.value]
            straight_top = _check_straight(hero_ranks_with_r)
            if straight_top is not None:
                board_ranks_with_r = [c.rank.value for c in board] + [r.value]
                board_top = _check_straight(board_ranks_with_r) if len(board_ranks_with_r) >= 5 else None
                if board_top is None or straight_top > board_top:
                    straight_cards.update(r_cards)
                    straight_ranks.add(r)

        if straight_cards:
            all_out_cards |= straight_cards
            sorted_rank_vals = sorted(r.value for r in straight_ranks)

            if len(straight_ranks) == 1:
                name = "卡门顺子"
                target_sym = list(straight_ranks)[0].display_name
                desc = f"内嵌顺子，补一张 {target_sym} 即成顺子"
            elif len(straight_ranks) == 2:
                if sorted_rank_vals[1] - sorted_rank_vals[0] == 5:
                    name = "两头顺子"
                    desc = "两端开放，两头都能成顺"
                else:
                    name = "双卡顺子"
                    syms = "/".join(r.display_name for r in sorted(straight_ranks, key=lambda x: x.value))
                    desc = f"双卡门顺子，补 {syms} 均可成顺"
            else:
                name = "多头顺子"
                desc = "多向顺子听牌"

            cats.append({
                "name": name,
                "outs": len(straight_cards),
                "desc": desc,
            })

    # --- 3. Trips to Full House / Quads ---
    if current_eval.category == HandCategory.THREE_OF_A_KIND:
        boat_quad_cards: Set[Card] = set()
        for c in deck_remaining:
            ev = evaluate_hand(hero_hand + board + [c])
            if ev.category in (HandCategory.FULL_HOUSE, HandCategory.FOUR_OF_A_KIND):
                if len(board) + 1 >= 5:
                    board_ev = evaluate_hand(board + [c])
                    if board_ev.category >= ev.category and ev.score_vector <= board_ev.score_vector:
                        continue
                boat_quad_cards.add(c)
        if boat_quad_cards:
            all_out_cards |= boat_quad_cards
            cats.append({
                "name": "葫芦/四条",
                "outs": len(boat_quad_cards),
                "desc": "补一张同点数牌即成葫芦或四条",
            })

    # --- 4. Two Pair to Full House ---
    elif current_eval.category == HandCategory.TWO_PAIR:
        boat_cards: Set[Card] = set()
        for c in deck_remaining:
            ev = evaluate_hand(hero_hand + board + [c])
            if ev.category == HandCategory.FULL_HOUSE:
                if len(board) + 1 >= 5:
                    board_ev = evaluate_hand(board + [c])
                    if board_ev.category >= ev.category and ev.score_vector <= board_ev.score_vector:
                        continue
                boat_cards.add(c)
        if boat_cards:
            all_out_cards |= boat_cards
            cats.append({
                "name": "葫芦",
                "outs": len(boat_cards),
                "desc": "补一张成对牌即成葫芦",
            })

    # --- 5. Overcards / Pair Improvement (Only shown if no primary draw) ---
    if not cats:
        if current_eval.category == HandCategory.HIGH_CARD:
            board_max_rank = max((c.rank.value for c in board), default=0)
            overcard_ranks = {c.rank.value for c in hero_hand if c.rank.value > board_max_rank}
            if overcard_ranks:
                over_cards = {c for c in deck_remaining if c.rank.value in overcard_ranks}
                if over_cards:
                    all_out_cards |= over_cards
                    syms = "/".join(Rank(r).display_name for r in sorted(overcard_ranks, reverse=True))
                    cats.append({
                        "name": "高牌击中",
                        "outs": len(over_cards),
                        "desc": f"补 {syms} 击中顶对",
                    })
        elif current_eval.category == HandCategory.ONE_PAIR:
            counts = Counter(c.rank.value for c in hero_hand + board)
            pair_rank = next((r for r, cnt in counts.items() if cnt == 2), None)
            if pair_rank is not None:
                hero_kicker_ranks = {c.rank.value for c in hero_hand if c.rank.value != pair_rank}
                improve_cards = {
                    c for c in deck_remaining
                    if c.rank.value == pair_rank or c.rank.value in hero_kicker_ranks
                }
                if improve_cards:
                    all_out_cards |= improve_cards
                    cats.append({
                        "name": "两对/三条",
                        "outs": len(improve_cards),
                        "desc": "补强为更高级两对或暗三条",
                    })

    total_outs = len(all_out_cards)

    # Calculate precise probabilities based on street
    if board_len == 3:  # Flop
        turn_hit_pct: Optional[float] = total_outs / 47.0
        river_hit_pct = 1.0 - ((47.0 - total_outs) / 47.0) * ((46.0 - total_outs) / 46.0)
    else:  # Turn
        turn_hit_pct = None
        river_hit_pct = total_outs / 46.0

    return {
        "categories": cats,
        "total_outs": total_outs,
        "turn_hit_pct": turn_hit_pct,
        "river_hit_pct": max(0.0, min(1.0, river_hit_pct)),
    }


# ----------------- Public API -----------------

STAGE_NAME = {
    "PREFLOP": "翻牌前",
    "FLOP": "翻牌圈",
    "TURN": "转牌圈",
    "RIVER": "河牌圈",
}


def compute_equity(
    hero_cards: List[Card],
    board_cards: List[Card],
    num_opponents: int = 1,
    pot_size: Optional[int] = None,
    to_call: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute poker equity, drawing probabilities, outs, and rational pot odds recommendations.

    Args:
        hero_cards: Exactly 2 hero hole cards.
        board_cards: 0..5 community cards currently visible on table.
        num_opponents: Number of active opponents still in the hand (>= 1).
        pot_size: Current pot total (in chips) — optional, used for pot odds.
        to_call: Chips required to call the current bet — optional, used for pot odds.

    Returns:
        JSON-serializable dictionary with equity, outs, potOdds, currentHand, drawProbabilities.
    """
    if len(hero_cards) != 2:
        return {"error": "需要恰好 2 张手牌"}

    num_opponents = max(1, num_opponents)
    dead: Set[Tuple[int, Suit]] = {(c.rank.value, c.suit) for c in hero_cards}
    dead.update((c.rank.value, c.suit) for c in board_cards)
    board_len = len(board_cards)

    # 1. Equity strategy selection
    if board_len == 5 and num_opponents == 1:
        strategy = "exact"
        win_rate, tie_rate, lose_rate = _exact_river_1v1(hero_cards, board_cards, dead)
    else:
        strategy = "mc"
        win_rate, tie_rate, lose_rate = _mc_equity(
            hero_cards, board_cards, num_opponents, dead, iterations=600
        )

    # 2. Drawing probabilities at river
    draw_dist = _draw_probabilities(hero_cards, board_cards, dead)
    cat_name_map = {
        HandCategory.HIGH_CARD.value: "高牌",
        HandCategory.ONE_PAIR.value: "一对",
        HandCategory.TWO_PAIR.value: "两对",
        HandCategory.THREE_OF_A_KIND.value: "三条",
        HandCategory.STRAIGHT.value: "顺子",
        HandCategory.FLUSH.value: "同花",
        HandCategory.FULL_HOUSE.value: "葫芦",
        HandCategory.FOUR_OF_A_KIND.value: "四条",
        HandCategory.STRAIGHT_FLUSH.value: "同花顺",
        HandCategory.ROYAL_FLUSH.value: "皇家同花顺",
    }
    draw_obj = {
        cat_val: {"pct": prob, "name": cat_name_map.get(cat_val, "?")}
        for cat_val, prob in draw_dist.items()
    }

    # 3. Current hand evaluation
    current_eval = _current_hand_eval(hero_cards, board_cards)

    # 4. Outs analysis (only for Flop and Turn)
    outs = _identify_outs(hero_cards, board_cards, dead)

    # 5. Pot odds & action recommendation
    pot_odds_result = None
    if pot_size is not None and to_call is not None and to_call > 0 and pot_size > 0:
        total_pot = pot_size + to_call
        need_rate = to_call / total_pot
        pot_odds_ratio = pot_size / to_call

        effective_win = win_rate + tie_rate * 0.5
        direct_hit_rate = 0.0
        if outs and outs["total_outs"] > 0:
            direct_hit_rate = (
                outs["turn_hit_pct"] if board_len == 3 and outs["turn_hit_pct"] is not None
                else outs["river_hit_pct"]
            )

        # Rational decision modeling:
        # 1. Effective equity exceeds required break-even equity -> Profitable Call
        if effective_win >= need_rate:
            decision = "call"
            reason = f"当前胜率 {effective_win * 100:.1f}% ≥ 所需底池胜率 {need_rate * 100:.1f}% (赔率划算)"
        # 2. Next-card direct out hit probability exceeds required break-even equity -> Justified Draw Call
        elif direct_hit_rate >= need_rate:
            decision = "call"
            reason = f"直接补牌概率 {direct_hit_rate * 100:.1f}% ≥ 所需胜率 {need_rate * 100:.1f}% (听牌划算)"
        # 3. On Flop with strong draw (outs >= 8) facing a relatively small bet (need_rate <= 0.22) -> Implied Odds Call
        elif board_len == 3 and outs and outs["total_outs"] >= 8 and need_rate <= 0.22:
            decision = "call"
            reason = f"持 {outs['total_outs']} Outs 强听牌，直接成牌率 {direct_hit_rate * 100:.1f}%，虽略逊门槛 {need_rate * 100:.1f}% 但潜在赔率充足"
        # 4. Negative EV -> Fold
        else:
            decision = "fold"
            reason = f"胜率 {effective_win * 100:.1f}% < 所需底池胜率 {need_rate * 100:.1f}% (赔率不划算)"

        pot_odds_result = {
            "pot_size": pot_size,
            "to_call": to_call,
            "total_pot": total_pot,
            "pot_odds_ratio": round(pot_odds_ratio, 2),
            "pot_odds_ratio_str": f"{pot_odds_ratio:.1f}:1",
            "pot_odds_pct": need_rate,
            "need_rate": need_rate,
            "decision": decision,
            "reason": reason,
            "direct_hit_rate": direct_hit_rate,
            "outs_hit_rate_estimate": direct_hit_rate,
        }

    return {
        "stage": ["PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"][min(board_len, 4)],
        "equity": {
            "winRate": win_rate,
            "tieRate": tie_rate,
            "loseRate": lose_rate,
            "strategy": strategy,
        },
        "drawProbabilities": draw_obj,
        "currentHand": {
            "description": current_eval.description if current_eval else None,
            "categoryValue": current_eval.category.value if current_eval else None,
            "categoryName": current_eval.category.display_name if current_eval else None,
        },
        "outs": outs,
        "potOdds": pot_odds_result,
    }


