"""Balance and Ledger Data Models."""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional


@dataclass
class ParticipantRecord:
    player_id: str
    username: str
    nickname: str
    avatar: str
    is_test: bool
    rebuy_count: int
    total_buyin_chips: int
    final_chips: int
    net_chips: int
    net_cash: float

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_test": self.is_test,
            "rebuy_count": self.rebuy_count,
            "total_buyin_chips": self.total_buyin_chips,
            "final_chips": self.final_chips,
            "net_chips": self.net_chips,
            "net_cash": round(self.net_cash, 2),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ParticipantRecord:
        return cls(
            player_id=data["player_id"],
            username=data.get("username", data["player_id"]),
            nickname=data.get("nickname", data.get("player_name", "未知玩家")),
            avatar=data.get("avatar", "👤"),
            is_test=bool(data.get("is_test", False)),
            rebuy_count=int(data.get("rebuy_count", 1)),
            total_buyin_chips=int(data.get("total_buyin_chips", 0)),
            final_chips=int(data.get("final_chips", 0)),
            net_chips=int(data.get("net_chips", 0)),
            net_cash=float(data.get("net_cash", 0.0)),
        )


@dataclass
class LedgerEntry:
    entry_id: str
    room_id: str
    room_name: str
    settlement_type: str              # "balance" (记账) or "immediate" (实时转账)
    status: str                       # "unsettled" or "settled"
    created_at: float
    is_test_game: bool
    participants: List[ParticipantRecord]
    transactions: List[dict]
    chip_to_cash_ratio: float
    buyin_chips: int
    cash_value: float
    entry_kind: str = "settlement"       # settlement, buyin, cashout, mode_change
    settled_at: Optional[float] = None
    settled_by: Optional[str] = None
    batch_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "settlement_type": self.settlement_type,
            "status": self.status,
            "created_at": self.created_at,
            "is_test_game": self.is_test_game,
            "participants": [p.to_dict() for p in self.participants],
            "transactions": self.transactions,
            "chip_to_cash_ratio": self.chip_to_cash_ratio,
            "buyin_chips": self.buyin_chips,
            "cash_value": self.cash_value,
            "entry_kind": self.entry_kind,
            "settled_at": self.settled_at,
            "settled_by": self.settled_by,
            "batch_id": self.batch_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LedgerEntry:
        return cls(
            entry_id=data["entry_id"],
            room_id=data["room_id"],
            room_name=data.get("room_name", "德州对局"),
            settlement_type=data.get("settlement_type", "balance"),
            status=data.get("status", "unsettled"),
            created_at=float(data.get("created_at", time.time())),
            is_test_game=bool(data.get("is_test_game", False)),
            participants=[ParticipantRecord.from_dict(p) for p in data.get("participants", [])],
            transactions=list(data.get("transactions", [])),
            chip_to_cash_ratio=float(data.get("chip_to_cash_ratio", 0.1)),
            buyin_chips=int(data.get("buyin_chips", 1000)),
            cash_value=float(data.get("cash_value", 100.0)),
            entry_kind=data.get("entry_kind", "settlement"),
            settled_at=data.get("settled_at"),
            settled_by=data.get("settled_by"),
            batch_id=data.get("batch_id"),
        )


@dataclass
class UserBalanceSummary:
    user_id: str
    username: str
    nickname: str
    avatar: str
    is_test: bool
    net_cash: float
    net_chips: int
    unsettled_games_count: int

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "avatar": self.avatar,
            "is_test": self.is_test,
            "net_cash": round(self.net_cash, 2),
            "net_chips": self.net_chips,
            "unsettled_games_count": self.unsettled_games_count,
        }


@dataclass
class SettlementBatch:
    batch_id: str
    created_at: float
    operator_id: str
    operator_name: str
    total_transferred_cash: float
    user_summaries: List[dict]
    transactions: List[dict]
    entry_ids: List[str]

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "total_transferred_cash": round(self.total_transferred_cash, 2),
            "user_summaries": self.user_summaries,
            "transactions": self.transactions,
            "entry_ids": self.entry_ids,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SettlementBatch:
        return cls(
            batch_id=data["batch_id"],
            created_at=float(data.get("created_at", time.time())),
            operator_id=data.get("operator_id", "admin"),
            operator_name=data.get("operator_name", "管理员"),
            total_transferred_cash=float(data.get("total_transferred_cash", 0.0)),
            user_summaries=list(data.get("user_summaries", [])),
            transactions=list(data.get("transactions", [])),
            entry_ids=list(data.get("entry_ids", [])),
        )
