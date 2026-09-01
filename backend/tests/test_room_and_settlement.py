import pytest
from backend.app.models.room import Room, RoomConfig
from backend.app.services.room_manager import RoomManager
from backend.app.services.settlement import SettlementEngine, PaymentTransaction


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


def test_room_lifecycle_and_rebuy():
    rm = RoomManager()
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
    assert room.sit_down_player("host1", "Alice (Host)", seat_index=0) is True
    assert room.sit_down_player("user2", "Bob", seat_index=1) is True

    # Bob cannot rebuy when chips > 0
    assert room.rebuy_player("user2") is False

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
    report = room.end_room(requester_id="host1")
    assert report is not None
    assert room.is_ended is True
    assert len(report.player_records) == 2
