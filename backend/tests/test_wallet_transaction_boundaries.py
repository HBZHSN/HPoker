"""Regression coverage for wallet funding, rollback, and open-hand recovery."""

import pytest

from backend.app.models.room import Room, RoomConfig
from backend.app.services.balance_manager import balance_manager
from backend.app.services.room_manager import RoomManager


def _real_room(room_id: str = "wallet-room", max_seats: int = 4) -> Room:
    room = Room("real1", RoomConfig(max_seats=max_seats), room_id=room_id)
    for seat_index, player_id in enumerate(("real1", "real2", "real3")):
        assert room.sit_down_player(
            player_id,
            player_id,
            seat_index,
            is_test=False,
        )
    return room


def test_late_real_player_in_play_mode_cannot_cash_out_free_chips():
    room = _real_room("late-join-room", max_seats=5)
    assert room.add_test_bot(seat_index=3)
    assert room.money_mode == "play"

    assert room.sit_down_player("late-real", "late-real", 0, is_test=False) is False
    assert room.sit_down_player("late-real", "late-real", 4, is_test=False)
    late_seat = next(seat for seat in room.table.active_seated_players if seat.player_id == "late-real")
    assert late_seat.wallet_mode == "play"
    assert not any(
        entry.entry_kind == "buyin"
        and entry.participants[0].player_id == "late-real"
        for entry in balance_manager._entries.values()
    )

    assert room.leave_player("late-real")
    assert not any(
        entry.entry_kind == "cashout"
        and entry.participants[0].player_id == "late-real"
        for entry in balance_manager._entries.values()
    )


def test_abort_refunds_a_departed_player_contribution_once():
    room = _real_room("abort-room")
    assert room.table.start_new_hand()
    # Seat 1 is the small blind in the first three-way hand and has money in
    # the pot when it leaves. The hand remains live because two players stay.
    assert room.leave_player("real2")
    assert room.table.street.value == "PREFLOP"

    room.cash_out_all_players(reason="aborted")
    room.cash_out_all_players(reason="repeated")

    real2_entries = [
        entry for entry in balance_manager._entries.values()
        if entry.participants[0].player_id == "real2"
    ]
    assert sum(entry.participants[0].net_chips for entry in real2_entries) == 0
    assert sorted(entry.participants[0].net_chips for entry in real2_entries) == [-1000, 10, 990]


def test_checkpoint_restore_replays_off_table_refund_without_double_credit():
    room = _real_room("restore-room")
    assert room.table.start_new_hand()
    assert room.leave_player("real2")
    checkpoint = room.to_checkpoint_dict()
    assert checkpoint["recovery_refunds"]
    before_restore = [
        entry.participants[0].net_chips
        for entry in balance_manager._entries.values()
        if entry.participants[0].player_id == "real2"
    ]
    assert sorted(before_restore) == [-1000, 990]

    restored = Room.from_checkpoint_dict(checkpoint)
    real2_entries = [
        entry for entry in balance_manager._entries.values()
        if entry.participants[0].player_id == "real2"
    ]
    assert restored.historical_players["real2"]["cashed_out_chips"] == 1000
    assert sorted(entry.participants[0].net_chips for entry in real2_entries) == [-1000, 10, 990]


def test_room_manager_checkpoint_defers_off_table_refund_until_recovery(tmp_path):
    manager = RoomManager(database_path=str(tmp_path / "recovery.sqlite3"))
    room = manager.create_room(
        host_player_id="real1",
        config=RoomConfig(max_seats=3),
        room_id="manager-recovery-room",
    )
    assert room.sit_down_player("real1", "real1", 0, is_test=False)
    assert room.sit_down_player("real2", "real2", 1, is_test=False)
    assert room.sit_down_player("real3", "real3", 2, is_test=False)
    assert room.table.start_new_hand()
    assert room.leave_player("real2")

    manager.checkpoint_room(room)
    real2_entries = [
        entry for entry in balance_manager._entries.values()
        if entry.participants[0].player_id == "real2"
    ]
    assert sorted(entry.participants[0].net_chips for entry in real2_entries) == [-1000, 990]

    restored = RoomManager(database_path=str(tmp_path / "recovery.sqlite3")).get_room(
        "manager-recovery-room"
    )
    assert restored is not None
    real2_entries = [
        entry for entry in balance_manager._entries.values()
        if entry.participants[0].player_id == "real2"
    ]
    assert sorted(entry.participants[0].net_chips for entry in real2_entries) == [-1000, 10, 990]


def test_wallet_and_seat_mutation_roll_back_together(monkeypatch):
    room = Room("real1", RoomConfig(max_seats=2), room_id="rollback-room")

    def fail_wallet_write(*args, **kwargs):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(balance_manager, "record_wallet_change", fail_wallet_write)
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        room.sit_down_player("real1", "real1", 0, is_test=False)

    assert room.table.active_seated_players == []
    assert room.historical_players == {}
    assert balance_manager._entries == {}
