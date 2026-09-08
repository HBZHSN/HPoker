"""Texas Hold'em Room Model and Configuration."""

from __future__ import annotations
from dataclasses import dataclass, field
import copy
from contextlib import contextmanager
import secrets
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
    hands_per_time_card: int = 15     # Reward 1 time card every 15 hands played
    assistant_win_ratio: float = 0.70  # Ratio of positive profit retained when using equity assistant (0.1 to 1.0)

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
            "hands_per_time_card": self.hands_per_time_card,
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
            max_time_cards=config.max_time_cards,
            hands_per_time_card=getattr(config, "hands_per_time_card", 15),
        )

        # Historical participant tracker (player_id -> dict of stats)
        self.historical_players: Dict[str, dict] = {}
        # Durable per-hand accounting checkpoints. Private cards are never
        # included in these records.
        self.hand_records: List[dict] = []
        self._departed_hand_players: Dict[int, List[dict]] = {}
        self._aborted_hand_numbers: set[int] = set()
        self._checkpoint_refund_keys: set[str] = set()
        self.pending_auto_leave_ids: set[str] = set()
        self._next_test_bot_number = 1
        # Real-money stacks are debited when chips enter the table and credited
        # when chips leave it. Test users and bots never touch this wallet.
        self.money_mode: str = "real"
        self.money_mode_epoch: int = 0

    @contextmanager
    def _financial_transaction(self):
        """Rollback room and wallet memory when one financial mutation fails."""
        room_snapshot = self.snapshot_state()
        from backend.app.services.balance_manager import balance_manager

        wallet_snapshot = balance_manager.snapshot_state()
        try:
            yield
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(room_snapshot)
            balance_manager.restore_state(wallet_snapshot)
            raise

    def snapshot_state(self) -> dict:
        """Deep-copy room state while keeping the CSPRNG object live."""
        rng = getattr(self.table.deck, "_rng", None)
        self.table.deck._rng = None
        try:
            snapshot = copy.deepcopy(self.__dict__)
        finally:
            self.table.deck._rng = rng
        snapshot["table"].deck._rng = secrets.SystemRandom()
        return snapshot

    def restore_state(self, snapshot: dict) -> None:
        """Replace the mutable room state with a transaction snapshot."""
        self.__dict__.clear()
        self.__dict__.update(snapshot)

    def record_completed_hand(self) -> Optional[dict]:
        """Build one immutable per-user hand history record at hand end."""
        if self.table.street != Street.HAND_END or self.table.hand_number <= 0:
            return None
        if self.table.hand_number in self._aborted_hand_numbers:
            return None
        if any(r.get("hand_number") == self.table.hand_number for r in self.hand_records):
            return None

        for seat in self.table.active_seated_players:
            if seat.player_id in self.historical_players:
                self.historical_players[seat.player_id]["hands_played"] = seat.hands_played
                self.historical_players[seat.player_id]["time_bank_cards"] = seat.time_bank_cards
                self.historical_players[seat.player_id]["vpip_hands"] = seat.vpip_hands

        player_snapshots = [
            {
                "player_id": seat.player_id,
                "player_name": seat.name,
                "avatar": seat.avatar,
                "seat_index": seat.seat_index,
                "is_test": seat.is_test or seat.is_bot,
                "hole_cards": [card.to_dict() for card in seat.hole_cards],
                "shown_cards": [card.to_dict() for card in seat.shown_cards],
                "ending_chips": seat.chips,
                "is_folded": seat.is_folded,
                "rebuy_count": seat.rebuy_count,
                "total_buyin_chips": seat.total_buyin_chips,
                "time_bank_cards": seat.time_bank_cards,
                "hands_played": seat.hands_played,
                "vpip_hands": seat.vpip_hands,
                "vpip": seat.vpip,
            }
            for seat in self.table.active_seated_players
            if seat.hole_cards
        ]
        player_snapshots.extend(
            self._departed_hand_players.pop(self.table.hand_number, [])
        )

        ratio = self.config.cash_value / self.config.buyin_chips
        players = []
        for snapshot in player_snapshots:
            player_id = snapshot["player_id"]
            contributed = self.table.pot_manager.get_player_total_bet(player_id)
            payout = sum(
                item.amount for item in self.table.payouts if item.player_id == player_id
            )
            ending_chips = int(snapshot["ending_chips"])
            net_chips = payout - contributed
            hand_description = "弃牌" if snapshot.get("is_folded") else "已盖牌"
            evaluation = self.table.hand_evaluations.get(player_id)
            if evaluation:
                hand_description = evaluation.description or evaluation.category.display_name
            else:
                matching_payout = next(
                    (item for item in self.table.payouts if item.player_id == player_id),
                    None,
                )
                if matching_payout and matching_payout.hand_description:
                    hand_description = matching_payout.hand_description

            players.append({
                **snapshot,
                "starting_chips": ending_chips + contributed - payout,
                "contributed_chips": contributed,
                "payout_chips": payout,
                "net_chips": net_chips,
                "net_cash": round(net_chips * ratio, 2) if self.money_mode == "real" else 0.0,
                "hand_description": hand_description,
                "is_winner": net_chips > 0,
            })

        ended_at = time.time()
        detailed_record = {
            "hand_id": f"{self.room_id}:{self.table.hand_number}",
            "room_id": self.room_id,
            "room_name": self.config.room_name,
            "hand_number": self.table.hand_number,
            "ended_at": ended_at,
            "money_mode": self.money_mode,
            "small_blind": self.config.small_blind,
            "big_blind": self.config.big_blind,
            "chip_to_cash_ratio": ratio if self.money_mode == "real" else 0.0,
            "total_pot": sum(self.table.pot_manager.total_contributions.values()),
            "board": [card.to_dict() for card in self.table.board_cards],
            "board_2": [card.to_dict() for card in self.table.board_cards_2],
            "actions": copy.deepcopy(self.table.last_action_history),
            "players": players,
        }
        self.hand_records.append({
            "hand_number": self.table.hand_number,
            "settled_at": ended_at,
            "total_chips": sum(player["ending_chips"] for player in players),
            "players": [
                {
                    "player_id": player["player_id"],
                    "player_name": player["player_name"],
                    "seat_index": player.get("seat_index"),
                    "chips": player["ending_chips"],
                    "total_buyin_chips": player.get("total_buyin_chips", 0),
                    "rebuy_count": player.get("rebuy_count", 0),
                    "net_chips": player["net_chips"],
                }
                for player in players
            ],
        })
        return detailed_record

    def _checkpoint_refund_key(self, player_id: str, hand_number: int) -> str:
        return f"{self.room_id}:hand:{hand_number}:{player_id}:checkpoint_refund"

    def _checkpoint_recovery_refunds(self) -> List[dict]:
        """Describe open-pot contributions belonging to players without seats."""
        if self.table.street in (Street.IDLE, Street.HAND_END):
            return []
        seated_ids = {seat.player_id for seat in self.table.active_seated_players}
        refunds = []
        for player_id, contribution in self.table.pot_manager.total_contributions.items():
            if player_id in seated_ids or contribution <= 0:
                continue
            history = self.historical_players.get(player_id)
            if history is None:
                continue
            key = self._checkpoint_refund_key(player_id, self.table.hand_number)
            if key in self._checkpoint_refund_keys:
                continue
            refunds.append({
                "player_id": player_id,
                "player_name": history.get("player_name", player_id),
                "avatar": history.get("avatar", "👤"),
                "amount": int(contribution),
                "is_bot": bool(history.get("is_bot", False)),
                "is_test": bool(history.get("is_test", False)),
                "wallet_mode": history.get("wallet_mode", "real"),
                "idempotency_key": key,
            })
        return refunds

    def _apply_checkpoint_refund(self, refund: dict, *, update_history: bool = True) -> None:
        """Apply one restart-safe off-table refund exactly once."""
        player_id = refund["player_id"]
        amount = int(refund.get("amount", 0))
        key = refund["idempotency_key"]
        if amount <= 0 or key in self._checkpoint_refund_keys:
            return

        history = self.historical_players.get(player_id)
        if update_history and history is not None:
            history["cashed_out_chips"] = int(
                history.get("cashed_out_chips", history.get("final_chips", 0))
            ) + amount
            history["final_chips"] = history["cashed_out_chips"]
            history["is_seated"] = False

        if refund.get("wallet_mode", "real") == "real" and not refund.get("is_test", False):
            from types import SimpleNamespace

            player = SimpleNamespace(
                player_id=player_id,
                name=refund.get("player_name", player_id),
                avatar=refund.get("avatar", "👤"),
                is_bot=bool(refund.get("is_bot", False)),
                is_test=bool(refund.get("is_test", False)),
            )
            self._record_wallet_change(
                player,
                amount,
                "cashout",
                idempotency_key=key,
            )
        self._checkpoint_refund_keys.add(key)

    def reconcile_checkpoint_refunds(self) -> int:
        """Credit off-table open-pot owners before persisting a checkpoint."""
        refunds = self._checkpoint_recovery_refunds()
        for refund in refunds:
            self._apply_checkpoint_refund(refund)
        return len(refunds)

    def _restore_checkpoint_refunds(self, refunds: List[dict]) -> None:
        """Replay checkpoint refunds after restoring an interrupted room."""
        for refund in refunds:
            if not isinstance(refund, dict) or not refund.get("idempotency_key"):
                continue
            self._apply_checkpoint_refund(refund, update_history=False)

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
                "is_test": seat.is_test,
                "wallet_mode": seat.wallet_mode,
                "is_sitting_out": seat.is_sitting_out,
                "rebuy_count": seat.rebuy_count,
                "total_buyin_chips": seat.total_buyin_chips,
                "time_bank_cards": seat.time_bank_cards,
                "hands_played": seat.hands_played,
                "vpip_hands": seat.vpip_hands,
                "vpip": seat.vpip,
            })

        # The active hand cannot be reconstructed after a restart. Active
        # players get their current-hand contribution restored in their seat
        # stack above; a player who already left has no seat to receive it, so
        # put that contribution into the persisted safe cash-out snapshot.
        recovery_refunds = []
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
                refund_key = self._checkpoint_refund_key(player_id, self.table.hand_number)
                if refund_key in self._checkpoint_refund_keys:
                    continue
                history["cashed_out_chips"] = int(
                    history.get("cashed_out_chips", history.get("final_chips", 0))
                ) + contribution
                history["final_chips"] = history["cashed_out_chips"]
                recovery_refunds.append({
                    "player_id": player_id,
                    "player_name": history.get("player_name", player_id),
                    "avatar": history.get("avatar", "👤"),
                    "amount": int(contribution),
                    "is_bot": bool(history.get("is_bot", False)),
                    "is_test": bool(history.get("is_test", False)),
                    "wallet_mode": history.get("wallet_mode", "real"),
                    "idempotency_key": refund_key,
                })

        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "config": self.config.to_dict(),
            "created_at": self.created_at,
            "historical_players": checkpoint_history,
            "hand_records": self.hand_records,
            "pending_settlements": copy.deepcopy(self.pending_settlements),
            "kicked_player_ids": sorted(self.kicked_player_ids),
            "pending_auto_leave_ids": sorted(self.pending_auto_leave_ids),
            "next_test_bot_number": self._next_test_bot_number,
            "has_bots": self.has_bots,
            "money_mode": self.money_mode,
            "money_mode_epoch": self.money_mode_epoch,
            "checkpoint_refund_keys": sorted(self._checkpoint_refund_keys),
            "recovery_refunds": recovery_refunds,
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
                "time_card_replenish_interval", "hands_per_time_card",
                "assistant_win_ratio",
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
        for player_id, history in room.historical_players.items():
            if "cashed_out_chips" not in history:
                history["cashed_out_chips"] = (
                    history.get("final_chips", 0)
                    if not history.get("is_seated", True)
                    else 0
                )
            history.setdefault(
                "is_test",
                cls._is_test_player(
                    player_id,
                    is_bot=bool(history.get("is_bot", False)),
                ),
            )
            history.setdefault(
                "wallet_mode",
                "play" if history.get("is_test") or history.get("is_bot") else "real",
            )
            history.setdefault("wallet_cashout_count", 0)
        room.hand_records = list(data.get("hand_records", []))
        room.pending_settlements = list(data.get("pending_settlements", []))
        room.kicked_player_ids = {
            player_id
            for player_id in data.get("kicked_player_ids", [])
            if isinstance(player_id, str)
        }
        room.pending_auto_leave_ids = {
            player_id
            for player_id in data.get("pending_auto_leave_ids", [])
            if isinstance(player_id, str)
        }
        room._next_test_bot_number = int(data.get("next_test_bot_number", 1))
        room.money_mode = data.get("money_mode", "real")
        room.money_mode_epoch = int(data.get("money_mode_epoch", 0))
        room._checkpoint_refund_keys = {
            key for key in data.get("checkpoint_refund_keys", [])
            if isinstance(key, str)
        }

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
                is_test=bool(
                    seat_data.get(
                        "is_test",
                        cls._is_test_player(
                            seat_data["player_id"],
                            is_bot=bool(seat_data.get("is_bot", False)),
                        ),
                    )
                ),
                wallet_mode=seat_data.get(
                    "wallet_mode",
                    "play" if bool(seat_data.get("is_test", False)) else room.money_mode,
                ),
                time_bank_cards=int(
                    seat_data.get("time_bank_cards", config.initial_time_cards)
                ),
                hands_played=int(seat_data.get("hands_played", 0)),
                vpip_hands=int(seat_data.get("vpip_hands", 0)),
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
                seat.hands_played = int(seat_data.get("hands_played", 0))
                seat.vpip_hands = int(seat_data.get("vpip_hands", 0))

        room.table.street = Street.IDLE
        room.table.current_turn_seat = None
        room.table.turn_started_at = None
        room.table.pot_manager.reset()
        room._restore_checkpoint_refunds(data.get("recovery_refunds", []))
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
        is_test: bool = False,
        wallet_mode: str = "real",
    ) -> None:
        """Record buyin or rebuy for historical accounting."""
        if player_id not in self.historical_players:
            self.historical_players[player_id] = {
                "player_id": player_id,
                "player_name": name,
                "avatar": avatar or "👤",
                "is_bot": is_bot,
                "is_test": is_test,
                "wallet_mode": wallet_mode if wallet_mode in {"real", "play"} else "real",
                "rebuy_count": 1,
                "total_buyin_chips": chips_added,
                "final_chips": 0,
                "cashed_out_chips": 0,
                "is_seated": True,
                "wallet_cashout_count": 0,
                "hands_played": 0,
                "time_bank_cards": self.config.initial_time_cards,
                "vpip_hands": 0,
            }
        else:
            self.historical_players[player_id]["player_name"] = name
            self.historical_players[player_id]["avatar"] = avatar or "👤"
            self.historical_players[player_id]["rebuy_count"] += 1
            self.historical_players[player_id]["total_buyin_chips"] += chips_added
            self.historical_players[player_id]["is_seated"] = True
            self.historical_players[player_id]["is_test"] = is_test
            self.historical_players[player_id]["wallet_mode"] = (
                wallet_mode if wallet_mode in {"real", "play"} else "real"
            )

    @staticmethod
    def _is_test_player(player_id: str, is_bot: bool = False, is_test: Optional[bool] = None) -> bool:
        if is_bot or player_id.startswith("bot_"):
            return True
        if is_test is not None:
            return bool(is_test)
        from backend.app.services.user_manager import user_manager
        return user_manager.is_test_user(player_id)

    def _record_wallet_change(
        self,
        player,
        chips_delta: int,
        entry_kind: str,
        idempotency_key: Optional[str] = None,
    ) -> None:
        """Persist a real-player table/wallet movement with a stable event key."""
        if chips_delta == 0 or player.is_bot or player.is_test:
            return
        history = self.historical_players.get(player.player_id)
        if history is None:
            return

        if entry_kind == "mode_change":
            sequence = self.money_mode_epoch + 1
            event = "mode_debit" if chips_delta < 0 else "mode_credit"
        elif chips_delta < 0:
            sequence = int(history.get("rebuy_count", player.rebuy_count))
            event = "buyin"
        else:
            sequence = int(history.get("wallet_cashout_count", 0)) + 1
            history["wallet_cashout_count"] = sequence
            event = "cashout"

        from backend.app.services.balance_manager import balance_manager
        balance_manager.record_wallet_change(
            room_id=self.room_id,
            room_name=self.config.room_name,
            player_id=player.player_id,
            player_name=player.name,
            avatar=player.avatar,
            chips_delta=chips_delta,
            buyin_chips=self.config.buyin_chips,
            cash_value=self.config.cash_value,
            entry_kind=entry_kind,
            idempotency_key=idempotency_key or (
                f"{self.room_id}:{player.player_id}:{event}:{sequence}:"
                f"mode:{self.money_mode_epoch}"
            ),
        )

    @property
    def has_active_test_players(self) -> bool:
        """Return whether a seated bot or test account makes hands play-money."""
        return any(
            seat and (seat.is_bot or seat.is_test)
            for seat in self.table.seats
        )

    def sync_money_mode(self) -> bool:
        """Switch table funding at a safe hand boundary.

        Entering play-money credits every real player's current stack first.
        Returning to an all-real table debits the stacks then present. This
        preserves wallet conservation while allowing chips to remain on seats.
        """
        if self.table.street not in (Street.IDLE, Street.HAND_END):
            return False

        desired_mode = "play" if self.has_active_test_players else "real"
        if desired_mode == self.money_mode:
            return True

        entering_play = desired_mode == "play"
        for seat in self.table.active_seated_players:
            if seat.is_bot or seat.is_test:
                continue
            self._record_wallet_change(
                seat,
                seat.chips if entering_play and seat.wallet_mode == "real" else (
                    -seat.chips if not entering_play and seat.wallet_mode == "play" else 0
                ),
                "mode_change",
            )
            if entering_play:
                seat.wallet_mode = "play"
            else:
                seat.wallet_mode = "real"
            history = self.historical_players.get(seat.player_id)
            if history is not None:
                history["wallet_mode"] = seat.wallet_mode

        self.money_mode = desired_mode
        self.money_mode_epoch += 1
        return True

    def prepare_next_hand(self) -> bool:
        """Apply any deferred test/real funding switch before cards are dealt."""
        return self.sync_money_mode()

    def sit_down_player(
        self,
        player_id: str,
        name: str,
        seat_index: int,
        avatar: str = "👤",
        is_bot: bool = False,
        is_test: Optional[bool] = None,
    ) -> bool:
        """Sit a player down with initial room buy-in."""
        with self._financial_transaction():
            return self._sit_down_player(
                player_id=player_id,
                name=name,
                seat_index=seat_index,
                avatar=avatar,
                is_bot=is_bot,
                is_test=is_test,
            )

    def _sit_down_player(
        self,
        player_id: str,
        name: str,
        seat_index: int,
        avatar: str = "👤",
        is_bot: bool = False,
        is_test: Optional[bool] = None,
    ) -> bool:
        """Internal seat mutation executed inside the financial boundary."""
        if self.is_ended or player_id in self.kicked_player_ids:
            return False
        buyin = self.config.buyin_chips
        test_identity = self._is_test_player(player_id, is_bot=is_bot, is_test=is_test)
        wallet_mode = "play" if test_identity or self.money_mode == "play" else "real"
        prev_hands = 0
        prev_cards = self.config.initial_time_cards
        prev_vpip_hands = 0
        if player_id in self.historical_players:
            prev_hands = int(self.historical_players[player_id].get("hands_played", 0))
            prev_cards = int(self.historical_players[player_id].get("time_bank_cards", self.config.initial_time_cards))
            prev_vpip_hands = int(self.historical_players[player_id].get("vpip_hands", 0))

        success = self.table.sit_down(
            player_id=player_id,
            name=name,
            seat_index=seat_index,
            chips=buyin,
            total_buyin=buyin,
            avatar=avatar,
            is_bot=is_bot,
            is_test=test_identity,
            wallet_mode=wallet_mode,
            time_bank_cards=prev_cards,
            hands_played=prev_hands,
            vpip_hands=prev_vpip_hands,
        )
        if success:
            self.track_player(
                player_id,
                name,
                buyin,
                avatar=avatar,
                is_bot=is_bot,
                is_test=test_identity,
                wallet_mode=wallet_mode,
            )
            seat = next(
                (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
                None,
            )
            history = self.historical_players.get(player_id)
            if seat and history:
                if wallet_mode == "real":
                    self._record_wallet_change(seat, -buyin, "buyin")
            self.sync_money_mode()
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
            is_test=True,
        ):
            return None

        self._next_test_bot_number += 1
        return self.table.seats[seat_index].to_dict() if self.table.seats[seat_index] else None

    def rebuy_player(self, player_id: str) -> bool:
        """Process rebuy for a seated player."""
        with self._financial_transaction():
            return self._rebuy_player(player_id)

    def _rebuy_player(self, player_id: str) -> bool:
        """Internal rebuy mutation executed inside the financial boundary."""
        if self.is_ended or self.table.street not in (Street.IDLE, Street.HAND_END):
            return False
        buyin = self.config.buyin_chips
        success = self.table.rebuy(player_id, buyin)
        if success:
            if player_id in self.historical_players:
                self.historical_players[player_id]["rebuy_count"] += 1
                self.historical_players[player_id]["total_buyin_chips"] += buyin
            player = next(
                (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
                None,
            )
            if player and not player.is_bot and not player.is_test and self.money_mode == "real":
                player.wallet_mode = "real"
                self.historical_players[player_id]["wallet_mode"] = "real"
                self._record_wallet_change(player, -buyin, "buyin")
            elif player:
                player.wallet_mode = "play"
                self.historical_players[player_id]["wallet_mode"] = "play"
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
        history["wallet_mode"] = getattr(player, "wallet_mode", history.get("wallet_mode", "real"))
        history["hands_played"] = player.hands_played
        history["time_bank_cards"] = player.time_bank_cards
        history["vpip_hands"] = player.vpip_hands

        if hand_number is not None and player.hole_cards:
            self._departed_hand_players.setdefault(hand_number, []).append({
                "player_id": player.player_id,
                "player_name": player.name,
                "avatar": player.avatar,
                "seat_index": player.seat_index,
                "is_test": player.is_test or player.is_bot,
                "hole_cards": [card.to_dict() for card in player.hole_cards],
                "shown_cards": [card.to_dict() for card in player.shown_cards],
                "ending_chips": player.chips,
                "is_folded": True,
                "rebuy_count": player.rebuy_count,
                "total_buyin_chips": player.total_buyin_chips,
                "time_bank_cards": player.time_bank_cards,
                "hands_played": player.hands_played,
                "vpip_hands": player.vpip_hands,
                "vpip": player.vpip,
            })

        self.pending_settlements.append({
            "player_id": player.player_id,
            "player_name": player.name,
            "avatar": player.avatar,
            "seat_index": player.seat_index,
            "cash_out_chips": player.chips,
            "total_buyin_chips": player.total_buyin_chips,
            "rebuy_count": player.rebuy_count,
            "is_bot": getattr(player, "is_bot", False),
            "is_test": getattr(player, "is_test", False),
            "wallet_mode": getattr(player, "wallet_mode", history.get("wallet_mode", "real")),
            "reason": reason,
            "hand_number": hand_number,
            "status": "credited",
            "created_at": time.time(),
        })
        if getattr(player, "wallet_mode", history.get("wallet_mode", "real")) == "real":
            self._record_wallet_change(player, player.chips, "cashout")

    def stand_up_player(self, seat_index: int, reason: str = "leave") -> Optional[dict]:
        """Stand up a player and retain their cash-out for pending settlement."""
        with self._financial_transaction():
            return self._stand_up_player(seat_index, reason=reason)

    def _stand_up_player(self, seat_index: int, reason: str = "leave") -> Optional[dict]:
        """Internal stand-up mutation executed inside the financial boundary."""
        hand_number = (
            self.table.hand_number
            if self.table.street not in (Street.IDLE, Street.HAND_END)
            else None
        )
        player = self.table.stand_up(seat_index)
        if not player:
            return None
        self._record_pending_departure(player, reason, hand_number=hand_number)
        self.sync_money_mode()
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

    def auto_leave_disconnected_player(self, player_id: str) -> Optional[dict]:
        """Auto-fold/cash out, or defer removal until an all-in hand resolves."""
        departed = self.leave_player(player_id)
        if departed:
            self.pending_auto_leave_ids.discard(player_id)
            return departed

        seat = next(
            (seat for seat in self.table.active_seated_players if seat.player_id == player_id),
            None,
        )
        if seat:
            seat.is_sitting_out = True
            self.pending_auto_leave_ids.add(player_id)
        return None

    def process_pending_auto_leaves(self) -> List[dict]:
        """Remove timed-out all-in players once the current hand is complete."""
        if self.table.street not in (Street.IDLE, Street.HAND_END):
            return []
        departed = []
        for player_id in tuple(self.pending_auto_leave_ids):
            player = self.leave_player(player_id)
            if player:
                departed.append(player)
                self.pending_auto_leave_ids.discard(player_id)
        return departed

    @property
    def has_human_players(self) -> bool:
        return any(seat and not seat.is_bot for seat in self.table.seats)

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

    def _refund_unsettled_hand(self, reason: str) -> Dict[str, int]:
        """Refund an open pot, including contributions from players without seats."""
        hand_was_running = self.table.street not in (Street.IDLE, Street.HAND_END)
        refunded_contributions = self.table.refund_unsettled_hand()
        if hand_was_running:
            self._aborted_hand_numbers.add(self.table.hand_number)
        seated_player_ids = {
            seat.player_id for seat in self.table.active_seated_players
        }
        for player_id, refund in refunded_contributions.items():
            if player_id in seated_player_ids or refund <= 0:
                continue
            history = self.historical_players.get(player_id)
            if history is None:
                continue
            history["cashed_out_chips"] = int(
                history.get("cashed_out_chips", history.get("final_chips", 0))
            ) + refund
            history["final_chips"] = history["cashed_out_chips"]
            history["wallet_mode"] = history.get("wallet_mode", "real")
            if history["wallet_mode"] == "real" and not history.get("is_test", False):
                from types import SimpleNamespace

                departed = SimpleNamespace(
                    player_id=player_id,
                    name=history.get("player_name", player_id),
                    avatar=history.get("avatar", "👤"),
                    rebuy_count=history.get("rebuy_count", 1),
                    is_bot=history.get("is_bot", False),
                    is_test=history.get("is_test", False),
                    wallet_mode="real",
                )
                self._record_wallet_change(
                    departed,
                    refund,
                    "cashout",
                    idempotency_key=(
                        f"{self.room_id}:hand:{self.table.hand_number}:"
                        f"{player_id}:abort_refund"
                    ),
                )
        return refunded_contributions

    def cash_out_all_players(self, reason: str = "room_closed") -> List[dict]:
        """Refund an unfinished hand and return every real stack to its wallet."""
        with self._financial_transaction():
            return self._cash_out_all_players(reason=reason)

    def _cash_out_all_players(self, reason: str = "room_closed") -> List[dict]:
        """Internal room cash-out mutation executed inside the financial boundary."""
        self._refund_unsettled_hand(reason)

        departed_players = []
        for seat in list(self.table.active_seated_players):
            departed = self.stand_up_player(seat.seat_index, reason=reason)
            if departed:
                departed_players.append(departed)
        return departed_players

    @property
    def has_bots(self) -> bool:
        """Return True if any bot is currently seated or has participated in the room."""
        for seat in self.table.seats:
            if seat and (getattr(seat, "is_bot", False) or (isinstance(seat.player_id, str) and seat.player_id.startswith("bot_"))):
                return True
        for pid, history in self.historical_players.items():
            if history.get("is_bot") or (isinstance(pid, str) and pid.startswith("bot_")):
                return True
        for pending in self.pending_settlements:
            pid = pending.get("player_id", "")
            if pending.get("is_bot") or (isinstance(pid, str) and pid.startswith("bot_")):
                return True
        return False

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
        with self._financial_transaction():
            return self._end_room(
                requester_id=requester_id,
                settlement_type=settlement_type,
                record_to_balance=record_to_balance,
            )

    def _end_room(
        self,
        requester_id: str,
        settlement_type: str = "balance",
        record_to_balance: bool = True,
    ) -> Optional[SettlementReport]:
        """Internal room close mutation executed inside the financial boundary."""
        if requester_id != self.host_player_id:
            return None
        if self.is_ended and self.settlement_report:
            return self.settlement_report
        if settlement_type not in ("balance", "immediate"):
            raise ValueError("settlement_type must be 'balance' or 'immediate'")
        # A room can be closed in the middle of a hand. Return all current
        # hand contributions before taking the settlement snapshot so the
        # chips remain conserved instead of being stranded in an open pot.
        self._refund_unsettled_hand(reason="room_ended")

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

        # Each stack has already had every buy-in debited. Closing the room now
        # credits the remaining chips; no second room-level net settlement is
        # written, avoiding duplicate accounting.
        for seat in list(self.table.active_seated_players):
            self.stand_up_player(seat.seat_index, reason="room_ended")

        self.is_ended = True
        self.settlement_type = settlement_type
        self.settlement_report = report
        resolved_at = time.time()
        for pending in self.pending_settlements:
            if pending.get("status", "pending") == "pending":
                pending["status"] = "resolved"
                pending["settlement_type"] = settlement_type
                pending["resolved_at"] = resolved_at

        return report

    def to_dict(self, viewer_player_id: Optional[str] = None) -> dict:
        pending_report = self.pending_settlement_report

        spectators = []
        try:
            from backend.app.websocket.connection_manager import ws_manager
            from backend.app.services.user_manager import user_manager
            seated_ids = {s.player_id for s in self.table.seats if s}
            spectator_ids = ws_manager.get_room_user_ids(self.room_id) - seated_ids
            for uid in sorted(spectator_ids):
                u = user_manager.get_user(uid)
                spectators.append({
                    "user_id": uid,
                    "name": u.nickname if u else f"Spectator_{uid[-4:]}",
                    "avatar": u.avatar if u else "👀",
                })
        except Exception:
            spectators = []

        table_state = self.table.get_table_state(viewer_player_id)
        table_state["spectator_count"] = len(spectators)
        table_state["spectators"] = spectators

        return {
            "room_id": self.room_id,
            "host_player_id": self.host_player_id,
            "config": self.config.to_dict(),
            "is_ended": self.is_ended,
            "has_bots": self.has_bots,
            "money_mode": self.money_mode,
            "has_active_test_players": self.has_active_test_players,
            "settlement_type": getattr(self, "settlement_type", "balance"),
            "table": table_state,
            "spectators": spectators,
            "spectator_count": len(spectators),
            "settlement_report": self.settlement_report.to_dict() if self.settlement_report else None,
            "pending_settlements": copy.deepcopy(self.pending_settlements),
            "pending_settlement_report": (
                pending_report.to_dict() if pending_report else None
            ),
            "recorded_hand_count": len(self.hand_records),
        }
