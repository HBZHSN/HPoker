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
import time
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
    RIT_DECISION = "RIT_DECISION"
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
    avatar: str = "👤"
    is_bot: bool = False
    hole_cards: List[Card] = field(default_factory=list)
    is_folded: bool = False
    is_all_in: bool = False
    is_sitting_out: bool = False
    rebuy_count: int = 0
    total_buyin_chips: int = 0
    has_acted_this_round: bool = False
    shown_cards: List[Card] = field(default_factory=list)
    last_action: Optional[str] = None
    time_bank_cards: int = 3

    def add_time_bank_card(self, amount: int = 1, max_cards: int = 5) -> bool:
        """Add time bank cards up to max_cards (default 5). Returns True if added."""
        if self.time_bank_cards < max_cards:
            self.time_bank_cards = min(max_cards, self.time_bank_cards + amount)
            return True
        return False

    def use_time_bank_card(self) -> bool:
        """Consume one time bank card. Returns True if successfully consumed."""
        if self.time_bank_cards > 0:
            self.time_bank_cards -= 1
            return True
        return False

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
            "avatar": self.avatar,
            "is_bot": self.is_bot,
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
            "time_bank_cards": self.time_bank_cards,
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
        self.board_cards_2: List[Card] = []
        # Cards that were not dealt before an uncontested hand ended.  They are
        # kept server-side until a player explicitly reveals the final board.
        self.final_board_cards: Optional[List[Card]] = None
        self.final_board_cards_2: Optional[List[Card]] = None
        self.board_cards_revealed: bool = False
        self.hand_number: int = 0

        self.current_round_highest_bet: int = 0
        self.min_raise_increment: int = big_blind
        self.last_raiser_seat: Optional[int] = None

        self.rit_enabled: bool = False
        self.rit_status: Optional[str] = None
        self.rit_votes: Dict[str, int] = {}
        self.rit_voters: List[str] = []
        self.current_dealing_board: int = 1
        self.is_all_in_runout: bool = False
        self.all_in_initial_board_count: int = 0

        self.hand_evaluations: Dict[str, HandEvaluation] = {}
        self.hand_evaluations_2: Dict[str, HandEvaluation] = {}
        self.payouts: List[PotPayout] = []
        self.payouts_1: List[PotPayout] = []
        self.payouts_2: List[PotPayout] = []
        self.last_action_history: List[dict] = []
        self.ready_player_ids: Set[str] = set()
        self.turn_count: int = 0
        self.is_using_time_bank: bool = False
        self.current_turn_duration: int = action_timeout
        # UNIX timestamp used by clients to render a synchronized local
        # countdown between WebSocket state broadcasts.
        self.turn_started_at: Optional[float] = None

    # ----------------- Seat & Player Management -----------------

    def sit_down(
        self,
        player_id: str,
        name: str,
        seat_index: int,
        chips: int,
        total_buyin: int = 0,
        avatar: str = "👤",
        is_bot: bool = False,
    ) -> bool:
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
            time_bank_cards=3,
            avatar=avatar or "👤",
            is_bot=is_bot,
        )
        return True

    def use_time_bank_for_current_player(self) -> bool:
        """Consume 1 time bank card for current active player and extend timer by 30 seconds."""
        if self.current_turn_seat is None:
            return False
        player = self.seats[self.current_turn_seat]
        if not player or player.time_bank_cards <= 0:
            return False
        if player.use_time_bank_card():
            self.is_using_time_bank = True
            self.current_turn_duration = 30
            self.turn_started_at = time.time()
            self.turn_count += 1
            player.last_action = "⏱️ 使用时间卡 +30s"
            return True
        return False

    def add_periodic_time_cards(self, max_cards: int = 5) -> int:
        """Add 1 time bank card to all active seated players up to max_cards."""
        count = 0
        for player in self.active_seated_players:
            if player.add_time_bank_card(1, max_cards=max_cards):
                count += 1
        return count

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

    def refund_unsettled_hand(self) -> Dict[str, int]:
        """Return every chip committed to a hand that has not been settled.

        Ending a cash-game room must not treat chips sitting in an unfinished
        pot as lost money. The room layer uses the returned contribution map
        to update historical records for players who already stood up.
        """
        if self.street in (Street.IDLE, Street.SHOWDOWN, Street.HAND_END):
            return {}

        contributions = dict(self.pot_manager.total_contributions)
        for player in self.active_seated_players:
            refund = contributions.get(player.player_id, 0)
            if refund > 0:
                player.chips += refund
                player.is_all_in = False

        self.pot_manager.reset()
        self.current_turn_seat = None
        self.turn_started_at = None
        self.current_round_highest_bet = 0
        self.min_raise_increment = self.big_blind
        self.last_raiser_seat = None
        self.is_using_time_bank = False
        self.current_turn_duration = self.action_timeout
        self.is_all_in_runout = False
        self.rit_enabled = False
        self.rit_status = None
        self.rit_votes.clear()
        self.rit_voters.clear()
        self.current_dealing_board = 1
        self.all_in_initial_board_count = 0
        self.street = Street.HAND_END
        return contributions

    def rebuy(self, player_id: str, additional_chips: int) -> bool:
        for player in self.active_seated_players:
            if player.player_id == player_id:
                if player.chips > 0:
                    return False
                player.chips += additional_chips
                player.total_buyin_chips += additional_chips
                player.rebuy_count += 1
                player.is_all_in = False
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
        self.board_cards_2.clear()
        self.final_board_cards = None
        self.final_board_cards_2 = None
        self.board_cards_revealed = False
        self.rit_enabled = False
        self.rit_status = None
        self.rit_votes.clear()
        self.rit_voters.clear()
        self.current_dealing_board = 1
        self.is_all_in_runout = False
        self.all_in_initial_board_count = 0
        self.hand_evaluations.clear()
        self.hand_evaluations_2.clear()
        self.payouts.clear()
        self.payouts_1.clear()
        self.payouts_2.clear()
        self.last_action_history.clear()
        self.ready_player_ids.clear()
        self.pot_manager.reset()
        self.deck.reset()
        self.is_using_time_bank = False
        self.current_turn_duration = self.action_timeout
        self.turn_started_at = None

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

        if self.should_trigger_all_in_runout():
            self.setup_all_in_runout()
        else:
            utg_seat = self._find_next_action_seat(self.bb_seat)
            self.current_turn_seat = utg_seat
            self.turn_started_at = time.time() if utg_seat is not None else None
            if self.current_turn_seat is not None:
                self.turn_count += 1
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

            # If target_bet is 0 or unassigned, default to minimum legal bet/raise
            if target_bet <= 0:
                if legal.can_bet:
                    target_bet = legal.min_bet
                elif legal.can_raise:
                    target_bet = legal.min_raise_to
                else:
                    return False

            # Clamp if below minimum legal raise but player has enough chips
            if highest_bet == 0 and target_bet < self.big_blind:
                if current_player.chips >= self.big_blind:
                    target_bet = min(self.big_blind, current_player.chips)
            elif highest_bet > 0:
                min_target = highest_bet + self.min_raise_increment
                if target_bet < min_target:
                    # If player has enough chips to make min raise, clamp up to min_target
                    if curr_round_bet + current_player.chips >= min_target:
                        target_bet = min_target

            added_chips = target_bet - curr_round_bet
            if added_chips <= 0:
                return False

            if added_chips > current_player.chips:
                # Fallback: if all-in
                added_chips = current_player.chips
                target_bet = curr_round_bet + added_chips

            # Room-created games use the small blind as the betting unit. An
            # explicit ALL_IN action remains available for short stacks whose
            # remaining chips are not an exact multiple.
            if added_chips != current_player.chips and target_bet % self.small_blind != 0:
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
            after_seat = self.current_turn_seat if self.current_turn_seat is not None else self.dealer_seat
            self.current_turn_seat = self._find_next_action_seat(after_seat)
            self.is_using_time_bank = False
            self.current_turn_duration = self.action_timeout
            self.turn_started_at = time.time() if self.current_turn_seat is not None else None
            if self.current_turn_seat is not None:
                self.turn_count += 1

    def _advance_street(self) -> None:
        """Advance to next street (Flop, Turn, River, or Showdown)."""
        self.pot_manager.end_betting_round()
        self.current_round_highest_bet = 0
        self.min_raise_increment = self.big_blind
        self.last_raiser_seat = None
        self.is_using_time_bank = False
        self.current_turn_duration = self.action_timeout

        for p in self.active_seated_players:
            p.has_acted_this_round = False

        # Check if 0 or 1 player can still act (others all-in) -> trigger all-in slow runout
        if self.should_trigger_all_in_runout():
            self.setup_all_in_runout()
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
            self.enter_showdown()
            return

        # Set first action player for post-flop streets (first active player after dealer button)
        first_seat = self._find_next_action_seat(self.dealer_seat)
        self.current_turn_seat = first_seat
        self.turn_started_at = time.time() if first_seat is not None else None
        if self.current_turn_seat is not None:
            self.turn_count += 1

    def should_trigger_all_in_runout(self) -> bool:
        """True if betting is complete and all remaining active players are all-in (<=1 player can act)."""
        return len(self.non_allin_active_players) <= 1 and len(self.active_in_hand_players) >= 2

    def setup_all_in_runout(self) -> bool:
        """Setup table for all-in Run-It-Twice choice and slow dealing."""
        if not self.should_trigger_all_in_runout():
            return False

        # Reveal cards of all contenders immediately for drama and excitement
        for p in self.active_in_hand_players:
            p.shown_cards = list(p.hole_cards)

        self.is_all_in_runout = True
        self.all_in_initial_board_count = len(self.board_cards)
        self.current_turn_seat = None
        self.turn_started_at = None

        if len(self.board_cards) < 5:
            # Prompt for RIT decision
            self.street = Street.RIT_DECISION
            self.rit_status = "VOTING"
            self.rit_votes.clear()
            self.rit_voters = [p.player_id for p in self.active_in_hand_players]
            return True
        else:
            # All 5 cards already out on river, directly showdown
            self.enter_showdown()
            return False

    def vote_rit(self, player_id: str, choice: int) -> Tuple[str, bool]:
        """Record player's Run-It-Twice choice (1 or 2).

        Every contender must submit a choice before the runout starts. If
        every choice is 2, Run It Twice is enabled; otherwise the completed
        vote falls back to Run It Once.
        
        Returns:
            (status, is_run_twice): status in ("FINALIZED", "WAITING", "IGNORED")
        """
        if self.street != Street.RIT_DECISION or player_id not in self.rit_voters:
            return ("IGNORED", False)
        if choice not in (1, 2):
            return ("IGNORED", False)

        self.rit_votes[player_id] = choice

        if len(self.rit_votes) < len(self.rit_voters):
            self.rit_status = "VOTING"
            return ("WAITING", False)

        self.rit_enabled = all(vote == 2 for vote in self.rit_votes.values())
        self.rit_status = "AGREED_TWICE" if self.rit_enabled else "AGREED_ONCE"
        return ("FINALIZED", self.rit_enabled)

    def timeout_rit(self) -> bool:
        """Compatibility hook; RIT voting intentionally has no timeout."""
        return False

    def deal_all_in_next_step(self) -> Optional[str]:
        """Deal the next street/card during slow all-in runout.
        
        Returns event description string (e.g. 'FLOP', 'TURN', 'RIVER', 'FLOP_2', 'TURN_2', 'RIVER_2', 'SHOWDOWN') or None.
        """
        if self.current_dealing_board == 1:
            if len(self.board_cards) == 0:
                self.street = Street.FLOP
                self.deck.burn()
                self.board_cards.extend(self.deck.draw(3))
                return "FLOP"
            elif len(self.board_cards) == 3:
                self.street = Street.TURN
                self.deck.burn()
                self.board_cards.append(self.deck.draw_one())
                return "TURN"
            elif len(self.board_cards) == 4:
                self.street = Street.RIVER
                self.deck.burn()
                self.board_cards.append(self.deck.draw_one())
                return "RIVER"
            elif len(self.board_cards) >= 5:
                if self.rit_enabled:
                    self.current_dealing_board = 2
                    self.board_cards_2 = list(self.board_cards[:self.all_in_initial_board_count])
                    return self.deal_all_in_next_step()
                else:
                    return "SHOWDOWN"

        elif self.current_dealing_board == 2:
            if len(self.board_cards_2) == 0:
                self.deck.burn()
                self.board_cards_2.extend(self.deck.draw(3))
                return "FLOP_2"
            elif len(self.board_cards_2) == 3:
                self.deck.burn()
                self.board_cards_2.append(self.deck.draw_one())
                return "TURN_2"
            elif len(self.board_cards_2) == 4:
                self.deck.burn()
                self.board_cards_2.append(self.deck.draw_one())
                return "RIVER_2"
            elif len(self.board_cards_2) >= 5:
                return "SHOWDOWN"

        return None

    def enter_showdown(self) -> None:
        """Evaluate hands for all contenders and distribute pots (supporting 1 or 2 boards)."""
        self.street = Street.SHOWDOWN
        self.current_turn_seat = None
        self.turn_started_at = None

        # A showdown already has a complete public board. Keep a snapshot so
        # the same reveal protocol also works for run-it-twice hands.
        self.final_board_cards = list(self.board_cards)
        self.final_board_cards_2 = list(self.board_cards_2)

        # Auto show hole cards in showdown
        for p in self.active_in_hand_players:
            p.shown_cards = list(p.hole_cards)

        # Get seat order starting from SB for odd chip resolution
        sb_order = [
            p.player_id for p in self._get_players_in_action_order(self.sb_seat)
            if not p.is_folded
        ]

        if not self.rit_enabled:
            evaluations: Dict[str, HandEvaluation] = {}
            for p in self.active_in_hand_players:
                total_cards = p.hole_cards + self.board_cards
                eval_res = evaluate_hand(total_cards)
                evaluations[p.player_id] = eval_res
                self.hand_evaluations[p.player_id] = eval_res

            self.payouts = self.pot_manager.resolve_showdown(
                hand_evaluations=evaluations,
                seat_order_from_sb=sb_order
            )
            for payout in self.payouts:
                player = next((p for p in self.active_seated_players if p.player_id == payout.player_id), None)
                if player:
                    player.chips += payout.amount
        else:
            evaluations_1: Dict[str, HandEvaluation] = {}
            evaluations_2: Dict[str, HandEvaluation] = {}
            for p in self.active_in_hand_players:
                e1 = evaluate_hand(p.hole_cards + self.board_cards)
                e2 = evaluate_hand(p.hole_cards + self.board_cards_2)
                evaluations_1[p.player_id] = e1
                evaluations_2[p.player_id] = e2
                self.hand_evaluations[p.player_id] = e1
                self.hand_evaluations_2[p.player_id] = e2

            p1, p2, combined = self.pot_manager.resolve_showdown_twice(
                hand_evaluations_1=evaluations_1,
                hand_evaluations_2=evaluations_2,
                seat_order_from_sb=sb_order
            )
            self.payouts_1 = p1
            self.payouts_2 = p2
            self.payouts = combined
            for payout in self.payouts:
                player = next((p for p in self.active_seated_players if p.player_id == payout.player_id), None)
                if player:
                    player.chips += payout.amount

        self.street = Street.HAND_END
        self.is_all_in_runout = False
        self.rit_status = "COMPLETED" if self.rit_enabled else None

    def _enter_showdown(self) -> None:
        self.enter_showdown()

    def _fast_forward_to_showdown(self) -> None:
        self.fast_forward_to_showdown()

    def fast_forward_to_showdown(self, run_twice: bool = False) -> None:
        """Synchronously deal remaining cards to showdown (convenient for testing)."""
        if run_twice:
            self.rit_enabled = True
            self.rit_status = "AGREED_TWICE"
            self.current_dealing_board = 1
            self.all_in_initial_board_count = len(self.board_cards)

        while True:
            step = self.deal_all_in_next_step()
            if step == "SHOWDOWN" or step is None:
                break
        self.enter_showdown()

    def _end_hand_uncontested(self) -> None:
        """Single winner takes the pot without revealing hand."""
        self.street = Street.HAND_END
        self.current_turn_seat = None
        self.turn_started_at = None
        self._prepare_final_board_cards()

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

    def _prepare_final_board_cards(self) -> None:
        """Reserve the remaining board cards for an ended uncontested hand.

        The normal dealing order is preserved, including the burn card before
        the flop, turn, and river.  The cards stay private until
        :meth:`reveal_board_cards` is called.
        """
        if self.final_board_cards is not None:
            return

        final_board = list(self.board_cards)
        while len(final_board) < 5:
            self.deck.burn()
            if len(final_board) == 0:
                final_board.extend(self.deck.draw(3))
            else:
                final_board.append(self.deck.draw_one())

        self.final_board_cards = final_board
        self.final_board_cards_2 = list(self.board_cards_2)

    def reveal_board_cards(self) -> bool:
        """Reveal any undealt community cards after the hand has ended."""
        if self.street != Street.HAND_END:
            return False

        self._prepare_final_board_cards()
        self.board_cards_revealed = True
        return True

    def set_player_ready(self, player_id: str, ready: bool = True) -> bool:
        """Mark a player as confirmed/ready for the next hand.
        Returns True if all active eligible seated players are ready.
        """
        if ready:
            self.ready_player_ids.add(player_id)
        else:
            self.ready_player_ids.discard(player_id)

        eligible = [p.player_id for p in self.eligible_hand_players]
        if len(eligible) >= 2 and all(pid in self.ready_player_ids for pid in eligible):
            return True
        return False

    def show_card(
        self,
        player_id: str,
        card_index: Optional[int] = None,
        show_all: bool = False,
        hide_all: bool = False,
        toggle_index: Optional[int] = None,
    ) -> bool:
        """Allow player to reveal or hide cards at the end of the hand."""
        if self.street != Street.HAND_END:
            return False
        player = next((p for p in self.active_seated_players if p.player_id == player_id), None)
        if not player or not player.hole_cards:
            return False

        if hide_all:
            player.shown_cards.clear()
            return True
        elif show_all:
            player.shown_cards = list(player.hole_cards)
            return True
        elif toggle_index is not None and 0 <= toggle_index < len(player.hole_cards):
            card = player.hole_cards[toggle_index]
            if card in player.shown_cards:
                player.shown_cards.remove(card)
            else:
                player.shown_cards.append(card)
            player.shown_cards = [c for c in player.hole_cards if c in player.shown_cards]
            return True
        elif card_index is not None and 0 <= card_index < len(player.hole_cards):
            card = player.hole_cards[card_index]
            if card not in player.shown_cards:
                player.shown_cards.append(card)
            player.shown_cards = [c for c in player.hole_cards if c in player.shown_cards]
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

        # Build hand_results for HAND_END / SHOWDOWN summary
        hand_results = []
        if self.street in (Street.HAND_END, Street.SHOWDOWN):
            for p in self.active_seated_players:
                total_bet = self.pot_manager.get_player_total_bet(p.player_id)
                payout_amt = sum(po.amount for po in self.payouts if po.player_id == p.player_id)
                payout_b1 = sum(po.amount for po in self.payouts_1 if po.player_id == p.player_id)
                payout_b2 = sum(po.amount for po in self.payouts_2 if po.player_id == p.player_id)
                net_profit = payout_amt - total_bet
                hand_desc = "未参与"
                hand_desc_2 = None
                if p.player_id in self.hand_evaluations:
                    eval_obj = self.hand_evaluations[p.player_id]
                    hand_desc = eval_obj.description or eval_obj.category.display_name
                elif payout_amt > 0:
                    matching_po = next((po for po in self.payouts if po.player_id == p.player_id), None)
                    hand_desc = matching_po.hand_description if matching_po and matching_po.hand_description else "获胜"
                elif p.is_folded:
                    hand_desc = "弃牌 (Folded)"
                elif len(p.hole_cards) > 0:
                    hand_desc = "已盖牌"

                if self.rit_enabled and p.player_id in self.hand_evaluations_2:
                    eval_obj_2 = self.hand_evaluations_2[p.player_id]
                    hand_desc_2 = eval_obj_2.description or eval_obj_2.category.display_name

                # Private cards revealed if user is viewer or if player's cards are shown
                show_private = (
                    p.player_id == viewer_player_id
                    or (len(p.shown_cards) > 0 and not p.is_folded)
                )

                hand_results.append({
                    "player_id": p.player_id,
                    "name": p.name,
                    "seat_index": p.seat_index,
                    "total_bet": total_bet,
                    "payout_amount": payout_amt,
                    "payout_board_1": payout_b1,
                    "payout_board_2": payout_b2,
                    "net_profit": net_profit,
                    "chips": p.chips,
                    "is_folded": p.is_folded,
                    "is_winner": payout_amt > 0,
                    "hand_desc": hand_desc,
                    "hand_desc_2": hand_desc_2,
                    "hole_cards": [c.to_dict() for c in p.hole_cards] if (p.player_id == viewer_player_id) else [],
                    "shown_cards": [c.to_dict() for c in p.shown_cards],
                    "is_ready": p.player_id in self.ready_player_ids,
                })

        return {
            "hand_number": self.hand_number,
            "street": self.street.value,
            "board_cards": [c.to_dict() for c in self.board_cards],
            "board_cards_2": [c.to_dict() for c in self.board_cards_2],
            "board_cards_full": (
                [c.to_dict() for c in self.final_board_cards]
                if self.board_cards_revealed and self.final_board_cards is not None
                else []
            ),
            "board_cards_2_full": (
                [c.to_dict() for c in self.final_board_cards_2]
                if self.board_cards_revealed and self.final_board_cards_2 is not None
                else []
            ),
            "board_cards_revealed": self.board_cards_revealed,
            "all_in_initial_board_count": self.all_in_initial_board_count,
            "rit_enabled": self.rit_enabled,
            "rit_status": self.rit_status,
            "rit_votes": dict(self.rit_votes),
            "rit_voters": list(self.rit_voters),
            "current_dealing_board": self.current_dealing_board,
            "is_all_in_runout": self.is_all_in_runout,
            "dealer_seat": self.dealer_seat,
            "sb_seat": self.sb_seat,
            "bb_seat": self.bb_seat,
            "current_turn_seat": self.current_turn_seat,
            "turn_count": self.turn_count,
            "is_using_time_bank": self.is_using_time_bank,
            "current_turn_duration": self.current_turn_duration,
            "turn_started_at": self.turn_started_at,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "current_round_highest_bet": self.current_round_highest_bet,
            "total_pot": self.pot_manager.total_pot_amount,
            "pots": [p.to_dict() for p in pots],
            "seats": [
                {
                    **s.to_dict(include_private_cards=(s.player_id == viewer_player_id)),
                    "current_round_bet": self.pot_manager.get_player_current_bet(s.player_id),
                }
                if s else None
                for s in self.seats
            ],
            "payouts": [p.to_dict() for p in self.payouts],
            "payouts_1": [p.to_dict() for p in self.payouts_1],
            "payouts_2": [p.to_dict() for p in self.payouts_2],
            "legal_actions": self.get_legal_actions(viewer_player_id).to_dict() if viewer_player_id else None,
            "action_history": self.last_action_history[-10:],
            "ready_player_ids": list(self.ready_player_ids),
            "hand_results": hand_results,
        }
