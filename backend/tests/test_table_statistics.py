"""Clicks read snapshots; background work cannot publish mixed or cleared history."""
import asyncio
import json
import threading

import pytest

from backend.app.engine.card import Card
from backend.app.services.hand_history_manager import HandHistoryManager
from backend.app.services import player_statistics


def record(history, number=1, room='table'):
    return history.record_hand({
        'hand_id': f'{room}:{number}', 'room_id': room, 'room_name': room,
        'hand_number': number, 'ended_at': number, 'small_blind': 5, 'big_blind': 10,
        'board': [Card.from_str(c).to_dict() for c in ('2s', '7h', '9d', 'Jc', 'Qs')],
        'actions': [{'player_id': p, 'street': 'PREFLOP', 'action': 'ALL_IN', 'amount': 100}
                    for p in ('u_test1', 'u_test2')],
        'players': [{'player_id': p, 'starting_chips': 100, 'contributed_chips': 100,
                     'net_chips': net, 'payout_chips': 100 + net,
                     'hole_cards': [Card.from_str(c).to_dict() for c in cards],
                     'shown_cards': [Card.from_str(c).to_dict() for c in cards]}
                    for p, cards, net in [('u_test1', ('As', 'Ah'), 100), ('u_test2', ('Ks', 'Kh'), -100)]],
    })


def test_snapshot_exact_restart_no_click_computation_and_clear(tmp_path, monkeypatch):
    history = HandHistoryManager(str(tmp_path / 'stats.sqlite3'))
    ids = ['u_test1', 'u_test2', 'new-player']
    assert history.get_table_statistics('table', ids)['u_test1']['hands'] == 0
    record(history)
    record(history, room='other')
    assert history.get_table_statistics('table', ids)['u_test1']['updating']
    assert history.refresh_table_statistics('table')
    expected = {p: {**player_statistics.query_statistics(history._database, p, 'table'), 'updating': False}
                for p in ids}
    assert history.get_table_statistics('table', ids) == expected
    assert not any(key in json.dumps(expected) for key in ('hole_cards', 'shown_cards', 'actions', 'As', 'Kh'))
    history = HandHistoryManager(history.storage_path)
    with monkeypatch.context() as patch:
        patch.setattr(player_statistics, 'query_statistics', lambda *_: pytest.fail('read recomputed'))
        history.seed_table_statistics()
        assert not history.refresh_table_statistics('table')
        assert history.get_table_statistics('table', ids) == expected
        assert not record(history)  # Idempotent recording does not dirty the snapshot.
        assert not history.refresh_table_statistics('table')
    record(history, 2)
    stale = history.get_table_statistics('table', ids)['u_test1']
    assert stale['hands'] == 1 and stale['updating']
    assert history.refresh_table_statistics('table')
    assert history.get_table_statistics('table', ids)['u_test1']['hands'] == 2
    history.clear_all()
    assert history.get_table_statistics('table', ids)['u_test1']['hands'] == 0
    assert not history.refresh_table_statistics('table')


@pytest.mark.parametrize('change', ['new-hand', 'clear', 'clear-recreate', 'failure'])
def test_changed_history_and_failure_never_publish_partial_results(tmp_path, monkeypatch, change):
    history = HandHistoryManager(str(tmp_path / 'race.sqlite3'))
    record(history)
    history.refresh_table_statistics('table')
    record(history, 2)
    query = player_statistics.query_statistics
    changed = False

    def compute(*args):
        nonlocal changed
        value = query(*args)
        if not changed:
            changed = True
            if change == 'new-hand':
                record(history, 3)
            elif change.startswith('clear'):
                history.clear_all()
                if change == 'clear-recreate':
                    record(history)
                    record(history, 2)
            else:
                raise ValueError('worker failure')
        return value

    with monkeypatch.context() as patch:
        patch.setattr(player_statistics, 'query_statistics', compute)
        if change == 'failure':
            with pytest.raises(ValueError):
                history.refresh_table_statistics('table')
        else:
            assert not history.refresh_table_statistics('table')
    snapshot = history.get_table_statistics('table', ['u_test1'])['u_test1']
    assert snapshot['hands'] == (0 if change.startswith('clear') else 1)
    history.refresh_table_statistics('table')
    assert history.get_table_statistics('table', ['u_test1'])['u_test1']['hands'] == {
        'new-hand': 3, 'clear': 0, 'clear-recreate': 2, 'failure': 2,
    }[change]


