import pytest
from backend.app.engine.state_machine import ActionType, Street
from backend.app.models.room import Room, RoomConfig
from backend.app.services.room_manager import RoomManager
from backend.app.services.settlement import SettlementEngine, PaymentTransaction
from backend.app.services.balance_manager import balance_manager


def test_settlement_engine_minimal_transfers():
    # 3 players:
    # Alice: bought 1000, final 2500 -> net +1500
    # Bob: bought 2000 (1 rebuy), final 500 -> net -1500
    # Charlie: bought 1000, final 1000 -> net 0
    # Cash ratio: 100 RMB per 1000 chips (0.1 RMB/chip)
    participants = [
        {"player_id": "p1", "player_name": "Alice", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 2500},
        {"player_id": "p2", "player_name": "Bob", "rebuy_count": 2, "total_buyin_chips": 2000, "final_chips": 500},
        {"player_id": "p3", "player_name": "Charlie", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1000},
    ]

    report = SettlementEngine.calculate_room_settlement(
        room_id="room-1",
        room_name="Test Room",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=participants,
    )

    assert report.is_balanced is True
    assert len(report.transactions) == 1
    t = report.transactions[0]
    assert t.from_player_name == "Bob"
    assert t.to_player_name == "Alice"
    assert t.amount_chips == 1500
    assert t.amount_cash == 150.0


def test_settlement_multi_party_transfer():
    # 4 players:
    # P1 (Alice): +1000
    # P2 (Bob): +500
    # P3 (Charlie): -800
    # P4 (David): -700
    participants = [
        {"player_id": "p1", "player_name": "Alice", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 2000},
        {"player_id": "p2", "player_name": "Bob", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 1500},
        {"player_id": "p3", "player_name": "Charlie", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 200},
        {"player_id": "p4", "player_name": "David", "rebuy_count": 1, "total_buyin_chips": 1000, "final_chips": 300},
    ]

    report = SettlementEngine.calculate_room_settlement(
        room_id="room-2",
        room_name="Multi Test",
        buyin_chips=1000,
        cash_value=100.0,
        player_data_list=participants,
    )

    assert report.is_balanced is True
    # At most 3 transactions for 4 people
    assert len(report.transactions) <= 3
    # Total money transferred equals total profit
    total_transferred = sum(t.amount_cash for t in report.transactions)
    assert total_transferred == 150.0  # 1500 chips * 0.1


@pytest.mark.parametrize("max_seats", range(2, 10))
def test_room_config_supports_every_table_size(max_seats):
    config = RoomConfig(max_seats=max_seats)
    room = Room(host_player_id="host", config=config)

    assert config.max_seats == max_seats
    assert len(room.table.seats) == max_seats


@pytest.mark.parametrize("max_seats", [1, 10])
def test_room_config_rejects_unsupported_table_size(max_seats):
    with pytest.raises(ValueError, match="max_seats"):
        RoomConfig(max_seats=max_seats)


def test_room_lifecycle_and_rebuy():
    rm = RoomManager(storage_path=":memory:")
    cfg = RoomConfig(
        room_name="VIP Cash Room",
        buyin_chips=1000,
        cash_value=100.0,
        small_blind=5,
        big_blind=10,
        action_timeout=15,
        max_seats=6,
    )
    room = rm.create_room(host_player_id="host1", config=cfg)
    assert room.room_id in [r["room_id"] for r in rm.list_rooms()]

    # Players sit down
    assert room.sit_down_player("host1", "Alice (Host)", seat_index=0, avatar="🦊") is True
    assert room.sit_down_player("user2", "Bob", seat_index=1, avatar="🐼") is True

    # Bob cannot rebuy when chips > 0
    assert room.rebuy_player("user2") is False

    # Even a zero-chip seat cannot buy back in before the current hand ends.
    assert room.table.start_new_hand() is True
    room.table.seats[1].chips = 0
    assert room.rebuy_player("user2") is False
    room.table.refund_unsettled_hand()

    # Bob loses all chips (chips == 0)
    room.table.seats[1].chips = 0
    assert room.rebuy_player("user2") is True
    assert room.table.seats[1].chips == 1000
    assert room.table.seats[1].rebuy_count == 2
    assert room.table.seats[1].total_buyin_chips == 2000

    # Non-host cannot end room
    assert room.end_room(requester_id="user2") is None
    assert room.is_ended is False

    # Host ends room
    report = room.end_room(requester_id="host1", record_to_balance=False)
    assert report is not None
    assert room.is_ended is True
    assert len(report.player_records) == 2
    records_by_id = {record.player_id: record for record in report.player_records}
    assert records_by_id["host1"].avatar == "🦊"
    assert records_by_id["user2"].avatar == "🐼"
    serialized_records = {
        record["player_id"]: record for record in report.to_dict()["player_records"]
    }
    assert serialized_records["host1"]["avatar"] == "🦊"
    assert serialized_records["user2"]["avatar"] == "🐼"


def test_ending_room_refunds_unsettled_hand_contributions():
    cfg = RoomConfig(
        room_name="Interrupted Hand Room",
        buyin_chips=100,
        cash_value=10.0,
        small_blind=5,
        action_timeout=15,
        max_seats=6,
    )
    room = Room(host_player_id="host1", config=cfg)
    assert room.sit_down_player("host1", "Alice", seat_index=0) is True
    assert room.sit_down_player("user2", "Bob", seat_index=1) is True

    assert room.table.start_new_hand() is True
    assert room.table.pot_manager.total_pot_amount == 15
    assert room.table.seats[0].chips == 95
    assert room.table.seats[1].chips == 90

    report = room.end_room(requester_id="host1", record_to_balance=False)

    assert report is not None
    assert report.is_balanced is True
    assert report.total_chips_in_game == 200
    assert report.transactions == []
    assert room.table.pot_manager.total_pot_amount == 0
    assert room.table.street.value == "HAND_END"
    assert room.table.seats[0].chips == 100
    assert room.table.seats[1].chips == 100
    assert all(record.net_chips == 0 for record in report.player_records)


