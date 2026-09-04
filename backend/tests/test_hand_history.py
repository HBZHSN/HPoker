"""Durable per-hand history, filtering, sorting, and privacy tests."""

import pytest
from fastapi import HTTPException

from backend.app.api.endpoints import get_my_hand_history
from backend.app.engine.state_machine import ActionType, Street
from backend.app.models.room import RoomConfig
from backend.app.services.hand_history_manager import hand_history_manager
from backend.app.services.room_manager import RoomManager
from backend.app.services.user_manager import user_manager


def test_completed_hand_is_persisted_with_each_users_own_cards(tmp_path):
    manager = RoomManager(database_path=str(tmp_path / "hands.sqlite3"))
    room = manager.create_room(
        host_player_id="alice",
        config=RoomConfig(room_name="历史桌", buyin_chips=100, cash_value=10, small_blind=5),
        room_id="history-room",
    )
    assert room.sit_down_player("alice", "Alice", 0, is_test=False)
    assert room.sit_down_player("bob", "Bob", 1, is_test=False)
    assert room.table.start_new_hand()
    alice_cards = [card.to_dict() for card in room.table.seats[0].hole_cards]
    bob_cards = [card.to_dict() for card in room.table.seats[1].hole_cards]

    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    assert room.table.street == Street.HAND_END
    manager.checkpoint_room(room)
    manager.checkpoint_room(room)

    alice = manager.hand_history_manager.list_user_hands("alice")
    bob = manager.hand_history_manager.list_user_hands("bob")
    assert alice["total"] == 1
    assert bob["total"] == 1
    assert alice["hands"][0]["hole_cards"] == alice_cards
    assert bob["hands"][0]["hole_cards"] == bob_cards
    assert alice["hands"][0]["net_chips"] == -bob["hands"][0]["net_chips"]
    assert "players" not in alice["hands"][0]


def test_hand_history_filters_and_sorts_biggest_wins_and_losses(tmp_path):
    manager = RoomManager(database_path=str(tmp_path / "history-filter.sqlite3"))
    history = manager.hand_history_manager
    base = {
        "room_id": "room-a",
        "room_name": "A桌",
        "money_mode": "real",
        "small_blind": 5,
        "big_blind": 10,
        "chip_to_cash_ratio": 0.1,
        "total_pot": 100,
        "board": [],
        "board_2": [],
        "actions": [],
    }
    for number, net in enumerate((20, -60, 100), start=1):
        history.record_hand({
            **base,
            "hand_id": f"room-a:{number}",
            "hand_number": number,
            "ended_at": 1000 + number,
            "players": [{
                "player_id": "alice",
                "player_name": "Alice",
                "starting_chips": 100,
                "ending_chips": 100 + net,
                "contributed_chips": max(-net, 0),
                "payout_chips": max(net, 0),
                "net_chips": net,
                "net_cash": net * 0.1,
            }],
        })

    wins = history.list_user_hands(
        "alice", outcome="win", sort_by="net_chips", order="desc"
    )
    losses = history.list_user_hands(
        "alice", outcome="loss", sort_by="net_chips", order="asc"
    )
    assert [item["net_chips"] for item in wins["hands"]] == [100, 20]
    assert [item["net_chips"] for item in losses["hands"]] == [-60]
    unfiltered = history.list_user_hands("alice")
    assert unfiltered["summary"]["biggest_win"]["net_chips"] == 100
    assert unfiltered["summary"]["biggest_loss"]["net_chips"] == -60


def test_hand_history_endpoint_requires_login_and_returns_only_owners_cards():
    hand_history_manager.record_hand({
        "hand_id": "private-room:1",
        "room_id": "private-room",
        "room_name": "隐私桌",
        "hand_number": 1,
        "ended_at": 1234,
        "money_mode": "play",
        "small_blind": 5,
        "big_blind": 10,
        "chip_to_cash_ratio": 0,
        "total_pot": 20,
        "players": [
            {
                "player_id": "u_test1",
                "player_name": "test1",
                "hole_cards": [{"rank": "A", "suit": "spades"}],
                "starting_chips": 100,
                "ending_chips": 110,
                "net_chips": 10,
            },
            {
                "player_id": "u_test2",
                "player_name": "test2",
                "hole_cards": [{"rank": "K", "suit": "hearts"}],
                "starting_chips": 100,
                "ending_chips": 90,
                "net_chips": -10,
            },
        ],
    })
    token = user_manager.get_or_create_token("u_test1")
    result = get_my_hand_history(
        outcome=None,
        room_id=None,
        started_at=None,
        ended_at=None,
        sort_by="ended_at",
        order="desc",
        limit=50,
        offset=0,
        authorization=None,
        token=token,
    )
    assert result["hands"][0]["hole_cards"] == [{"rank": "A", "suit": "spades"}]
    assert "players" not in result["hands"][0]

    with pytest.raises(HTTPException) as exc:
        get_my_hand_history(
            outcome=None,
            room_id=None,
            started_at=None,
            ended_at=None,
            sort_by="ended_at",
            order="desc",
            limit=50,
            offset=0,
            authorization=None,
            token=None,
        )
    assert exc.value.status_code == 401
