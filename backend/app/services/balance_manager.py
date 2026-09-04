"""Balance and Ledger Management Service.

Handles game settlement recording, user balance aggregation,
minimal debt consolidation across multiple hands/rooms, and batch settlements.
Strictly isolates test accounts and bot matches to prevent contaminating real balances.
"""

from __future__ import annotations
import json
import hashlib
import logging
import os
import time
from typing import Dict, List, Optional, Tuple
import uuid

from backend.app.database import DEFAULT_DATABASE_PATH, SQLiteDatabase
from backend.app.models.balance import (
    ParticipantRecord,
    LedgerEntry,
    UserBalanceSummary,
    SettlementBatch,
)
from backend.app.services.settlement import SettlementEngine, PaymentTransaction, SettlementReport
from backend.app.services.user_manager import user_manager, UserManager

logger = logging.getLogger("poker.balance")

LEGACY_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "balance_ledger.json",
)


class BalanceManager:
    """Manage normalized SQLite ledgers, debt settlement, and test isolation."""

    def __init__(
        self,
        database_path: Optional[str] = None,
        *,
        storage_path: Optional[str] = None,
        legacy_storage_path: Optional[str] = None,
    ):
        if database_path is not None and storage_path is not None:
            raise ValueError("database_path and storage_path cannot both be set")
        selected_path = database_path if database_path is not None else storage_path
        self._database = SQLiteDatabase(selected_path)
        self.storage_path = self._database.path
        self.legacy_storage_path = legacy_storage_path
        if (
            legacy_storage_path is None
            and self.storage_path == os.path.realpath(DEFAULT_DATABASE_PATH)
        ):
            self.legacy_storage_path = LEGACY_STORAGE_FILE

        self._entries: Dict[str, LedgerEntry] = {}
        self._batches: Dict[str, SettlementBatch] = {}
        self.load_from_storage()

    def _migrate_legacy_json(self) -> None:
        """Import balance_ledger.json exactly once into normalized tables."""
        migration_name = "balance_ledger_json_v1"
        if self._database.migration_applied(migration_name):
            return
        existing_entries, existing_batches = self._database.load_ledger()
        if existing_entries or existing_batches:
            self._database.mark_migration_applied(migration_name)
            return

        legacy_path = self.legacy_storage_path
        if legacy_path and os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as storage_file:
                    payload = json.load(storage_file)
                self._database.replace_ledger(
                    payload.get("entries", []), payload.get("batches", [])
                )
            except (OSError, ValueError, KeyError):
                logger.exception("Failed to migrate balance ledger from %s", legacy_path)
                raise
        self._database.mark_migration_applied(migration_name)

    def load_from_storage(self) -> None:
        """Load ledger entries and settlement batches from normalized tables."""
        self._entries.clear()
        self._batches.clear()

        self._migrate_legacy_json()
        stored_entries, stored_batches = self._database.load_ledger()
        for entry_data in stored_entries:
            entry = LedgerEntry.from_dict(entry_data)
            self._entries[entry.entry_id] = entry
        for batch_data in stored_batches:
            batch = SettlementBatch.from_dict(batch_data)
            self._batches[batch.batch_id] = batch

    def save_to_storage(self) -> None:
        """Atomically persist the ledger graph to normalized SQLite tables."""
        entries = []
        for entry in self._entries.values():
            payload = entry.to_dict()
            for participant, participant_payload in zip(
                entry.participants, payload["participants"]
            ):
                participant_payload["username"] = participant.username
            entries.append(payload)
        self._database.replace_ledger(
            entries,
            [batch.to_dict() for batch in self._batches.values()],
        )

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

    def record_wallet_change(
        self,
        *,
        room_id: str,
        room_name: str,
        player_id: str,
        player_name: str,
        avatar: str,
        chips_delta: int,
        buyin_chips: int,
        cash_value: float,
        entry_kind: str,
        idempotency_key: str,
        u_mgr: Optional[UserManager] = None,
    ) -> LedgerEntry:
        """Apply one durable table-wallet movement exactly once.

        Negative ``chips_delta`` debits a buy-in from the player's pending
        balance. Positive values credit chips cashed out from the table.
        """
        if chips_delta == 0:
            raise ValueError("chips_delta must be non-zero")
        if entry_kind not in {"buyin", "cashout", "mode_change"}:
            raise ValueError("unsupported wallet entry kind")
        if not idempotency_key:
            raise ValueError("idempotency_key is required")

        digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
        entry_id = f"wallet_{digest}"
        existing = self._entries.get(entry_id)
        if existing is not None:
            return existing

        mgr = u_mgr or user_manager
        user = mgr.get_user(player_id)
        is_test = player_id.startswith("bot_") or mgr.is_test_user(player_id)
        ratio = cash_value / buyin_chips if buyin_chips > 0 else 0.0
        total_buyin = -chips_delta if chips_delta < 0 else 0
        final_chips = chips_delta if chips_delta > 0 else 0
        participant = ParticipantRecord(
            player_id=player_id,
            username=user.username if user else player_id,
            nickname=player_name or (user.nickname if user else player_id),
            avatar=avatar or (user.avatar if user else "👤"),
            is_test=is_test,
            rebuy_count=1 if chips_delta < 0 else 0,
            total_buyin_chips=total_buyin,
            final_chips=final_chips,
            net_chips=chips_delta,
            net_cash=round(chips_delta * ratio, 2),
        )
        entry = LedgerEntry(
            entry_id=entry_id,
            room_id=room_id,
            room_name=room_name,
            settlement_type="balance",
            status="unsettled",
            created_at=time.time(),
            is_test_game=is_test,
            participants=[participant],
            transactions=[],
            chip_to_cash_ratio=ratio,
            buyin_chips=buyin_chips,
            cash_value=cash_value,
            entry_kind=entry_kind,
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

        net_cash_cents = sum(
            int(round(user["net_cash"] * 100)) for user in user_summaries
        )
        return {
            "entry_count": len(selected_entries),
            "entry_ids": [e.entry_id for e in selected_entries],
            "total_transferred_cash": round(total_transferred_cash, 2),
            "user_summaries": user_summaries,
            "transactions": transactions,
            "is_balanced": net_cash_cents == 0,
            "unmatched_cash": round(abs(net_cash_cents) / 100, 2),
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
        if not preview["is_balanced"]:
            raise ValueError("仍有筹码在牌桌中，需全部兑回余额后再划转结算")

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