def test_player_leave_stages_cash_out_until_host_chooses_settlement():
    room = Room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    room.table.seats[0].chips = 140
    room.table.seats[1].chips = 60

    departed = room.leave_player("user2")

    assert departed is not None
    assert room.table.seats[1] is None
    assert room.historical_players["user2"]["final_chips"] == 60
    assert room.pending_settlements[0]["reason"] == "leave"
    assert room.pending_settlements[0]["status"] == "pending"
    assert room.pending_settlement_report is not None
    assert room.pending_settlement_report.settlement_type == "pending"
    assert balance_manager._entries == {}

    report = room.end_room(requester_id="host1", settlement_type="balance")
    records = {record.player_id: record for record in report.player_records}

    assert report.is_balanced is True
    assert records["user2"].final_chips == 60
    assert records["host1"].final_chips == 140
    assert room.pending_settlements[0]["status"] == "resolved"
    assert room.pending_settlements[0]["settlement_type"] == "balance"
    assert len(balance_manager._entries) == 1
    assert next(iter(balance_manager._entries.values())).status == "unsettled"


def test_player_can_buy_in_again_without_losing_previous_cash_out():
    room = Room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    room.table.seats[0].chips = 140
    room.table.seats[1].chips = 60
    assert room.leave_player("user2") is not None

    assert room.sit_down_player("user2", "Bob", seat_index=1)
    assert room.historical_players["user2"]["total_buyin_chips"] == 200
    assert room.historical_players["user2"]["rebuy_count"] == 2

    report = room.end_room(requester_id="host1", record_to_balance=False)
    records = {record.player_id: record for record in report.player_records}

    assert report.is_balanced is True
    assert records["user2"].final_chips == 160
    assert records["user2"].net_chips == -40
    assert records["host1"].final_chips == 140


def test_all_in_player_cannot_leave_before_hand_end():
    room = Room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    assert room.table.start_new_hand()
    current_player = room.table.seats[room.table.current_turn_seat]
    assert current_player is not None
    assert room.table.handle_action(current_player.player_id, ActionType.ALL_IN)

    assert room.leave_player(current_player.player_id) is None
    assert room.table.seats[current_player.seat_index] is current_player


def test_pending_departure_and_kick_survive_room_checkpoint(tmp_path):
    storage_path = tmp_path / "rooms.json"
    manager = RoomManager(storage_path=str(storage_path))
    room = manager.create_room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="departure1",
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    room.table.seats[0].chips = 140
    room.table.seats[1].chips = 60
    assert room.leave_player("user2") is not None
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    assert room.kick_player("user2") is not None

    manager.checkpoint_room(room)
    restored = RoomManager(storage_path=str(storage_path)).get_room("departure1")

    assert restored is not None
    assert restored.table.seats[1] is None
    assert [item["reason"] for item in restored.pending_settlements] == ["leave", "kick"]
    assert restored.is_player_kicked("user2") is True
    assert restored.sit_down_player("user2", "Bob", seat_index=1) is False


def test_room_checkpoint_restores_completed_hand_ledger(tmp_path):
    storage_path = tmp_path / "rooms.json"
    manager = RoomManager(storage_path=str(storage_path))
    room = manager.create_room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, cash_value=10, small_blind=5),
        room_id="durable1",
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    manager.checkpoint_room(room)

    assert room.table.start_new_hand()
    acting_player = room.table.seats[room.table.current_turn_seat]
    assert acting_player is not None
    assert room.table.handle_action(acting_player.player_id, ActionType.FOLD)
    assert room.table.street == Street.HAND_END
    manager.checkpoint_room(room)

    restored_manager = RoomManager(storage_path=str(storage_path))
    restored = restored_manager.get_room("durable1")
    assert restored is not None
    assert restored.table.street == Street.IDLE
    assert restored.table.hand_number == 1
    assert [seat.chips for seat in restored.table.active_seated_players] == [95, 105]
    assert [seat.total_buyin_chips for seat in restored.table.active_seated_players] == [100, 100]
    assert restored.hand_records[0]["hand_number"] == 1
    assert restored.hand_records[0]["total_chips"] == 200


def test_in_progress_checkpoint_refunds_current_hand_contributions(tmp_path):
    storage_path = tmp_path / "rooms.json"
    manager = RoomManager(storage_path=str(storage_path))
    room = manager.create_room(
        host_player_id="host1",
        config=RoomConfig(buyin_chips=100, small_blind=5),
        room_id="recover1",
    )
    assert room.sit_down_player("host1", "Alice", seat_index=0)
    assert room.sit_down_player("user2", "Bob", seat_index=1)
    manager.checkpoint_room(room)
    assert room.table.start_new_hand()

    # A crash during a hand restores the safe pre-hand stacks rather than
    # stranding posted blinds in a hand that cannot be reconstructed safely.
    manager.checkpoint_room(room)
    restored = RoomManager(storage_path=str(storage_path)).get_room("recover1")
    assert restored is not None
    assert restored.table.street == Street.IDLE
    assert [seat.chips for seat in restored.table.active_seated_players] == [100, 100]
    assert restored.table.pot_manager.total_pot_amount == 0
