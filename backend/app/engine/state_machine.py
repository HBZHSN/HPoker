"""Texas Hold'em Table State Machine & Game Flow Engine.

Implements standard No-Limit Texas Hold'em game rules:
- Blind posts (SB, BB) & dealer button rotation
- Full round state progression: Preflop -> Flop -> Turn -> River -> Showdown -> HandEnd
- Turn rotation, action legality validation, and min-raise rules
- Fast-forward dealing on multi-way All-in
- Uncontested pot resolution when all opponents fold
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

from backend.app.engine.card import Card
from backend.app.engine.deck import Deck
from backend.app.engine.evaluator import evaluate_hand, HandEvaluation
from backend.app.engine.pot import PotManager, Pot, PotPayout


class Street(str, Enum):
    IDLE = "IDLE"
    PREFLOP = "PREFLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    SHOWDOWN = "SHOWDOWN"
    HAND_END = "HAND_END"


class ActionType(str, Enum):
    POST_SB = "POST_SB"
    POST_BB = "POST_BB"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"
    FOLD = "FOLD"


@dataclass
class PlayerSeat:
    """Represents a player seated at the poker table."""
    player_id: str
    name: str
    seat_index: int
    chips: int
    hole_cards: List[Card] = field(default_factory=list)
    is_folded: bool = False
    is_all_in: bool = False
    is_sitting_out: bool = False
    rebuy_count: int = 0
    total_buyin_chips: int = 0
    has_acted_this_round: bool = False
    shown_cards: List[Card] = field(default_factory=list)
    last_action: Optional[str] = None

    def reset_for_new_hand(self) -> None:
        self.hole_cards.clear()
        self.is_folded = False
        self.is_all_in = (self.chips == 0)
        self.has_acted_this_round = False
        self.shown_cards.clear()
        self.last_action = None

    def to_dict(self, include_private_cards: bool = True) -> dict:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "seat_index": self.seat_index,
            "chips": self.chips,
            "hole_cards": [c.to_dict() for c in self.hole_cards] if include_private_cards else [],
            "has_cards": len(self.hole_cards) > 0,
            "is_folded": self.is_folded,
            "is_all_in": self.is_all_in,
            "is_sitting_out": self.is_sitting_out,
            "rebuy_count": self.rebuy_count,
            "total_buyin_chips": self.total_buyin_chips,
            "has_acted_this_round": self.has_acted_this_round,
            "shown_cards": [c.to_dict() for c in self.shown_cards],
            "last_action": self.last_action,
        }


@dataclass
class LegalActions:
    can_check: bool = False
    can_call: bool = False
    call_amount: int = 0
    can_bet: bool = False
    min_bet: int = 0
    max_bet: int = 0
    can_raise: bool = False
    min_raise_to: int = 0
    max_raise_to: int = 0
    can_fold: bool = True
    can_all_in: bool = False
    all_in_amount: int = 0

    def to_dict(self) -> dict:
        return {
            "can_check": self.can_check,
            "can_call": self.can_call,
            "call_amount": self.call_amount,
            "can_bet": self.can_bet,
            "min_bet": self.min_bet,
            "max_bet": self.max_bet,
            "can_raise": self.can_raise,
            "min_raise_to": self.min_raise_to,
            "max_raise_to": self.max_raise_to,
            "can_fold": self.can_fold,
            "can_all_in": self.can_all_in,
            "all_in_amount": self.all_in_amount,
        }


class TableStateMachine:
    """Manages full Texas Hold'em game flow and state transitions."""

    def __init__(
        self,
        max_seats: int = 9,
        small_blind: int = 1,
        big_blind: int = 2,
        action_timeout: int = 15,
    ):
        self.max_seats = max_seats
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.action_timeout = action_timeout

        self.seats: List[Optional[PlayerSeat]] = [None] * max_seats
        self.deck = Deck()
        self.pot_manager = PotManager()

        self.dealer_seat: int = 0
        self.sb_seat: int = 0
        self.bb_seat: int = 0
        self.current_turn_seat: Optional[int] = None

        self.street: Street = Street.IDLE
        self.board_cards: List[Card] = []
        self.hand_number: int = 0

        self.current_round_highest_bet: int = 0
        self.min_raise_increment: int = big_blind
        self.last_raiser_seat: Optional[int] = None

        self.hand_evaluations: Dict[str, HandEvaluation] = {}
        self.payouts: List[PotPayout] = []
        self.last_action_history: List[dict] = []

    # ----------------- Seat & Player Management -----------------

    def sit_down(self, player_id: str, name: str, seat_index: int, chips: int, total_buyin: int = 0) -> bool:
        if not (0 <= seat_index < self.max_seats):
            return False
        if self.seats[seat_index] is not None:
            return False
        # Ensure player is not already seated elsewhere
        for s in self.seats:
            if s is not None and s.player_id == player_id:
                return False

        self.seats[seat_index] = PlayerSeat(
            player_id=player_id,
            name=name,
            seat_index=seat_index,
            chips=chips,
            total_buyin_chips=total_buyin or chips,
            rebuy_count=1,
        )
        return True

    def stand_up(self, seat_index: int) -> Optional[PlayerSeat]:
        if 0 <= seat_index < self.max_seats:
            player = self.seats[seat_index]
            if player:
                if self.street not in (Street.IDLE, Street.HAND_END):
                    # Fold if game is in progress
                    if not player.is_folded:
                        self.handle_action(player.player_id, ActionType.FOLD)
                self.seats[seat_index] = None
                return player
        return None

    def rebuy(self, player_id: str, additional_chips: int) -> bool:
        for player in self.active_seated_players:
            if player.player_id == player_id:
                player.chips += additional_chips
                player.total_buyin_chips += additional_chips
                player.rebuy_count += 1
                return True
        return False

    @property
    def active_seated_players(self) -> List[PlayerSeat]:
        """All non-null seated players."""
        return [s for s in self.seats if s is not None]

    @property
    def eligible_hand_players(self) -> List[PlayerSeat]:
        """Seated players who have chips and are not sitting out."""
        return [s for s in self.active_seated_players if s.chips > 0 and not s.is_sitting_out]

    @property
    def active_in_hand_players(self) -> List[PlayerSeat]:
        """Players currently in the active hand (not folded)."""
        return [s for s in self.active_seated_players if not s.is_folded and len(s.hole_cards) > 0]

    @property
    def non_allin_active_players(self) -> List[PlayerSeat]:
        """Active players who can still make betting actions (not folded, not all-in)."""
        return [s for s in self.active_in_hand_players if not s.is_all_in and s.chips > 0]

    # ----------------- Game Flow & Lifecycle -----------------

    def can_start_hand(self) -> bool:
        return len(self.eligible_hand_players) >= 2 and self.street in (Street.IDLE, Street.HAND_END)

    def start_new_hand(self) -> bool:
        if not self.can_start_hand():
            return False

        self.hand_number += 1
        self.board_cards.clear()
        self.hand_evaluations.clear()
        self.payouts.clear()
        self.last_action_history.clear()
        self.pot_manager.reset()
        self.deck.reset()

        # Reset player hand states
        for player in self.active_seated_players:
            if player.chips > 0 and not player.is_sitting_out:
                player.reset_for_new_hand()
            else:
                player.is_folded = True

        # Rotate button and assign SB, BB
        self._rotate_positions()

        # Deal 2 hole cards to each eligible player
        for _ in range(2):
            for p in self._get_players_in_action_order(start_seat=(self.dealer_seat + 1) % self.max_seats):
                if not p.is_folded:
                    p.hole_cards.append(self.deck.draw_one())

        # Post Blinds
        self.street = Street.PREFLOP
        self._post_blinds()

        # Determine first action player for Preflop (Under the Gun / UTG = player after BB)
        self.current_round_highest_bet = self.big_blind
        self.min_raise_increment = self.big_blind

        if len(self.non_allin_active_players) <= 1:
            self._fast_forward_to_showdown()
        else:
            utg_seat = self._find_next_action_seat(self.bb_seat)
            self.current_turn_seat = utg_seat
        return True

    def _rotate_positions(self) -> None:
        eligible_seats = [p.seat_index for p in self.eligible_hand_players]
        if not eligible_seats:
            return

        # Advance dealer button to next eligible seat
        if self.hand_number == 1:
            self.dealer_seat = eligible_seats[0]
        else:
            self.dealer_seat = self._next_eligible_seat(self.dealer_seat, eligible_seats)

        # Heads-up (2 players) rule: Dealer is Small Blind, other player is Big Blind
        if len(eligible_seats) == 2:
            self.sb_seat = self.dealer_seat
            self.bb_seat = self._next_eligible_seat(self.dealer_seat, eligible_seats)
        else:
            # 3+ players: SB is seat after Dealer, BB is seat after SB
            self.sb_seat = self._next_eligible_seat(self.dealer_seat, eligible_seats)
            self.bb_seat = self._next_eligible_seat(self.sb_seat, eligible_seats)

    def _next_eligible_seat(self, current_seat: int, eligible_seats: List[int]) -> int:
        idx = (current_seat + 1) % self.max_seats
        for _ in range(self.max_seats):
            if idx in eligible_seats:
                return idx
            idx = (idx + 1) % self.max_seats
        return eligible_seats[0]

    def _post_blinds(self) -> None:
        # Small Blind
        sb_player = self.seats[self.sb_seat]
        if sb_player:
            sb_amt = min(self.small_blind, sb_player.chips)
            sb_player.chips -= sb_amt
            self.pot_manager.record_bet(sb_player.player_id, sb_amt)
            if sb_player.chips == 0:
                sb_player.is_all_in = True
            sb_player.last_action = f"SB {sb_amt}"
            self._log_action(sb_player.player_id, ActionType.POST_SB, sb_amt)

        # Big Blind
        bb_player = self.seats[self.bb_seat]
        if bb_player:
            bb_amt = min(self.big_blind, bb_player.chips)
            bb_player.chips -= bb_amt
            self.pot_manager.record_bet(bb_player.player_id, bb_amt)
            if bb_player.chips == 0:
                bb_player.is_all_in = True
            bb_player.last_action = f"BB {bb_amt}"
            self._log_action(bb_player.player_id, ActionType.POST_BB, bb_amt)

    def _get_players_in_action_order(self, start_seat: int) -> List[PlayerSeat]:
        """Return list of seated players ordered clockwise starting from start_seat."""
        ordered = []
        idx = start_seat
        for _ in range(self.max_seats):
            p = self.seats[idx]
            if p is not None:
                ordered.append(p)
            idx = (idx + 1) % self.max_seats
        return ordered

    def _find_next_action_seat(self, after_seat: int) -> Optional[int]:
        """Find the next seated active non-all-in player to act clockwise."""
        idx = (after_seat + 1) % self.max_seats
        for _ in range(self.max_seats):
            p = self.seats[idx]
            if p is not None and not p.is_folded and not p.is_all_in and p.chips > 0:
                return idx
            idx = (idx + 1) % self.max_seats
        return None

    # ----------------- Action Legality & Handling -----------------

    def get_legal_actions(self, player_id: str) -> LegalActions:
        player = next((p for p in self.active_seated_players if p.player_id == player_id), None)
        if not player or player.seat_index != self.current_turn_seat or player.is_folded or player.is_all_in:
            return LegalActions()

        curr_round_bet = self.pot_manager.get_player_current_bet(player.player_id)
        highest_bet = self.current_round_highest_bet
        call_cost = highest_bet - curr_round_bet
        chips = player.chips

        la = LegalActions()
        la.can_fold = True

        # Can Check if player has matched the current round bet
        if call_cost == 0:
            la.can_check = True

        # Can Call if there is a higher bet and player has chips
        if call_cost > 0:
            la.can_call = True
            la.call_amount = min(call_cost, chips)

        # Can Bet if no one has bet yet in this round (current_bet == 0)
        if highest_bet == 0:
            if chips > 0:
                la.can_bet = True
                la.min_bet = min(self.big_blind, chips)
                la.max_bet = chips

        # Can Raise if highest_bet > 0 and player has more chips than call_cost
        if highest_bet > 0 and chips > call_cost:
            la.can_raise = True
            # Standard NL min raise is current_bet + min_raise_increment
            min_raise_to = highest_bet + self.min_raise_increment
            la.min_raise_to = min(min_raise_to, curr_round_bet + chips)
            la.max_raise_to = curr_round_bet + chips

        # Can All-in
        if chips > 0:
            la.can_all_in = True
            la.all_in_amount = chips

        return la

    def handle_action(self, player_id: str, action: ActionType, raise_total_amount: int = 0) -> bool:
        """Process player action."""
        if self.street in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END):
            return False

        if self.current_turn_seat is None:
            return False

        current_player = self.seats[self.current_turn_seat]
        if not current_player or current_player.player_id != player_id:
            return False

        legal = self.get_legal_actions(player_id)
        curr_round_bet = self.pot_manager.get_player_current_bet(player_id)
        highest_bet = self.current_round_highest_bet
        call_cost = highest_bet - curr_round_bet

        if action == ActionType.FOLD:
            if not legal.can_fold:
                return False
            current_player.is_folded = True
            current_player.has_acted_this_round = True
            current_player.last_action = "Fold"
            self.pot_manager.record_fold(player_id)
            self._log_action(player_id, ActionType.FOLD, 0)

        elif action == ActionType.CHECK:
            if not legal.can_check:
                return False
            current_player.has_acted_this_round = True
            current_player.last_action = "Check"
            self._log_action(player_id, ActionType.CHECK, 0)

        elif action == ActionType.CALL:
            if not legal.can_call:
                return False
            actual_call = min(call_cost, current_player.chips)
            current_player.chips -= actual_call
            self.pot_manager.record_bet(player_id, actual_call)
            if current_player.chips == 0:
                current_player.is_all_in = True
            current_player.has_acted_this_round = True
            current_player.last_action = f"Call {actual_call}"
            self._log_action(player_id, ActionType.CALL, actual_call)

        elif action in (ActionType.BET, ActionType.RAISE):
            # raise_total_amount is the total target bet for this round
            target_bet = raise_total_amount
            added_chips = target_bet - curr_round_bet
            if added_chips <= 0 or added_chips > current_player.chips:
                # Fallback: if all-in
                if added_chips >= current_player.chips:
                    added_chips = current_player.chips
                    target_bet = curr_round_bet + added_chips
                else:
                    return False

            # Check min-raise rules
            raise_diff = target_bet - highest_bet
            if target_bet < curr_round_bet + current_player.chips:  # If not all-in
                if highest_bet == 0 and target_bet < self.big_blind:
                    return False
                if highest_bet > 0 and raise_diff < self.min_raise_increment:
                    return False

            if raise_diff >= self.min_raise_increment:
                self.min_raise_increment = raise_diff
                self.last_raiser_seat = current_player.seat_index

            current_player.chips -= added_chips
            self.pot_manager.record_bet(player_id, added_chips)
            self.current_round_highest_bet = target_bet

            if current_player.chips == 0:
                current_player.is_all_in = True

            # When someone bets or raises, all other active players must act again
            for p in self.active_in_hand_players:
                if p.player_id != player_id and not p.is_all_in:
                    p.has_acted_this_round = False

            current_player.has_acted_this_round = True
            act_name = "Bet" if highest_bet == 0 else "Raise"
            current_player.last_action = f"{act_name} to {target_bet}"
            self._log_action(player_id, action, target_bet)

        elif action == ActionType.ALL_IN:
            if not legal.can_all_in:
                return False
            allin_chips = current_player.chips
            target_bet = curr_round_bet + allin_chips
            current_player.chips = 0
            current_player.is_all_in = True
            self.pot_manager.record_bet(player_id, allin_chips)

            if target_bet > highest_bet:
                raise_diff = target_bet - highest_bet
                if raise_diff >= self.min_raise_increment:
                    self.min_raise_increment = raise_diff
                    self.last_raiser_seat = current_player.seat_index
                self.current_round_highest_bet = target_bet
                # Re-open action for others
                for p in self.active_in_hand_players:
                    if p.player_id != player_id and not p.is_all_in:
                        p.has_acted_this_round = False

            current_player.has_acted_this_round = True
            current_player.last_action = f"All-In {target_bet}"
            self._log_action(player_id, ActionType.ALL_IN, target_bet)

        else:
            return False

        # Advance to next turn or next round
        self._check_round_completion()
        return True

    def _check_round_completion(self) -> None:
        """Check if round/street is complete, or if single player wins uncontensted."""
        # 1. Uncontested Win check: Only 1 non-folded player left
        if len(self.active_in_hand_players) <= 1:
            self._end_hand_uncontested()
            return

        # 2. Check if all eligible players have matched current bet & acted
        non_allin = self.non_allin_active_players
        all_acted = all(p.has_acted_this_round for p in non_allin)
        all_matched = all(
            self.pot_manager.get_player_current_bet(p.player_id) == self.current_round_highest_bet
            for p in non_allin
        )

        if len(non_allin) == 0 or (all_acted and all_matched):
            # Round is complete!
            self._advance_street()
        else:
            # Advance to next active player
            self.current_turn_seat = self._find_next_action_seat(self.current_turn_seat or self.dealer_seat)

    def _advance_street(self) -> None:
        """Advance to next street (Flop, Turn, River, or Showdown)."""
        self.pot_manager.end_betting_round()
        self.current_round_highest_bet = 0
        self.min_raise_increment = self.big_blind
        self.last_raiser_seat = None

        for p in self.active_seated_players:
            p.has_acted_this_round = False

        # Check if 0 or 1 player can still act (others all-in) -> fast-forward board!
        if len(self.non_allin_active_players) <= 1 and len(self.active_in_hand_players) >= 2:
            self._fast_forward_to_showdown()
            return

        if self.street == Street.PREFLOP:
            self.street = Street.FLOP
            self.deck.burn()
            self.board_cards.extend(self.deck.draw(3))
        elif self.street == Street.FLOP:
            self.street = Street.TURN
            self.deck.burn()
            self.board_cards.append(self.deck.draw_one())
        elif self.street == Street.TURN:
            self.street = Street.RIVER
            self.deck.burn()
            self.board_cards.append(self.deck.draw_one())
        elif self.street == Street.RIVER:
            self._enter_showdown()
            return

        # Set first action player for post-flop streets (first active player after dealer button)
        first_seat = self._find_next_action_seat(self.dealer_seat)
        self.current_turn_seat = first_seat

    def _fast_forward_to_showdown(self) -> None:
        """Deal remaining community cards automatically when players are all-in."""
        while len(self.board_cards) < 5:
            if len(self.board_cards) == 0:
                self.deck.burn()
                self.board_cards.extend(self.deck.draw(3))
            else:
                self.deck.burn()
                self.board_cards.append(self.deck.draw_one())
        self._enter_showdown()

    def _enter_showdown(self) -> None:
        """Evaluate hands for all contenders and distribute pots."""
        self.street = Street.SHOWDOWN
        self.current_turn_seat = None

        # Evaluate hands for all non-folded players
        evaluations: Dict[str, HandEvaluation] = {}
        for p in self.active_in_hand_players:
            total_cards = p.hole_cards + self.board_cards
            eval_res = evaluate_hand(total_cards)
            evaluations[p.player_id] = eval_res
            self.hand_evaluations[p.player_id] = eval_res
            # Auto show hole cards in showdown
            p.shown_cards = list(p.hole_cards)

        # Get seat order starting from SB for odd chip resolution
        sb_order = [
            p.player_id for p in self._get_players_in_action_order(self.sb_seat)
            if not p.is_folded
        ]

        # Calculate and apply payouts
        self.payouts = self.pot_manager.resolve_showdown(
            hand_evaluations=evaluations,
            seat_order_from_sb=sb_order
        )

        for payout in self.payouts:
            player = next((p for p in self.active_seated_players if p.player_id == payout.player_id), None)
            if player:
                player.chips += payout.amount

        self.street = Street.HAND_END

    def _end_hand_uncontested(self) -> None:
        """Single winner takes the pot without revealing hand."""
        self.street = Street.HAND_END
        self.current_turn_seat = None

        winner = self.active_in_hand_players[0] if self.active_in_hand_players else None
        if winner:
            pots, refunds = self.pot_manager.calculate_pots()
            self.payouts.clear()

            # Refunds
            for pid, ref_amt in refunds.items():
                if ref_amt > 0:
                    p = next((p for p in self.active_seated_players if p.player_id == pid), None)
                    if p:
                        p.chips += ref_amt
                    self.payouts.append(PotPayout(player_id=pid, amount=ref_amt, pot_name="多余下注退回"))

            # Pot to winner
            for pot in pots:
                winner.chips += pot.amount
                self.payouts.append(PotPayout(
                    player_id=winner.player_id,
                    amount=pot.amount,
                    pot_name=pot.name,
                    hand_description="其他玩家弃牌获胜"
                ))

    def show_card(self, player_id: str, card_index: Optional[int] = None, show_all: bool = False) -> bool:
        """Allow player to reveal one or all cards at the end of the hand."""
        if self.street != Street.HAND_END:
            return False
        player = next((p for p in self.active_seated_players if p.player_id == player_id), None)
        if not player or not player.hole_cards:
            return False

        if show_all:
            player.shown_cards = list(player.hole_cards)
            return True
        elif card_index is not None and 0 <= card_index < len(player.hole_cards):
            card = player.hole_cards[card_index]
            if card not in player.shown_cards:
                player.shown_cards.append(card)
            return True
        return False

    def _log_action(self, player_id: str, action: ActionType, amount: int) -> None:
        self.last_action_history.append({
            "player_id": player_id,
            "action": action.value,
            "amount": amount,
            "street": self.street.value,
        })

    def get_table_state(self, viewer_player_id: Optional[str] = None) -> dict:
        """Produce full serialized table snapshot for client broadcast."""
        pots, refunds = self.pot_manager.calculate_pots()
        return {
            "hand_number": self.hand_number,
            "street": self.street.value,
            "board_cards": [c.to_dict() for c in self.board_cards],
            "dealer_seat": self.dealer_seat,
            "sb_seat": self.sb_seat,
            "bb_seat": self.bb_seat,
            "current_turn_seat": self.current_turn_seat,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "current_round_highest_bet": self.current_round_highest_bet,
            "total_pot": self.pot_manager.total_pot_amount,
            "pots": [p.to_dict() for p in pots],
            "seats": [
                s.to_dict(include_private_cards=(s.player_id == viewer_player_id or self.street == Street.SHOWDOWN or self.street == Street.HAND_END and len(s.shown_cards) > 0))
                if s else None
                for s in self.seats
            ],
            "payouts": [p.to_dict() for p in self.payouts],
            "legal_actions": self.get_legal_actions(viewer_player_id).to_dict() if viewer_player_id else None,
            "action_history": self.last_action_history[-10:],
        }
