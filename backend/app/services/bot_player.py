"""Equity-based test-bot decisions for the Texas Hold'em table.

The bot uses the equity calculator (compute_equity) to evaluate its win rate,
pot odds, outs, and hand category using strictly the information visible to itself
(own hole cards, visible board cards, active opponent count, pot size, and call amount).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from backend.app.engine.card import Card
from backend.app.engine.equity import compute_equity
from backend.app.engine.state_machine import ActionType, TableStateMachine

logger = logging.getLogger("poker.bot")


@dataclass(frozen=True)
class BotDecision:
    """A legal action selected for a test bot."""

    action: ActionType
    amount: int = 0


BotChoice = Callable[[Sequence[str]], str]
EquityCalculator = Callable[..., dict[str, Any]]


def choose_bot_action(
    table: TableStateMachine,
    player_id: str,
    equity_calculator: EquityCalculator = compute_equity,
    chooser: Optional[BotChoice] = None,
) -> Optional[BotDecision]:
    """Choose a legal action for the bot based on equity calculator results.

    Only information visible to the bot itself is passed into the equity calculator:
      - hero_cards: bot's own hole cards (player.hole_cards)
      - board_cards: visible community cards on the table (table.board_cards)
      - num_opponents: number of other active, non-folded players still in the hand
      - pot_size: current total pot amount (table.pot_manager.total_pot_amount)
      - to_call: chips required to call (legal.call_amount)

    If a legacy `chooser` callable is explicitly passed, the bot falls back to
    options-based selection for backwards compatibility in tests.
    """

    player = next(
        (seat for seat in table.active_seated_players if seat.player_id == player_id),
        None,
    )
    if not player or not player.is_bot:
        return None

    legal = table.get_legal_actions(player_id)

    # Legacy chooser fallback if explicitly requested
    if chooser is not None:
        options: dict[str, BotDecision] = {}
        if legal.can_fold:
            options["fold"] = BotDecision(ActionType.FOLD)
        if legal.can_call:
            options["call"] = BotDecision(ActionType.CALL, legal.call_amount)
        elif legal.can_check:
            options["call"] = BotDecision(ActionType.CHECK)
        if legal.can_bet:
            options["raise"] = BotDecision(ActionType.RAISE, legal.min_bet)
        elif legal.can_raise:
            options["raise"] = BotDecision(ActionType.RAISE, legal.min_raise_to)
        if not options:
            return None
        selected = chooser(tuple(options.keys()))
        return options.get(selected, options.get("fold", next(iter(options.values()))))

    hero_cards: list[Card] = list(player.hole_cards)
    board_cards: list[Card] = list(table.board_cards)
    opponents = [s for s in table.active_in_hand_players if s.player_id != player_id]
    num_opponents = max(1, len(opponents))
    pot_size = table.pot_manager.total_pot_amount
    to_call = legal.call_amount if legal.can_call else 0

    # Defensive fallback if cards are not dealt (e.g. edge-case tests)
    if len(hero_cards) != 2:
        if legal.can_check:
            return BotDecision(ActionType.CHECK)
        if legal.can_call:
            return BotDecision(ActionType.CALL, legal.call_amount)
        if legal.can_fold:
            return BotDecision(ActionType.FOLD)
        return None

    # Compute equity strictly with visible information
    try:
        equity_data = equity_calculator(
            hero_cards=hero_cards,
            board_cards=board_cards,
            num_opponents=num_opponents,
            pot_size=pot_size,
            to_call=to_call,
        )
    except Exception as e:
        logger.exception("Equity calculation failed for bot %s: %s", player_id, e)
        equity_data = {}

    equity_info = equity_data.get("equity") or {}
    win_rate = float(equity_info.get("winRate", 0.0))
    tie_rate = float(equity_info.get("tieRate", 0.0))
    effective_equity = win_rate + tie_rate * 0.5

    pot_odds_info = equity_data.get("potOdds") or {}
    pot_odds_decision = pot_odds_info.get("decision")  # "call" or "fold"

    if (pot_size + to_call) > 0 and to_call > 0:
        need_rate = to_call / (pot_size + to_call)
    else:
        need_rate = 0.0

    outs_info = equity_data.get("outs") or {}
    total_outs = int(outs_info.get("total_outs", 0))

    current_hand = equity_data.get("currentHand") or {}
    category_val = int(current_hand.get("categoryValue") or 1)

    fair_equity = 1.0 / (num_opponents + 1)

    # ----------------- Strategy Decision -----------------

    # Case 1: Facing a bet (to_call > 0, can_call is True, cannot check)
    if to_call > 0 and legal.can_call:
        # A. Strong value raise
        strong_equity = (effective_equity >= 0.70 and effective_equity >= need_rate + 0.20)
        strong_made_hand = (category_val >= 3 and effective_equity >= 0.60)
        dominant_equity = (effective_equity >= max(0.55, fair_equity * 1.80))

        if legal.can_raise and (strong_equity or strong_made_hand or dominant_equity):
            return BotDecision(ActionType.RAISE, legal.min_raise_to)

        # B. Profitable / justified call
        positive_ev = (effective_equity >= need_rate)
        calculator_recommends_call = (pot_odds_decision == "call")
        strong_draw = (total_outs >= 8 and need_rate <= 0.40)
        cheap_odds = (need_rate <= 0.15 and effective_equity >= 0.15)
        small_call = (to_call <= table.big_blind and effective_equity >= 0.30)

        if positive_ev or calculator_recommends_call or strong_draw or cheap_odds or small_call:
            return BotDecision(ActionType.CALL, legal.call_amount)

        # C. Negative expectation -> Fold (or Check if somehow legal)
        if legal.can_check:
            return BotDecision(ActionType.CHECK)
        if legal.can_fold:
            return BotDecision(ActionType.FOLD)
        return BotDecision(ActionType.CALL, legal.call_amount)

    # Case 2: No bet to call (to_call == 0, can_check is True)
    if legal.can_check:
        # Value bet / raise if holding significantly positive advantage
        clear_lead = (effective_equity >= max(0.55, fair_equity * 1.30))
        good_made_hand = (category_val >= 3 and effective_equity >= 0.50)

        if (legal.can_bet or legal.can_raise) and (clear_lead or good_made_hand):
            if legal.can_bet:
                return BotDecision(ActionType.BET, legal.min_bet)
            elif legal.can_raise:
                return BotDecision(ActionType.RAISE, legal.min_raise_to)

        return BotDecision(ActionType.CHECK)

    # Defensive fallback
    if legal.can_check:
        return BotDecision(ActionType.CHECK)
    if legal.can_call:
        return BotDecision(ActionType.CALL, legal.call_amount)
    if legal.can_fold:
        return BotDecision(ActionType.FOLD)
    return None


def execute_bot_action(
    table: TableStateMachine,
    player_id: str,
    equity_calculator: EquityCalculator = compute_equity,
    chooser: Optional[BotChoice] = None,
) -> Optional[BotDecision]:
    """Apply one bot decision and return it when the action succeeds."""

    decision = choose_bot_action(
        table,
        player_id,
        equity_calculator=equity_calculator,
        chooser=chooser,
    )
    if decision is None:
        return None

    if table.handle_action(player_id, decision.action, raise_total_amount=decision.amount):
        return decision
    return None
