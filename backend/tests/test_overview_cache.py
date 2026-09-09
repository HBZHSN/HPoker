"""Overview requests read snapshots; departure is the aggregation boundary."""

import json

import pytest

from backend.app.engine.card import Card
from backend.app.models.room import RoomConfig
from backend.app.services.hand_history_manager import HandHistoryManager
from backend.app.services.room_manager import RoomManager
from backend.app.services import player_statistics


def record(manager, number=1, player_id='u_test1', net=20):
    manager.record_hand({
        'hand_id': f'cache-room:{number}', 'room_id': 'cache-room',
        'room_name': 'Cache test', 'hand_number': number, 'ended_at': number,
        'small_blind': 5, 'big_blind': 10, 'money_mode': 'real',
        'board': [], 'board_2': [], 'actions': [],
        'players': [{'player_id': player_id, 'net_chips': net, 'net_cash': net / 10,
                     'payout_chips': max(0, net),
                     'hole_cards': [Card.from_str('As').to_dict(), Card.from_str('Ah').to_dict()]}],
    })


def test_reads_never_recalculate_and_survive_restart(tmp_path, monkeypatch):
    manager = HandHistoryManager(str(tmp_path / 'cache.sqlite3'))
    record(manager)
    # No fallback full-history scan, even when old history has not been migrated yet.
    assert manager.get_user_overview('u_test1')['generated_at'] is None
    manager.backfill_user_overviews()
    first = manager.get_user_overview('u_test1')
    assert first['total'] == first['statistics']['hands'] == 1
    assert first['summary']['net_chips'] == 20
    assert first['generated_at'] > 0
    record(manager, 2, net=-5)
    restarted = HandHistoryManager(manager.storage_path)
    with monkeypatch.context() as patch:
        patch.setattr(player_statistics, 'query_statistics', lambda *_: pytest.fail('read recalculated stats'))
        patch.setattr(restarted, '_calculate_user_overview', lambda *_: pytest.fail('read scanned history'))
        restarted.backfill_user_overviews()  # Existing snapshots are not rebuilt on every restart.
        assert restarted.get_user_overview('u_test1') == first
        assert restarted.get_user_overview('unknown')['total'] == 0
    restarted.refresh_user_overviews(['u_test1'])
    updated = restarted.get_user_overview('u_test1')
    assert updated['total'] == updated['statistics']['hands'] == 2
    assert updated['summary']['net_chips'] == 15
    assert updated['generated_at'] >= first['generated_at']
    assert not any(field in json.dumps(updated) for field in ('hole_cards', 'actions', 'room_name'))
    restarted.clear_all()
    assert restarted.get_user_overview('u_test1')['total'] == 0
    assert restarted.get_user_overview('u_test1')['generated_at'] is None


@pytest.mark.parametrize('departure', ['leave', 'kick', 'disconnect', 'end', 'delete'])
def test_departure_refreshes_snapshot(tmp_path, departure):
    manager = RoomManager(str(tmp_path / 'room.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig(), room_id='cache-room')
    assert room.sit_down_player('u_test1', 'One', 0, is_test=True)
    assert room.sit_down_player('u_test2', 'Two', 1, is_test=True)
    history = manager.hand_history_manager
    record(history)
    manager.checkpoint_room(room)
    assert history.get_user_overview('u_test1')['generated_at'] is None
    operations = {
        'leave': lambda r: r.leave_player('u_test1'),
        'kick': lambda r: r.kick_player('u_test1'),
        'disconnect': lambda r: r.auto_leave_disconnected_player('u_test1'),
        'end': lambda r: r.end_room('u_test1', record_to_balance=False),
    }
    if departure == 'delete':
        manager.delete_room(room.room_id)
    else:
        manager.transact_room(room.room_id, operations[departure])
    assert history.get_user_overview('u_test1')['total'] == 1
    assert history.get_user_overview('u_test1')['generated_at'] is not None
    if departure in ('end', 'delete'):
        assert history.get_user_overview('u_test2')['generated_at'] is not None
    else:
        assert history.get_user_overview('u_test2')['generated_at'] is None


def test_failed_departure_keeps_previous_cache(tmp_path, monkeypatch):
    manager = RoomManager(str(tmp_path / 'failure.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig())
    assert room.sit_down_player('u_test1', 'One', 0, is_test=True)
    history = manager.hand_history_manager
    history.refresh_user_overviews(['u_test1'])
    before = history.get_user_overview('u_test1')
    record(history)
    monkeypatch.setattr(manager, 'save_to_storage', lambda: (_ for _ in ()).throw(OSError('checkpoint failed')))
    with pytest.raises(OSError):
        manager.transact_room(room.room_id, lambda r: r.leave_player('u_test1'))
    assert room.table.seats[0].player_id == 'u_test1'
    assert history.get_user_overview('u_test1') == before


def test_refresh_batch_is_atomic_if_calculation_fails(tmp_path, monkeypatch):
    history = HandHistoryManager(str(tmp_path / 'atomic.sqlite3'))
    history.refresh_user_overviews(['u_test1', 'u_test2'])
    before = history.get_user_overview('u_test1')
    record(history)
    query = player_statistics.query_statistics

    def failing_query(database, player_id):
        if player_id == 'u_test2':
            raise ValueError('calculation failed')
        return query(database, player_id)

    monkeypatch.setattr(player_statistics, 'query_statistics', failing_query)
    with pytest.raises(ValueError):
        history.refresh_user_overviews(['u_test1', 'u_test2'])
    assert history.get_user_overview('u_test1') == before


def test_mid_hand_departure_updates_again_when_hand_finishes(tmp_path):
    from backend.app.engine.state_machine import ActionType, Street
    manager = RoomManager(str(tmp_path / 'midhand.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig())
    for index in range(3):
        assert room.sit_down_player(f'u_test{index + 1}', str(index), index, is_test=True)
    assert room.table.start_new_hand()
    manager.transact_room(room.room_id, lambda r: r.leave_player('u_test1'))
    history = manager.hand_history_manager
    assert history.get_user_overview('u_test1')['total'] == 0
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    assert room.table.street == Street.HAND_END
    manager.checkpoint_room(room)
    snapshot = history.get_user_overview('u_test1')
    assert snapshot['total'] == snapshot['statistics']['hands'] == 1
    manager.checkpoint_room(room)
    assert history.get_user_overview('u_test1') == snapshot


def test_deferred_departure_includes_previously_departed_player(tmp_path):
    from backend.app.engine.state_machine import ActionType
    manager = RoomManager(str(tmp_path / 'deferred.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig())
    for index in range(3):
        assert room.sit_down_player(f'u_test{index + 1}', str(index), index, is_test=True)
    assert room.table.start_new_hand()
    manager.transact_room(room.room_id, lambda r: r.leave_player('u_test1'))
    actor = room.table.seats[room.table.current_turn_seat]
    assert room.table.handle_action(actor.player_id, ActionType.FOLD)
    room.pending_auto_leave_ids.add('u_test2')

    def complete_and_depart(current):
        completed = current.record_completed_hand()
        manager.hand_history_manager.record_hand(completed)
        return current.process_pending_auto_leaves()

    manager.transact_room(room.room_id, complete_and_depart)
    assert manager.hand_history_manager.get_user_overview('u_test1')['total'] == 1
    assert manager.hand_history_manager.get_user_overview('u_test2')['total'] == 1
    assert manager.hand_history_manager.get_user_overview('u_test3')['generated_at'] is None
