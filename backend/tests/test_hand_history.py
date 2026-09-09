"""Durable per-hand history, filtering, sorting, and privacy tests."""

import pytest
from fastapi import HTTPException

from backend.app.api.endpoints import get_my_hand_history
from backend.app.engine.state_machine import ActionType, Street
from backend.app.models.room import RoomConfig
from backend.app.services.hand_history_manager import hand_history_manager
from backend.app.services.room_manager import RoomManager
from backend.app.services.user_manager import user_manager


pytestmark = pytest.mark.usefixtures("funded_room_players")


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


def test_table_history_groups_all_hands_paginates_and_survives_restart(tmp_path):
    from backend.app.services.hand_history_manager import HandHistoryManager
    path = str(tmp_path / 'tables.sqlite3')
    manager = HandHistoryManager(path)
    for room, number, net in [('one', 1, 20), ('one', 2, -5), ('two', 1, 40)]:
        manager.record_hand(dict(
            hand_id=f'{room}:{number}', room_id=room, room_name='同名桌',
            hand_number=number, ended_at=100 + number + (10 if room == 'two' else 0),
            small_blind=5, big_blind=10, money_mode='real',
            actions=[dict(player_id='alice', action='CALL', street='PREFLOP', amount=10)],
            players=[dict(player_id='alice', player_name='Alice', net_chips=net,
                          net_cash=net / 10, contributed_chips=10, payout_chips=10 + net),
                     dict(player_id='bob', player_name='Bob', net_chips=-net,
                          hole_cards=[{'rank': 'A', 'suit': 's'}])]))
    manager = HandHistoryManager(path)
    first = manager.list_user_tables('alice', limit=1)
    second = manager.list_user_tables('alice', limit=1, offset=1)
    assert first['total'] == 2
    assert first['tables'][0]['room_id'] == 'two'
    table = second['tables'][0]
    assert table['hands'] == 2
    assert table['net_chips'] == 15
    assert table['net_cash'] == 1.5
    assert table['winning_hands'] == 1
    assert table['biggest_win'] == 20 and table['biggest_loss'] == -5
    assert 'hole_cards' not in table
    assert manager.list_user_tables('outsider')['total'] == 0
    assert manager.list_user_tables('alice', offset=2)['tables'] == []
    history = manager.list_user_hands('alice', room_id='one', limit=1, offset=1)
    assert history['total'] == 2
    assert history['hands'][0]['actions'][0]['player_name'] == 'Alice'
    assert 'players' not in history['hands'][0]


def test_table_history_and_archived_statistics_require_owner(monkeypatch):
    from backend.app.api.endpoints import get_my_tables, get_my_statistics
    from backend.app.services import player_statistics
    calls = []
    monkeypatch.setattr(hand_history_manager, 'list_user_tables',
                        lambda uid, limit, offset: calls.append((uid, limit, offset)) or {})
    monkeypatch.setattr(player_statistics, 'query_statistics',
                        lambda db, uid, rid: calls.append((uid, rid)) or {})
    token = user_manager.get_or_create_token('u_test1')
    get_my_tables(limit=20, offset=0, authorization=None, token=token)
    assert calls[-1] == ('u_test1', 20, 0)
    get_my_statistics(authorization=None, token=token, room_id='deleted-room')
    assert calls[-1] == ('u_test1', 'deleted-room')
    with pytest.raises(HTTPException) as exc:
        get_my_tables(limit=20, offset=0, authorization=None, token=None)
    assert exc.value.status_code == 401


def test_balance_lifetime_profit_survives_transfers_and_restart(tmp_path, monkeypatch):
    from backend.app.api import endpoints
    from backend.app.services.balance_manager import BalanceManager
    from backend.app.services.hand_history_manager import HandHistoryManager
    from backend.app.services.settlement import SettlementEngine

    path = str(tmp_path / 'lifetime.sqlite3')
    history = HandHistoryManager(path)
    ledger = BalanceManager(database_path=path)
    monkeypatch.setattr(endpoints, 'hand_history_manager', history)
    monkeypatch.setattr(endpoints, 'balance_manager', ledger)
    assert history.get_lifetime_net_cash('u_test1') == 0
    for number, net in enumerate([125, -25, 1], 1):
        history.record_hand(dict(
            hand_id=f'lifetime:{number}', room_id='lifetime', room_name='累计',
            hand_number=number, ended_at=number, money_mode='real',
            small_blind=1, big_blind=2,
            players=[dict(player_id='u_test1', player_name='test1',
                          net_chips=net, net_cash=net / 100),
                     dict(player_id='u_test2', player_name='test2',
                          net_chips=-net, net_cash=-net / 100)]))
    report = SettlementEngine.calculate_room_settlement('lifetime', '累计', 100, 1, [
        dict(player_id='u_test1', player_name='test1', rebuy_count=1,
             total_buyin_chips=200, final_chips=301),
        dict(player_id='u_test2', player_name='test2', rebuy_count=1,
             total_buyin_chips=200, final_chips=99),
    ])
    ledger.record_settlement(report, u_mgr=user_manager)
    token = user_manager.get_or_create_token('u_test1')

    def balance(include_settled=True):
        return endpoints.get_my_balance(include_settled=include_settled,
                                        authorization=None, token=token)

    assert balance()['pending_net_cash'] == 1.01
    assert balance()['lifetime_net_cash'] == 1.01
    ledger.settle_batch(operator_id='u_test1', include_test=True)
    monkeypatch.setattr(endpoints, 'hand_history_manager', HandHistoryManager(path))
    monkeypatch.setattr(endpoints, 'balance_manager', BalanceManager(database_path=path))
    after = balance(include_settled=False)
    assert after['pending_net_cash'] == 0
    assert after['records'] == []
    assert after['lifetime_net_cash'] == 1.01
    assert history.get_lifetime_net_cash('u_test2') == -1.01
    assert history.get_lifetime_net_cash('outsider') == 0
    with pytest.raises(HTTPException) as exc:
        endpoints.get_my_balance(include_settled=True, authorization=None, token=None)
    assert exc.value.status_code == 401