def test_legacy_seed_and_version_rebuild(tmp_path):
    history = HandHistoryManager(str(tmp_path / 'legacy.sqlite3'))
    record(history)
    with history._database.connection(write=True) as connection:
        connection.execute('DELETE FROM poker_table_statistics')
    history.seed_table_statistics()
    assert history.refresh_table_statistics('table')
    with history._database.connection(write=True) as connection:
        connection.execute('UPDATE poker_table_statistics SET version=0')
    assert history.get_table_statistics('table', ['u_test1'])['u_test1']['updating']
    assert history.refresh_table_statistics('table')


def test_background_computation_leaves_event_loop_and_snapshot_reads_available(tmp_path, monkeypatch):
    from backend.app.services import table_statistics as worker
    from backend.app.models.room import RoomConfig
    from backend.app.services.room_manager import RoomManager
    manager = RoomManager(str(tmp_path / 'worker.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig(), room_id='table')
    history = manager.hand_history_manager
    record(history)
    history.refresh_table_statistics('table')
    record(history, 2)
    started, release = threading.Event(), threading.Event()
    query = player_statistics.query_statistics
    main_thread = threading.get_ident()
    pushed = []

    def slow_query(*args):
        assert threading.get_ident() != main_thread
        started.set()
        assert release.wait(3)
        return query(*args)

    async def broadcast(current_room, *, checkpoint):
        assert current_room is room and checkpoint is False
        pushed.append(history.get_table_statistics('table', ['u_test1']))

    monkeypatch.setattr(worker, 'room_manager', manager)
    monkeypatch.setattr(worker, 'hand_history_manager', history)
    monkeypatch.setattr(worker.ws_manager, 'broadcast_room_state', broadcast)
    monkeypatch.setattr(player_statistics, 'query_statistics', slow_query)

    async def scenario():
        task = asyncio.create_task(worker.refresh_active_table_statistics())
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.01)
            assert started.is_set()
            assert history.get_table_statistics('table', ['u_test1'])['u_test1']['hands'] == 1
        finally:
            release.set()
            await task
        assert pushed[0]['u_test1']['hands'] == 2
        stop = asyncio.Event()
        task = asyncio.create_task(worker.maintain_table_statistics(stop))
        await asyncio.sleep(.01)
        stop.set()
        await asyncio.wait_for(task, 1)

    asyncio.run(scenario())


def test_websocket_preloads_public_stats_for_self_opponent_and_spectator(tmp_path, monkeypatch):
    from backend.app.models.room import RoomConfig
    from backend.app.services import hand_history_manager as history_module
    from backend.app.services.room_manager import RoomManager
    from backend.app.websocket.connection_manager import ConnectionManager
    manager = RoomManager(str(tmp_path / 'push.sqlite3'))
    room = manager.create_room('u_test1', RoomConfig(), room_id='table')
    for i in range(2):
        room.sit_down_player(f'u_test{i + 1}', str(i), i, is_test=True)
    history = manager.hand_history_manager
    record(history)
    history.refresh_table_statistics('table')
    monkeypatch.setattr(history_module, 'hand_history_manager', history)
    monkeypatch.setattr(player_statistics, 'query_statistics', lambda *_: pytest.fail('broadcast computed stats'))
    sent = []

    class Socket:
        async def send_text(self, message):
            sent.append(json.loads(message))

    ws = ConnectionManager()
    for viewer in ('u_test1', 'u_test2', 'spectator'):
        socket = Socket()
        ws.room_connections.setdefault('table', set()).add(socket)
        ws.socket_info[socket] = ('table', viewer)
    asyncio.run(ws.broadcast_room_state(room, checkpoint=False))
    assert len(sent) == 3
    for message in sent:
        assert message['event'] == 'ROOM_STATE'
        stats = message['payload']['player_statistics']
        assert set(stats) == {'u_test1', 'u_test2'}
        assert all(item['hands'] == 1 and not item['updating'] for item in stats.values())
        assert not any(key in json.dumps(stats) for key in ('hole_cards', 'shown_cards', 'actions', 'As', 'Kh'))
