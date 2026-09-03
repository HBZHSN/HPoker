"""Balance and Ledger Management Service.

Handles game settlement recording, user balance aggregation,
minimal debt consolidation across multiple hands/rooms, and batch settlements.
Strictly isolates test accounts and bot matches to prevent contaminating real balances.
"""

from __future__ import annotations
import json
import os
import time
from typing import Dict, List, Optional, Tuple
import uuid

from backend.app.models.balance import (
    ParticipantRecord,
    LedgerEntry,
    UserBalanceSummary,
    SettlementBatch,
)
from backend.app.services.settlement import SettlementEngine, PaymentTransaction, SettlementReport
from backend.app.services.user_manager import user_manager, UserManager

DEFAULT_BALANCE_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "balance_ledger.json",
)


class BalanceManager:
    """Manages balance ledgers, batch debt settlement, and test-data isolation."""

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is not None:
            self.storage_path = storage_path
        else:
            self.storage_path = os.environ.get("BALANCE_DATA_FILE", DEFAULT_BALANCE_STORAGE_FILE)

        self._entries: Dict[str, LedgerEntry] = {}
        self._batches: Dict[str, SettlementBatch] = {}
        self.load_from_storage()

    def load_from_storage(self) -> None:
        """Load ledger entries and settlement batches from JSON storage."""
        self._entries.clear()
        self._batches.clear()

        if not self.storage_path or self.storage_path == ":memory:":
            return

        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for e_data in data.get("entries", []):
                        entry = LedgerEntry.from_dict(e_data)
                        self._entries[entry.entry_id] = entry
                    for b_data in data.get("batches", []):
                        batch = SettlementBatch.from_dict(b_data)
                        self._batches[batch.batch_id] = batch
            except Exception as e:
                print(f"[BalanceManager] Warning: Failed to load balance storage from {self.storage_path}: {e}")

    def save_to_storage(self) -> None:
        """Persist ledger entries and settlement batches to JSON storage."""
        if not self.storage_path or self.storage_path == ":memory:":
            return

        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.storage_path)), exist_ok=True)
            payload = {
                "entries": [e.to_dict() for e in self._entries.values()],
                "batches": [b.to_dict() for b in self._batches.values()],
            }
            tmp_path = f"{self.storage_path}.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.storage_path)
        except Exception as e:
            print(f"[BalanceManager] Warning: Failed to save balance storage to {self.storage_path}: {e}")

    def record_settlement(
        self,
        report: SettlementReport,
        settlement_type: str = "balance",
        u_mgr: Optional[UserManager] = None,
    ) -> LedgerEntry:
        """Record a completed room's settlement report into ledger.

        Args:
            report: The computed SettlementReport
            settlement_type: "balance" (record to balance) or "immediate" (settled on spot)
            u_mgr: User manager to inspect user flags
        """
        mgr = u_mgr or user_manager
        entry_id = f"entry_{uuid.uuid4().hex[:10]}"
        now = time.time()

        participants: List[ParticipantRecord] = []
        is_test_game = False

        for rec in report.player_records:
            pid = rec.player_id
            is_bot = pid.startswith("bot_")
            is_test = is_bot or mgr.is_test_user(pid)
            if is_test:
                is_test_game = True

            u = mgr.get_user(pid)
            username = u.username if u else pid
            nickname = rec.player_name or (u.nickname if u else pid)
            avatar = rec.avatar or (u.avatar if u else "👤")

            participants.append(
                ParticipantRecord(
                    player_id=pid,
                    username=username,
                    nickname=nickname,
                    avatar=avatar,
                    is_test=is_test,
                    rebuy_count=rec.rebuy_count,
                    total_buyin_chips=rec.total_buyin_chips,
                    final_chips=rec.final_chips,
                    net_chips=rec.net_chips,
                    net_cash=rec.net_cash,
                )
            )

        status = "settled" if settlement_type == "immediate" else "unsettled"
        settled_at = now if settlement_type == "immediate" else None
        settled_by = "immediate_transfer" if settlement_type == "immediate" else None

        entry = LedgerEntry(
            entry_id=entry_id,
            room_id=report.room_id,
            room_name=report.room_name,
            settlement_type=settlement_type,
            status=status,
            created_at=now,
            is_test_game=is_test_game,
            participants=participants,
            transactions=[t.to_dict() for t in report.transactions],
            chip_to_cash_ratio=report.chip_to_cash_ratio,
            buyin_chips=report.buyin_chips,
            cash_value=report.cash_value,
            settled_at=settled_at,
            settled_by=settled_by,
        )

        self._entries[entry_id] = entry
        self.save_to_storage()
        return entry

    def get_user_balances(self, include_test: bool = False) -> List[UserBalanceSummary]:
        """Aggregate pending unsettled balances across all unsettled 'balance' entries.

        When include_test=False (default), test games and test accounts are strictly
        excluded so real users' balances remain 100% clean and conserved.
        """
        user_map: Dict[str, dict] = {}

        for entry in self._entries.values():
            if entry.status != "unsettled" or entry.settlement_type != "balance":
                continue

            # Anti-contamination: exclude test games unless explicitly requested
            if not include_test and entry.is_test_game:
                continue

            for p in entry.participants:
                if not include_test and p.is_test:
                    continue

                if p.player_id not in user_map:
                    user_map[p.player_id] = {
                        "user_id": p.player_id,
                        "username": p.username,
                        "nickname": p.nickname,
                        "avatar": p.avatar,
                        "is_test": p.is_test,
                        "net_cash": 0.0,
                        "net_chips": 0,
                        "unsettled_games_count": 0,
                    }

                user_map[p.player_id]["net_cash"] += p.net_cash
                user_map[p.player_id]["net_chips"] += p.net_chips
                user_map[p.player_id]["unsettled_games_count"] += 1

        summaries = [
            UserBalanceSummary(
                user_id=data["user_id"],
                username=data["username"],
                nickname=data["nickname"],
                avatar=data["avatar"],
                is_test=data["is_test"],
                net_cash=round(data["net_cash"], 2),
                net_chips=data["net_chips"],
                unsettled_games_count=data["unsettled_games_count"],
            )
            for data in user_map.values()
        ]

        # Sort descending by net_cash (top winners first)
        summaries.sort(key=lambda s: s.net_cash, reverse=True)
        return summaries

    def preview_batch_settlement(
        self,
        include_test: bool = False,
        entry_ids: Optional[List[str]] = None,
    ) -> dict:
        """Preview the optimal minimal peer-to-peer transfer scheme for pending balances."""
        selected_entries: List[LedgerEntry] = []
        for entry in self._entries.values():
            if entry.status != "unsettled" or entry.settlement_type != "balance":
                continue
            if entry_ids is not None and entry.entry_id not in entry_ids:
                continue
            if not include_test and entry.is_test_game:
                continue
            selected_entries.append(entry)

        user_map: Dict[str, dict] = {}
        for entry in selected_entries:
            for p in entry.participants:
                if not include_test and p.is_test:
                    continue
                if p.player_id not in user_map:
                    user_map[p.player_id] = {
                        "user_id": p.player_id,
                        "username": p.username,
                        "nickname": p.nickname,
                        "avatar": p.avatar,
                        "is_test": p.is_test,
                        "net_cash": 0.0,
                        "net_chips": 0,
                        "unsettled_games_count": 0,
                    }
                user_map[p.player_id]["net_cash"] += p.net_cash
                user_map[p.player_id]["net_chips"] += p.net_chips
                user_map[p.player_id]["unsettled_games_count"] += 1

        user_summaries = [
            {
                "user_id": u["user_id"],
                "nickname": u["nickname"],
                "avatar": u["avatar"],
                "is_test": u["is_test"],
                "net_cash": round(u["net_cash"], 2),
                "net_chips": u["net_chips"],
                "unsettled_games_count": u["unsettled_games_count"],
            }
            for u in user_map.values()
        ]
        user_summaries.sort(key=lambda s: s["net_cash"], reverse=True)

        # Convert net_cash to cents for exact integer debt simplification
        # 1 cent = 1 unit
        net_cents_map: Dict[str, Tuple[str, int]] = {
            u["user_id"]: (u["nickname"], int(round(u["net_cash"] * 100)))
            for u in user_summaries
        }

        # Run minimal debt simplification with ratio=0.01 (cents to cash)
        raw_txs = SettlementEngine.simplify_debts(net_cents_map, chip_to_cash_ratio=0.01)
        transactions = []
        total_transferred_cash = 0.0
        for tx in raw_txs:
            amt = round(tx.amount_cash, 2)
            total_transferred_cash += amt
            transactions.append({
                "from_player_id": tx.from_player_id,
                "from_player_name": tx.from_player_name,
                "to_player_id": tx.to_player_id,
                "to_player_name": tx.to_player_name,
                "amount_cash": amt,
                "amount_chips": tx.amount_chips,
                "display": f"{tx.from_player_name} 应付给 {tx.to_player_name}: ¥{amt:.2f}",
            })

        return {
            "entry_count": len(selected_entries),
            "entry_ids": [e.entry_id for e in selected_entries],
            "total_transferred_cash": round(total_transferred_cash, 2),
            "user_summaries": user_summaries,
            "transactions": transactions,
        }

    def settle_batch(
        self,
        operator_id: str,
        operator_name: str = "管理员",
        include_test: bool = False,
        entry_ids: Optional[List[str]] = None,
    ) -> SettlementBatch:
        """Execute one-time batch debt settlement across unsettled balance records."""
        preview = self.preview_batch_settlement(include_test=include_test, entry_ids=entry_ids)
        if not preview["entry_ids"]:
            raise ValueError("当前没有可结算的待结账单条目")

        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        now = time.time()

        batch = SettlementBatch(
            batch_id=batch_id,
            created_at=now,
            operator_id=operator_id,
            operator_name=operator_name,
            total_transferred_cash=preview["total_transferred_cash"],
            user_summaries=preview["user_summaries"],
            transactions=preview["transactions"],
            entry_ids=preview["entry_ids"],
        )

        for eid in preview["entry_ids"]:
            if eid in self._entries:
                entry = self._entries[eid]
                entry.status = "settled"
                entry.settled_at = now
                entry.settled_by = operator_id
                entry.batch_id = batch_id

        self._batches[batch_id] = batch
        self.save_to_storage()
        return batch

    def get_user_records(
        self,
        user_id: str,
        include_settled: bool = True,
    ) -> List[dict]:
        """List all ledger records participated in by a specific user."""
        records = []
        for entry in self._entries.values():
            if not include_settled and entry.status == "settled":
                continue

            my_part = next((p for p in entry.participants if p.player_id == user_id), None)
            if my_part:
                e_dict = entry.to_dict()
                e_dict["my_record"] = my_part.to_dict()
                records.append(e_dict)

        records.sort(key=lambda r: r["created_at"], reverse=True)
        return records

    def list_entries(
        self,
        include_test: bool = True,
        status: Optional[str] = None,
    ) -> List[dict]:
        """List ledger entries with optional status and test filters."""
        result = []
        for entry in self._entries.values():
            if not include_test and entry.is_test_game:
                continue
            if status and entry.status != status:
                continue
            result.append(entry.to_dict())

        result.sort(key=lambda e: e["created_at"], reverse=True)
        return result

    def list_batches(self) -> List[dict]:
        """List all settlement batches ordered by creation time descending."""
        batches = [b.to_dict() for b in self._batches.values()]
        batches.sort(key=lambda b: b["created_at"], reverse=True)
        return batches

    def get_batch(self, batch_id: str) -> Optional[dict]:
        """Get details of a settlement batch."""
        b = self._batches.get(batch_id)
        return b.to_dict() if b else None

    def clear_test_records(self) -> int:
        """Purge test game records and test accounts from ledger storage."""
        to_delete = [
            eid for eid, entry in self._entries.items()
            if entry.is_test_game
        ]
        for eid in to_delete:
            del self._entries[eid]

        if to_delete:
            self.save_to_storage()
        return len(to_delete)

    def clear_all_records(self) -> Tuple[int, int]:
        """Purge all ledger entries and settlement batches to restart balance accounting afresh.

        Returns:
            Tuple of (cleared_entries_count, cleared_batches_count)
        """
        entries_count = len(self._entries)
        batches_count = len(self._batches)

        self._entries.clear()
        self._batches.clear()
        self.save_to_storage()
        return entries_count, batches_count


# Global singleton
balance_manager = BalanceManager()
