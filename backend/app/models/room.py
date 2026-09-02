"""Texas Hold'em Room Model and Configuration."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import time
import uuid

from backend.app.engine.state_machine import Street, TableStateMachine
from backend.app.services.settlement import SettlementReport, SettlementEngine


@dataclass
class RoomConfig:
    room_name: str = "HPoker 现金桌"
    buyin_chips: int = 1000
    cash_value: float = 100.0        # e.g., 100 RMB for 1000 chips (0.1 RMB/chip)
    small_blind: int = 10
    # Kept as a compatibility input for older callers. The room rule is always
    # derived from the configured small blind in __post_init__.
    big_blind: Optional[int] = field(default=None, repr=False)
    action_timeout: int = 15          # Seconds to act
    max_seats: int = 6
    time_card_duration: int = 30      # Seconds added per time card
    initial_time_cards: int = 3      # Starting time cards per player
    max_time_cards: int = 5          # Maximum time cards per player
    time_card_replenish_interval: int = 900  # 15 minutes replenishment interval (in seconds)

    def __post_init__(self) -> None:
        if self.small_blind < 1:
            raise ValueError("small_blind must be at least 1")
        self.big_blind = self.small_blind * 2

    def to_dict(self) -> dict:
        return {
            "room_name": self.room_name,
            "buyin_chips": self.buyin_chips,
            "cash_value": self.cash_value,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "action_timeout": self.action_timeout,
            "max_seats": self.max_seats,
            "time_card_duration": self.time_card_duration,
            "initial_time_cards": self.initial_time_cards,
            "max_time_cards": self.max_time_cards,
            "time_card_replenish_interval": self.time_card_replenish_interval,
            "chip_to_cash_ratio": self.cash_value / self.buyin_chips if self.buyin_chips > 0 else 1.0,
        }


class Room:
    """Represents a Texas Hold'em game room."""

    def __init__(self, host_player_id: str, config: RoomConfig, room_id: Optional[str] = None):
        self.room_id = room_id or str(uuid.uuid4())[:8]
        self.host_player_id = host_player_id
        self.config = config
        self.created_at = time.time()
        self.is_ended = False
        self.settlement_report: Optional[SettlementReport] = None

        # Table state machine
        self.table = TableStateMachine(
            max_seats=config.max_seats,
            small_blind=config.small_blind,
            big_blind=config.big_blind,
            action_timeout=config.action_timeout,
        )

        # Historical participant tracker (player_id -> dict of stats)
        self.historical_players: Dict[str, dict] = {}
        self._next_test_bot_number = 1

    def add_periodic_time_cards(self) -> int:
        """Add 1 periodic time card to all active seated players up to max_time_cards."""
        if self.is_ended:
            return 0
        return self.table.add_periodic_time_cards(max_cards=self.config.max_time_cards)

    def track_player(self, player_id: str, name: str, chips_added: int, is_bot: bool = False) -> None:
        """Record buyin or rebuy for historical accounting."""
        if player_id not in self.historical_players:
            self.historical_players[player_id] = {
                "player_id": player_id,
                "player_name": name,
                "is_bot": is_bot,
                "rebuy_count": 1,
                "total_buyin_chips": chips_added,
                "final_chips": 0,
                "is_seated": True,
            }
        else:
            self.historical_players[player_id]["rebuy_count"] += 1
            self.historical_players[player_id]["total_buyin_chips"] += chips_added
            self.historical_players[player_id]["is_seated"] = True

    def sit_down_player(
        self,
        player_id: str,
        name: str,
        seat_index: int,
        avatar: str = "👤",
        is_bot: bool = False,
    ) -> bool:
        """Sit a player down with initial room buy-in."""
        if self.is_ended:
            return False
        buyin = self.config.buyin_chips
        success = self.table.sit_down(
            player_id=player_id,
            name=name,
            seat_index=seat_index,
            chips=buyin,
            total_buyin=buyin,
            avatar=avatar,
            is_bot=is_bot,
        )
        if success:
            self.track_player(player_id, name, buyin, is_bot=is_bot)
        return success

    def add_test_bot(self, seat_index: Optional[int] = None) -> Optional[dict]:
        """Add a virtual test bot to an empty seat between hands."""
        if self.is_ended or self.table.street not in (Street.IDLE, Street.HAND_END):
            return None

        if seat_index is None:
            seat_index = next(
                (idx for idx, seat in enumerate(self.table.seats) if seat is None),
                None,
            )
        if (
            not isinstance(seat_index, int)
            or isinstance(seat_index, bool)
            or not (0 <= seat_index < self.config.max_seats)
        ):
            return None

        bot_id = f"bot_{uuid.uuid4().hex[:10]}"
        bot_name = f"测试机器人 {self._next_test_bot_number}"
        if not self.sit_down_player(
            player_id=bot_id,
            name=bot_name,
            seat_index=seat_index,
            avatar="🤖",
            is_bot=True,
        ):
            return None

        self._next_test_bot_number += 1
        return self.table.seats[seat_index].to_dict() if self.table.seats[seat_index] else None

    def rebuy_player(self, player_id: str) -> bool:
        """Process rebuy for a seated player."""
        if self.is_ended:
            return False
        buyin = self.config.buyin_chips
        success = self.table.rebuy(player_id, buyin)
        if success:
            if player_id in self.historical_players:
                self.historical_players[player_id]["rebuy_count"] += 1
                self.historical_players[player_id]["total_buyin_chips"] += buyin
        return success

    def stand_up_player(self, seat_index: int) -> Optional[dict]:
        """Player stands up and leaves table."""
        player = self.table.stand_up(seat_index)
        if player:
            if player.player_id in self.historical_players:
                self.historical_players[player.player_id]["final_chips"] = player.chips
                self.historical_players[player.player_id]["is_seated"] = False
            return player.to_dict()
        return None

    def end_room(self, requester_id: str) -> Optional[SettlementReport]:
        """Host ends the room and calculates final settlements."""
        if requester_id != self.host_player_id:
            return None
        if self.is_ended and self.settlement_report:
            return self.settlement_report

        # A room can be closed in the middle of a hand. Return all current
        # hand contributions before taking the settlement snapshot so the
        # chips remain conserved instead of being stranded in an open pot.
        refunded_contributions = self.table.refund_unsettled_hand()
        seated_player_ids = {
            seat.player_id for seat in self.table.active_seated_players
        }
        for player_id, refund in refunded_contributions.items():
            if player_id not in seated_player_ids and player_id in self.historical_players:
                self.historical_players[player_id]["final_chips"] += refund

        # Update final chips for currently seated players
        for seat in self.table.active_seated_players:
            if seat.player_id in self.historical_players:
                self.historical_players[seat.player_id]["final_chips"] = seat.chips

        # Prepare participant data list
        participant_data = list(self.historical_players.values())

        report = SettlementEngine.calculate_room_settlement(
            room_id=self.room_id,
            room_name=self.config.room_name,
            buyin_chips=self.config.buyin_chips,
            cash_value=self.config.cash_value,
            player_data_list=participant_data,
        )

        self.is_ended = True
        self.settlement_report = report
        return report

    def to_dict(self, viewer_player_id: Optional[str] = None) -> dict:
        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "config": self.config.to_dict(),
            "is_ended": self.is_ended,
            "table": self.table.get_table_state(viewer_player_id),
            "settlement_report": self.settlement_report.to_dict() if self.settlement_report else None,
        }
