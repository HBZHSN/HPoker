"""Texas Hold'em Room Model and Configuration."""

from __future__ import annotations
from dataclasses import dataclass, field
import copy
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
    assistant_win_ratio: float = 0.70  # Ratio of pot won when using equity assistant (0.1 to 1.0)

    def __post_init__(self) -> None:
        if self.small_blind < 1:
            raise ValueError("small_blind must be at least 1")
        if not 2 <= self.max_seats <= 9:
            raise ValueError("max_seats must be between 2 and 9")
        if not (0.1 <= self.assistant_win_ratio <= 1.0):
            raise ValueError("assistant_win_ratio must be between 0.1 and 1.0")
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
            "assistant_win_ratio": self.assistant_win_ratio,
            "assistant_win_pct": int(round(self.assistant_win_ratio * 100)),
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
        self.settlement_type: str = "balance"
        # Explicitly departed players are kept as pending room-level
        # settlements. They are not written to the balance ledger until the
        # host closes the room and chooses a settlement mode.
        self.pending_settlements: List[dict] = []
        # A host kick also prevents the removed account from being auto-seated
        # again by a fresh WebSocket connection to the same room.
        self.kicked_player_ids: set[str] = set()

        # Table state machine
        self.table = TableStateMachine(
            max_seats=config.max_seats,
            small_blind=config.small_blind,
            big_blind=config.big_blind,
            action_timeout=config.action_timeout,
            assistant_win_ratio=config.assistant_win_ratio,
        )

        # Historical participant tracker (player_id -> dict of stats)
        self.historical_players: Dict[str, dict] = {}
        # Durable per-hand accounting checkpoints. Private cards are never
        # included in these records.
        self.hand_records: List[dict] = []
        self._next_test_bot_number = 1

    def record_completed_hand(self) -> bool:
        """Append one chip/buy-in ledger entry for a completed hand."""
        if self.table.street != Street.HAND_END or self.table.hand_number <= 0:
            return False
        if any(r.get("hand_number") == self.table.hand_number for r in self.hand_records):
            return False

        players = []
        active_player_ids = {
            seat.player_id for seat in self.table.active_seated_players
        }
        hand_departure_ids = {
            item.get("player_id")
            for item in self.pending_settlements
            if item.get("hand_number") == self.table.hand_number
        }
        participant_ids = active_player_ids | hand_departure_ids
        for participant in self._build_participant_data():
            if participant["player_id"] not in participant_ids:
                continue
            players.append({
                "player_id": participant["player_id"],
                "player_name": participant["player_name"],
                "seat_index": participant.get("seat_index"),
                "chips": participant["final_chips"],
                "total_buyin_chips": participant["total_buyin_chips"],
                "rebuy_count": participant["rebuy_count"],
            })
        self.hand_records.append({
            "hand_number": self.table.hand_number,
            "settled_at": time.time(),
            "total_chips": sum(player["chips"] for player in players),
            "players": players,
        })
        return True

    def to_checkpoint_dict(self) -> dict:
        """Serialize a restart-safe room checkpoint.

        If a hand is still running, every committed chip is returned to its
        owner in the checkpoint. A restart therefore resumes from the latest
        safe hand boundary instead of reconstructing a partially dealt hand.
        """
        hand_in_progress = self.table.street not in (Street.IDLE, Street.HAND_END)
        contributions = self.table.pot_manager.total_contributions if hand_in_progress else {}
        checkpoint_history = copy.deepcopy(self.historical_players)
        seats = []
        for seat in self.table.seats:
            if seat is None:
                seats.append(None)
                continue
            seats.append({
                "player_id": seat.player_id,
                "name": seat.name,
                "seat_index": seat.seat_index,
                "chips": seat.chips + contributions.get(seat.player_id, 0),
                "avatar": seat.avatar,
                "is_bot": seat.is_bot,
                "is_sitting_out": seat.is_sitting_out,
                "rebuy_count": seat.rebuy_count,
                "total_buyin_chips": seat.total_buyin_chips,
                "time_bank_cards": seat.time_bank_cards,
            })

        # The active hand cannot be reconstructed after a restart. Active
        # players get their current-hand contribution restored in their seat
        # stack above; a player who already left has no seat to receive it, so
        # put that contribution into the persisted safe cash-out snapshot.
        if hand_in_progress:
            seated_ids = {
                seat.player_id for seat in self.table.active_seated_players
            }
            for player_id, contribution in contributions.items():
                if player_id in seated_ids or contribution <= 0:
                    continue
                history = checkpoint_history.get(player_id)
                if history is None:
                    continue
                history["cashed_out_chips"] = int(
                    history.get("cashed_out_chips", history.get("final_chips", 0))
                ) + contribution
                history["final_chips"] = history["cashed_out_chips"]

        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "config": self.config.to_dict(),
            "created_at": self.created_at,
            "historical_players": checkpoint_history,
            "hand_records": self.hand_records,
            "pending_settlements": copy.deepcopy(self.pending_settlements),
            "kicked_player_ids": sorted(self.kicked_player_ids),
            "next_test_bot_number": self._next_test_bot_number,
            "table": {
                "hand_number": self.table.hand_number,
                "dealer_seat": self.table.dealer_seat,
                "seats": seats,
            },
        }

    @classmethod
    def from_checkpoint_dict(cls, data: dict) -> "Room":
        """Restore an active room at a clean between-hands boundary."""
        raw_config = data.get("config", {})
        config = RoomConfig(**{
            key: raw_config[key]
            for key in (
                "room_name", "buyin_chips", "cash_value", "small_blind",
                "action_timeout", "max_seats", "time_card_duration",
                "initial_time_cards", "max_time_cards",
                "time_card_replenish_interval", "assistant_win_ratio",
            )
            if key in raw_config
        })
        room = cls(
            host_player_id=data["host_player_id"],
            config=config,
            room_id=data["room_id"],
        )
        room.created_at = float(data.get("created_at", time.time()))
        room.historical_players = copy.deepcopy(data.get("historical_players", {}))
        for history in room.historical_players.values():
            if "cashed_out_chips" not in history:
                history["cashed_out_chips"] = (
                    history.get("final_chips", 0)
                    if not history.get("is_seated", True)
                    else 0
                )
        room.hand_records = list(data.get("hand_records", []))
        room.pending_settlements = list(data.get("pending_settlements", []))
        room.kicked_player_ids = {
            player_id
            for player_id in data.get("kicked_player_ids", [])
            if isinstance(player_id, str)
        }
        room._next_test_bot_number = int(data.get("next_test_bot_number", 1))

        table_data = data.get("table", {})
        room.table.hand_number = int(table_data.get("hand_number", 0))
        room.table.dealer_seat = int(table_data.get("dealer_seat", 0))
        for seat_data in table_data.get("seats", []):
            if not seat_data:
                continue
            seat_index = int(seat_data["seat_index"])
            if not room.table.sit_down(
                player_id=seat_data["player_id"],
                name=seat_data["name"],
                seat_index=seat_index,
                chips=int(seat_data["chips"]),
                total_buyin=int(seat_data.get("total_buyin_chips", 0)),
                avatar=seat_data.get("avatar", "👤"),
                is_bot=bool(seat_data.get("is_bot", False)),
            ):
                continue
            seat = room.table.seats[seat_index]
            if seat:
                seat.is_sitting_out = bool(seat_data.get("is_sitting_out", False))
                seat.rebuy_count = int(seat_data.get("rebuy_count", 1))
                seat.total_buyin_chips = int(
                    seat_data.get("total_buyin_chips", seat.chips)
                )
                seat.time_bank_cards = int(
                    seat_data.get("time_bank_cards", config.initial_time_cards)
                )

        room.table.street = Street.IDLE
        room.table.current_turn_seat = None
        room.table.turn_started_at = None
        room.table.pot_manager.reset()
        return room

    def add_periodic_time_cards(self) -> int:
        """Add 1 periodic time card to all active seated players up to max_time_cards."""
        if self.is_ended:
            return 0
        return self.table.add_periodic_time_cards(max_cards=self.config.max_time_cards)

    def track_player(
        self,
        player_id: str,
        name: str,
        chips_added: int,
        avatar: str = "👤",
        is_bot: bool = False,
    ) -> None:
        """Record buyin or rebuy for historical accounting."""
        if player_id not in self.historical_players:
            self.historical_players[player_id] = {
                "player_id": player_id,
                "player_name": name,
                "avatar": avatar or "👤",
                "is_bot": is_bot,
                "rebuy_count": 1,
                "total_buyin_chips": chips_added,
                "final_chips": 0,
                "cashed_out_chips": 0,
                "is_seated": True,
            }
        else:
            self.historical_players[player_id]["player_name"] = name
            self.historical_players[player_id]["avatar"] = avatar or "👤"
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
        if self.is_ended or player_id in self.kicked_player_ids:
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
            self.track_player(player_id, name, buyin, avatar=avatar, is_bot=is_bot)
            seat = next(
                (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
                None,
            )
            history = self.historical_players.get(player_id)
            if seat and history:
                seat.rebuy_count = int(history["rebuy_count"])
                seat.total_buyin_chips = int(history["total_buyin_chips"])
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
        if self.is_ended or self.table.street not in (Street.IDLE, Street.HAND_END):
            return False
        buyin = self.config.buyin_chips
        success = self.table.rebuy(player_id, buyin)
        if success:
            if player_id in self.historical_players:
                self.historical_players[player_id]["rebuy_count"] += 1
                self.historical_players[player_id]["total_buyin_chips"] += buyin
        return success

    def _build_participant_data(self) -> List[dict]:
        """Build settlement participants from seated and departed players."""
        seats_by_player = {
            seat.player_id: seat for seat in self.table.active_seated_players
        }
        participants = []
        for player_id, history in self.historical_players.items():
            seat = seats_by_player.get(player_id)
            realized_chips = int(
                history.get("cashed_out_chips", history.get("final_chips", 0))
            )
            participant = dict(history)
            if seat:
                participant.update({
                    "player_name": seat.name,
                    "avatar": seat.avatar,
                    "is_bot": seat.is_bot,
                    "seat_index": seat.seat_index,
                    "rebuy_count": int(history.get("rebuy_count", seat.rebuy_count)),
                    "total_buyin_chips": int(
                        history.get("total_buyin_chips", seat.total_buyin_chips)
                    ),
                    "final_chips": realized_chips + seat.chips,
                })
            else:
                participant["final_chips"] = int(
                    history.get("final_chips", realized_chips)
                )
            participants.append(participant)
        return participants

    def _update_active_final_chips(self) -> None:
        """Refresh historical final stacks without losing prior cash-outs."""
        seats_by_player = {
            seat.player_id: seat for seat in self.table.active_seated_players
        }
        for player_id, seat in seats_by_player.items():
            history = self.historical_players.get(player_id)
            if not history:
                continue
            realized_chips = int(
                history.get("cashed_out_chips", history.get("final_chips", 0))
            )
            history["final_chips"] = realized_chips + seat.chips
            history["is_seated"] = True

    def _record_pending_departure(
        self,
        player,
        reason: str,
        hand_number: Optional[int] = None,
    ) -> None:
        history = self.historical_players.get(player.player_id)
        if history is None:
            return

        realized_chips = int(
            history.get("cashed_out_chips", history.get("final_chips", 0))
        ) + player.chips
        history["cashed_out_chips"] = realized_chips
        history["final_chips"] = realized_chips
        history["is_seated"] = False

        self.pending_settlements.append({
            "player_id": player.player_id,
            "player_name": player.name,
            "avatar": player.avatar,
            "seat_index": player.seat_index,
            "cash_out_chips": player.chips,
            "total_buyin_chips": player.total_buyin_chips,
            "rebuy_count": player.rebuy_count,
            "reason": reason,
            "hand_number": hand_number,
            "status": "pending",
            "created_at": time.time(),
        })

    def stand_up_player(self, seat_index: int, reason: str = "leave") -> Optional[dict]:
        """Stand up a player and retain their cash-out for pending settlement."""
        hand_number = (
            self.table.hand_number
            if self.table.street not in (Street.IDLE, Street.HAND_END)
            else None
        )
        player = self.table.stand_up(seat_index)
        if not player:
            return None
        self._record_pending_departure(player, reason, hand_number=hand_number)
        return player.to_dict()

    def leave_player(self, player_id: str) -> Optional[dict]:
        """Stand up the requesting player, if they currently occupy a seat."""
        seat = next(
            (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
            None,
        )
        if not seat:
            return None
        return self.stand_up_player(seat.seat_index, reason="leave")

    def kick_player(self, player_id: str) -> Optional[dict]:
        """Remove a player by id for a host-initiated kick operation."""
        seat = next(
            (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
            None,
        )
        if not seat:
            return None
        kicked = self.stand_up_player(seat.seat_index, reason="kick")
        if kicked:
            self.kicked_player_ids.add(player_id)
        return kicked

    def is_player_kicked(self, player_id: str) -> bool:
        """Return whether the host has removed this player from the room."""
        return player_id in self.kicked_player_ids

    @property
    def pending_settlement_report(self) -> Optional[SettlementReport]:
        """Return a recalculated, not-yet-recorded settlement preview."""
        if self.is_ended or not any(
            item.get("status", "pending") == "pending"
            for item in self.pending_settlements
        ):
            return None
        return SettlementEngine.calculate_room_settlement(
            room_id=self.room_id,
            room_name=self.config.room_name,
            buyin_chips=self.config.buyin_chips,
            cash_value=self.config.cash_value,
            player_data_list=self._build_participant_data(),
            settlement_type="pending",
        )

    def end_room(
        self,
        requester_id: str,
        settlement_type: str = "balance",
        record_to_balance: bool = True,
    ) -> Optional[SettlementReport]:
        """Host ends the room and calculates final settlements."""
        if requester_id != self.host_player_id:
            return None
        if self.is_ended and self.settlement_report:
            return self.settlement_report
        if settlement_type not in ("balance", "immediate"):
            raise ValueError("settlement_type must be 'balance' or 'immediate'")

        # A room can be closed in the middle of a hand. Return all current
        # hand contributions before taking the settlement snapshot so the
        # chips remain conserved instead of being stranded in an open pot.
        refunded_contributions = self.table.refund_unsettled_hand()
        seated_player_ids = {
            seat.player_id for seat in self.table.active_seated_players
        }
        for player_id, refund in refunded_contributions.items():
            if player_id not in seated_player_ids and player_id in self.historical_players:
                history = self.historical_players[player_id]
                history["cashed_out_chips"] = int(
                    history.get("cashed_out_chips", history.get("final_chips", 0))
                ) + refund
                history["final_chips"] = history["cashed_out_chips"]

        # Update final chips for currently seated players
        self._update_active_final_chips()

        # Prepare participant data list
        participant_data = self._build_participant_data()

        report = SettlementEngine.calculate_room_settlement(
            room_id=self.room_id,
            room_name=self.config.room_name,
            buyin_chips=self.config.buyin_chips,
            cash_value=self.config.cash_value,
            player_data_list=participant_data,
            settlement_type=settlement_type,
        )

        self.is_ended = True
        self.settlement_type = settlement_type
        self.settlement_report = report
        resolved_at = time.time()
        for pending in self.pending_settlements:
            if pending.get("status", "pending") == "pending":
                pending["status"] = "resolved"
                pending["settlement_type"] = settlement_type
                pending["resolved_at"] = resolved_at

        # Automatically record into balance ledger if enabled
        if record_to_balance:
            try:
                from backend.app.services.balance_manager import balance_manager
                balance_manager.record_settlement(report, settlement_type=settlement_type)
            except Exception as e:
                print(f"[Room.end_room] Warning: Failed to record settlement to balance_manager: {e}")

        return report

    def to_dict(self, viewer_player_id: Optional[str] = None) -> dict:
        pending_report = self.pending_settlement_report
        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "config": self.config.to_dict(),
            "is_ended": self.is_ended,
            "settlement_type": getattr(self, "settlement_type", "balance"),
            "table": self.table.get_table_state(viewer_player_id),
            "settlement_report": self.settlement_report.to_dict() if self.settlement_report else None,
            "pending_settlements": copy.deepcopy(self.pending_settlements),
            "pending_settlement_report": (
                pending_report.to_dict() if pending_report else None
            ),
            "recorded_hand_count": len(self.hand_records),
        }
