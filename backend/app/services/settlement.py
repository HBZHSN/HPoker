"""Texas Hold'em Cash Game Settlement & Minimal Debt Transfer Flow.

Computes exact net cash profit/loss for all participants and generates
the optimal minimal peer-to-peer payment transaction ledger.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class PlayerSettlementRecord:
    player_id: str
    player_name: str
    avatar: str
    rebuy_count: int
    total_buyin_chips: int
    final_chips: int
    net_chips: int
    total_buyin_cash: float
    final_cash: float
    net_cash: float

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "avatar": self.avatar,
            "rebuy_count": self.rebuy_count,
            "total_buyin_chips": self.total_buyin_chips,
            "final_chips": self.final_chips,
            "net_chips": self.net_chips,
            "total_buyin_cash": self.total_buyin_cash,
            "final_cash": self.final_cash,
            "net_cash": self.net_cash,
        }


@dataclass
class PaymentTransaction:
    """Who pays whom and how much cash."""
    from_player_id: str
    from_player_name: str
    to_player_id: str
    to_player_name: str
    amount_cash: float
    amount_chips: int

    def to_dict(self) -> dict:
        return {
            "from_player_id": self.from_player_id,
            "from_player_name": self.from_player_name,
            "to_player_id": self.to_player_id,
            "to_player_name": self.to_player_name,
            "amount_cash": self.amount_cash,
            "amount_chips": self.amount_chips,
            "display": f"{self.from_player_name} 应付给 {self.to_player_name}: ¥{self.amount_cash:.2f} ({self.amount_chips} 筹码)",
        }


@dataclass
class SettlementReport:
    room_id: str
    room_name: str
    buyin_chips: int
    cash_value: float
    chip_to_cash_ratio: float
    player_records: List[PlayerSettlementRecord]
    transactions: List[PaymentTransaction]
    total_chips_in_game: int
    is_balanced: bool
    settlement_type: str = "balance"

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "room_name": self.room_name,
            "buyin_chips": self.buyin_chips,
            "cash_value": self.cash_value,
            "chip_to_cash_ratio": self.chip_to_cash_ratio,
            "player_records": [r.to_dict() for r in self.player_records],
            "transactions": [t.to_dict() for t in self.transactions],
            "total_chips_in_game": self.total_chips_in_game,
            "is_balanced": self.is_balanced,
            "settlement_type": self.settlement_type,
        }


class SettlementEngine:
    """Calculates settlement accounts and minimal transfer graph."""

    @staticmethod
    def simplify_debts(
        net_chips_map: Dict[str, Tuple[str, int]],
        chip_to_cash_ratio: float
    ) -> List[PaymentTransaction]:
        """Greedy minimal transaction transfer simplification.
        
        Args:
            net_chips_map: player_id -> (player_name, net_chips)
            chip_to_cash_ratio: cash per chip
        """
        # Debtors (net_chips < 0): need to pay
        debtors: List[List] = []
        # Creditors (net_chips > 0): need to receive
        creditors: List[List] = []

        for pid, (pname, net_chips) in net_chips_map.items():
            if net_chips < 0:
                debtors.append([pid, pname, -net_chips])  # positive amount owed
            elif net_chips > 0:
                creditors.append([pid, pname, net_chips])

        # Sort descending by amount to optimize matches
        debtors.sort(key=lambda x: x[2], reverse=True)
        creditors.sort(key=lambda x: x[2], reverse=True)

        transactions: List[PaymentTransaction] = []
        d_idx = 0
        c_idx = 0

        while d_idx < len(debtors) and c_idx < len(creditors):
            d_pid, d_pname, d_amt = debtors[d_idx]
            c_pid, c_pname, c_amt = creditors[c_idx]

            transfer_chips = min(d_amt, c_amt)
            if transfer_chips > 0:
                transfer_cash = round(transfer_chips * chip_to_cash_ratio, 2)
                transactions.append(PaymentTransaction(
                    from_player_id=d_pid,
                    from_player_name=d_pname,
                    to_player_id=c_pid,
                    to_player_name=c_pname,
                    amount_cash=transfer_cash,
                    amount_chips=transfer_chips,
                ))

            debtors[d_idx][2] -= transfer_chips
            creditors[c_idx][2] -= transfer_chips

            if debtors[d_idx][2] == 0:
                d_idx += 1
            if creditors[c_idx][2] == 0:
                c_idx += 1

        return transactions

    @classmethod
    def calculate_room_settlement(
        cls,
        room_id: str,
        room_name: str,
        buyin_chips: int,
        cash_value: float,
        player_data_list: List[dict],
        settlement_type: str = "balance",
    ) -> SettlementReport:
        """Calculate complete settlement report for a cash game room.
        
        player_data_list: list of dicts with keys:
            - player_id: str
            - player_name: str
            - rebuy_count: int
            - total_buyin_chips: int
            - final_chips: int
        """
        chip_to_cash_ratio = cash_value / buyin_chips if buyin_chips > 0 else 1.0

        records: List[PlayerSettlementRecord] = []
        net_chips_map: Dict[str, Tuple[str, int]] = {}

        total_buyins = 0
        total_finals = 0

        for p in player_data_list:
            pid = p["player_id"]
            pname = p["player_name"]
            avatar = p.get("avatar") or "👤"
            rebuy_count = p.get("rebuy_count", 1)
            total_buyin = p.get("total_buyin_chips", buyin_chips)
            final_chips = p.get("final_chips", 0)
            net_chips = final_chips - total_buyin

            total_buyins += total_buyin
            total_finals += final_chips

            total_buyin_cash = round(total_buyin * chip_to_cash_ratio, 2)
            final_cash = round(final_chips * chip_to_cash_ratio, 2)
            net_cash = round(net_chips * chip_to_cash_ratio, 2)

            records.append(PlayerSettlementRecord(
                player_id=pid,
                player_name=pname,
                avatar=avatar,
                rebuy_count=rebuy_count,
                total_buyin_chips=total_buyin,
                final_chips=final_chips,
                net_chips=net_chips,
                total_buyin_cash=total_buyin_cash,
                final_cash=final_cash,
                net_cash=net_cash,
            ))

            net_chips_map[pid] = (pname, net_chips)

        # Generate minimal peer-to-peer payment transactions
        transactions = cls.simplify_debts(net_chips_map, chip_to_cash_ratio)

        # Sort records by net_chips descending (winners on top)
        records.sort(key=lambda r: r.net_chips, reverse=True)

        is_balanced = (total_buyins == total_finals)

        return SettlementReport(
            room_id=room_id,
            room_name=room_name,
            buyin_chips=buyin_chips,
            cash_value=cash_value,
            chip_to_cash_ratio=chip_to_cash_ratio,
            player_records=records,
            transactions=transactions,
            total_chips_in_game=total_buyins,
            is_balanced=is_balanced,
            settlement_type=settlement_type,
        )
