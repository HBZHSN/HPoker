"""Texas Hold'em Pot & Side Pot Calculation Engine.

Handles:
- Per-round bet tracking & pot accumulation
- Multi-way All-in side pot slicing & eligibility management
- Uncalled bet refunds
- Showdown payout resolution with tie splits and earliest-position odd chip allocation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

from backend.app.engine.evaluator import HandEvaluation


@dataclass
class Pot:
    """Represents a single pot (Main pot or Side pot)."""
    name: str                           # e.g., "主池", "边池 1", "边池 2"
    amount: int                         # Total chips in this pot
    eligible_players: Set[str]          # IDs of players eligible to win this pot

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "amount": self.amount,
            "eligible_players": list(self.eligible_players),
        }


@dataclass
class PotPayout:
    """Represents a payout to a player from a specific pot."""
    player_id: str
    amount: int
    pot_name: str
    hand_description: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "amount": self.amount,
            "pot_name": self.pot_name,
            "hand_description": self.hand_description,
        }


class PotManager:
    """Manages chip contributions, side pots, and showdown distribution."""

    def __init__(self):
        # player_id -> total chips contributed throughout the hand
        self.total_contributions: Dict[str, int] = defaultdict(int)
        # player_id -> chips bet in the current betting round (street)
        self.current_round_bets: Dict[str, int] = defaultdict(int)
        # Set of player_ids who have folded
        self.folded_players: Set[str] = set()

    def reset(self) -> None:
        """Reset pot manager for a new hand."""
        self.total_contributions.clear()
        self.current_round_bets.clear()
        self.folded_players.clear()

    def record_bet(self, player_id: str, amount: int) -> None:
        """Record an additional bet for a player in the current street."""
        if amount <= 0:
            return
        self.current_round_bets[player_id] += amount
        self.total_contributions[player_id] += amount

    def record_fold(self, player_id: str) -> None:
        """Mark a player as folded."""
        self.folded_players.add(player_id)

    def end_betting_round(self) -> None:
        """Clear current street bets for the next street."""
        self.current_round_bets.clear()

    @property
    def total_pot_amount(self) -> int:
        """Sum of all contributions in the hand."""
        return sum(self.total_contributions.values())

    @property
    def current_highest_bet(self) -> int:
        """Highest bet in the current round."""
        return max(self.current_round_bets.values(), default=0)

    def get_player_current_bet(self, player_id: str) -> int:
        """Get the current street bet of a player."""
        return self.current_round_bets.get(player_id, 0)

    def get_player_total_contribution(self, player_id: str) -> int:
        """Get the total hand contribution of a player."""
        return self.total_contributions.get(player_id, 0)

    def calculate_pots(self, is_all_in_dict: Optional[Dict[str, bool]] = None) -> Tuple[List[Pot], Dict[str, int]]:
        """Calculate Main Pot and Side Pots based on all contributions.
        
        Returns:
            (pots, refunds): List of Pots and Dict of player_id -> uncalled refund amount.
        """
        if not self.total_contributions:
            return [], {}

        # Collect all positive contributor IDs
        contributors = {p: amt for p, amt in self.total_contributions.items() if amt > 0}
        if not contributors:
            return [], {}

        # Non-folded active contributors
        active_contributors = {p: amt for p, amt in contributors.items() if p not in self.folded_players}

        # If everyone folded except one player, or 0 active players
        if len(active_contributors) <= 1:
            # Single winner gets the whole pot minus uncalled excess if applicable
            pots: List[Pot] = []
            refunds: Dict[str, int] = {}
            if len(active_contributors) == 1:
                winner_id = next(iter(active_contributors))
                # Check if winner contributed more than the highest folded player
                highest_folded_contrib = max(
                    [amt for p, amt in contributors.items() if p != winner_id],
                    default=0
                )
                winner_contrib = contributors[winner_id]
                if winner_contrib > highest_folded_contrib:
                    refund = winner_contrib - highest_folded_contrib
                    refunds[winner_id] = refund
                    main_pot_amt = self.total_pot_amount - refund
                else:
                    main_pot_amt = self.total_pot_amount

                if main_pot_amt > 0:
                    pots.append(Pot(name="主池", amount=main_pot_amt, eligible_players={winner_id}))
            return pots, refunds

        # Multiple active contributors: calculate tiered pots
        # Get sorted distinct contribution levels of all players
        levels = sorted(set(contributors.values()))
        
        raw_pots: List[Pot] = []
        prev_level = 0
        refunds: Dict[str, int] = {}

        for level in levels:
            tier_diff = level - prev_level
            if tier_diff <= 0:
                continue

            tier_amount = 0
            eligible_for_tier: Set[str] = set()

            for player_id, total_amt in contributors.items():
                if total_amt > prev_level:
                    # Player contributed to this tier
                    contributed_to_tier = min(total_amt - prev_level, tier_diff)
                    tier_amount += contributed_to_tier
                    # Is this player eligible to win this tier? (Must not have folded)
                    if player_id not in self.folded_players:
                        eligible_for_tier.add(player_id)

            if tier_amount > 0:
                if len(eligible_for_tier) == 0:
                    # No active player eligible (all who reached this tier folded)
                    # Merge this amount into previous pot or give to lowest eligible
                    if raw_pots:
                        raw_pots[-1].amount += tier_amount
                elif len(eligible_for_tier) == 1:
                    # Uncalled bet from single active player in this tier -> Refund!
                    refund_player = next(iter(eligible_for_tier))
                    refunds[refund_player] = refunds.get(refund_player, 0) + tier_amount
                else:
                    # Valid pot with 2 or more eligible players
                    raw_pots.append(Pot(
                        name="",
                        amount=tier_amount,
                        eligible_players=eligible_for_tier
                    ))

            prev_level = level

        # Merge adjacent pots that have identical eligible_players
        merged_pots: List[Pot] = []
        for pot in raw_pots:
            if merged_pots and merged_pots[-1].eligible_players == pot.eligible_players:
                merged_pots[-1].amount += pot.amount
            else:
                merged_pots.append(pot)

        # Name the pots: First is "主池", subsequent are "边池 1", "边池 2"...
        for idx, pot in enumerate(merged_pots):
            if idx == 0:
                pot.name = "主池"
            else:
                pot.name = f"边池 {idx}"

        return merged_pots, refunds

    def resolve_showdown(
        self,
        hand_evaluations: Dict[str, HandEvaluation],
        seat_order_from_sb: Sequence[str]
    ) -> List[PotPayout]:
        """Distribute all pots to winning players based on hand evaluations.
        
        Args:
            hand_evaluations: player_id -> HandEvaluation (for all showdown players)
            seat_order_from_sb: list of player_ids starting clockwise from Small Blind (for odd chip rule)
        
        Returns:
            List of PotPayout detailing which player received what amount from which pot.
        """
        pots, refunds = self.calculate_pots()
        payouts: List[PotPayout] = []

        # First add refunds (if any)
        for player_id, refund_amt in refunds.items():
            if refund_amt > 0:
                payouts.append(PotPayout(
                    player_id=player_id,
                    amount=refund_amt,
                    pot_name="多余下注退回"
                ))

        # Distribute each pot (from main pot to side pots)
        for pot in pots:
            if pot.amount <= 0:
                continue

            # Eligible players for this pot who showed down cards
            contenders = [p for p in pot.eligible_players if p in hand_evaluations]
            if not contenders:
                # Fallback: if somehow no evaluations, give to first eligible
                contenders = list(pot.eligible_players)
                if not contenders:
                    continue
                # Split equally
                split_val = pot.amount // len(contenders)
                for c in contenders:
                    payouts.append(PotPayout(player_id=c, amount=split_val, pot_name=pot.name))
                continue

            # Find maximum hand evaluation among contenders
            best_eval: Optional[HandEvaluation] = None
            winners: List[str] = []

            for p in contenders:
                p_eval = hand_evaluations[p]
                if best_eval is None or p_eval > best_eval:
                    best_eval = p_eval
                    winners = [p]
                elif p_eval == best_eval:
                    winners.append(p)

            # Split pot among winners
            winner_count = len(winners)
            share = pot.amount // winner_count
            remainder = pot.amount % winner_count

            # Assign base shares
            winner_payouts: Dict[str, int] = {w: share for w in winners}

            # Distribute odd chips in clockwise seat order from Small Blind
            if remainder > 0:
                ordered_winners = [p for p in seat_order_from_sb if p in winners]
                # If some winner wasn't in seat order, append at end
                for w in winners:
                    if w not in ordered_winners:
                        ordered_winners.append(w)

                for i in range(remainder):
                    winner_payouts[ordered_winners[i]] += 1

            for w, amt in winner_payouts.items():
                if amt > 0:
                    payouts.append(PotPayout(
                        player_id=w,
                        amount=amt,
                        pot_name=pot.name,
                        hand_description=best_eval.description if best_eval else None
                    ))

        return payouts
