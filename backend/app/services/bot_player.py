"""Random test-bot decisions for the Texas Hold'em table.

The bot intentionally has no hand-strength strategy.  It only chooses among
the actions that are legal for the current turn, which makes it useful for
exercising table flow without introducing a second rules implementation.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from backend.app.engine.state_machine import ActionType, TableStateMachine


@dataclass(frozen=True)
class BotDecision:
    """A legal action selected for a test bot."""

    action: ActionType
    amount: int = 0


BotChoice = Callable[[Sequence[str]], str]


def choose_bot_action(
    table: TableStateMachine,
    player_id: str,
    chooser: BotChoice = secrets.choice,
) -> Optional[BotDecision]:
    """Choose a random legal Fold, Call, or Bet/Raise action.

    A poker ``Call`` is represented by ``Check`` when there is no amount to
    call.  A post-flop opening bet is still sent as ``RAISE`` in the bot
    protocol; the table engine accepts it as its opening-bet branch when no
    bet exists.

    ``chooser`` is injectable so the decision rules can be tested without
    relying on a particular random result.
    """

    player = next(
        (seat for seat in table.active_seated_players if seat.player_id == player_id),
        None,
    )
    if not player or not player.is_bot:
        return None

    legal = table.get_legal_actions(player_id)
    options: dict[str, BotDecision] = {}

    if legal.can_fold:
        options["fold"] = BotDecision(ActionType.FOLD)

    if legal.can_call:
        options["call"] = BotDecision(ActionType.CALL, legal.call_amount)
    elif legal.can_check:
        # Keep the bot's three-way decision vocabulary while respecting the
        # rules: checking is the no-cost form of calling.
        options["call"] = BotDecision(ActionType.CHECK)

    if legal.can_bet:
        options["raise"] = BotDecision(ActionType.RAISE, legal.min_bet)
    elif legal.can_raise:
        options["raise"] = BotDecision(ActionType.RAISE, legal.min_raise_to)

    if not options:
        return None

    selected = chooser(tuple(options.keys()))
    return options.get(selected, options["fold"])


def execute_bot_action(
    table: TableStateMachine,
    player_id: str,
    chooser: BotChoice = secrets.choice,
) -> Optional[BotDecision]:
    """Apply one random bot decision and return it when the action succeeds."""

    decision = choose_bot_action(table, player_id, chooser=chooser)
    if decision is None:
        return None

    if table.handle_action(player_id, decision.action, raise_total_amount=decision.amount):
        return decision
    return None
