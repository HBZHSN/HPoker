import pytest
from fastapi import HTTPException
from backend.app.services.player_statistics import summarize, query_statistics
from backend.app.engine.card import Card
from backend.app.api.endpoints import get_my_statistics


def action(pid, act, amount=0, street='PREFLOP'):
    return dict(player_id=pid, action=act, amount=amount, street=street)


def hand(actions=(), board=(), shown=True):
    return dict(big_blind=10, board=[Card.from_str(c).to_dict() for c in board], board_2=[], actions=list(actions),
                players=[dict(player_id=p, net_chips=n, payout_chips=pay,
                              shown_cards=[Card.from_str(c).to_dict() for c in cards] if shown else [])
                         for p, n, pay, cards in [('a', 10, 20, ['As','Ah']), ('b', -10, 0, ['Ks','Kh'])]])


def test_empty_and_blinds_checks_folds():
    assert summarize([], 'a')['vpip'] is None
    s = summarize([hand([action('a','POST_BB',10), action('a','CHECK'), action('b','FOLD')])], 'a')
    assert s['vpip'] == s['pfr'] == 0
    assert s['three_bet'] is None
    assert s['win_rate'] == s['collect_rate'] == 100


def test_three_bet_denominator_calls_short_allins_and_fourbets():
    hands = [hand([action('b','RAISE',30), action('a','ALL_IN',20)]),
             hand([action('b','RAISE',30), action('a','RAISE',60), action('b','RAISE',120), action('a','CALL',60)]),
             hand([action('a','CALL',10), action('b','RAISE',30), action('a','FOLD')]),
             hand([action('a','RAISE',30), action('b','RAISE',60), action('a','RAISE',120)])]
    hands[0]['players'][0]['starting_chips'] = 20
    s = summarize(hands, 'a')
    assert s['vpip'] == 100
    assert s['pfr'] == 50
    assert s['three_bet_hands'] == 1
    assert s['three_bet_opportunities'] == 2
    assert s['three_bet'] == 50


def test_folded_refund_does_not_collect_and_postflop_not_vpip():
    s = summarize([hand([action('a','BET',20,'FLOP'), action('a','FOLD',0,'TURN')])], 'a')
    assert s['vpip'] == s['collect_rate'] == 0


def test_history_identity_required():
    with pytest.raises(HTTPException) as exc:
        get_my_statistics(authorization=None, token=None)
    assert exc.value.status_code == 401


def test_durable_statistics_scoped_and_idempotent(tmp_path):
    from backend.app.services.hand_history_manager import HandHistoryManager
    manager = HandHistoryManager(str(tmp_path / 'stats.sqlite3'))
    for room in ('one', 'two'):
        record = {**hand([action('a','CALL',10),action('b','FOLD')]), 'hand_id': room+':1',
                  'room_id':room, 'room_name':room, 'hand_number':1, 'ended_at':1,
                  'small_blind':5}
        assert manager.record_hand(record)
        assert not manager.record_hand(record)
    assert query_statistics(manager._database, 'a')['hands'] == 2
    assert query_statistics(manager._database, 'a', 'one')['hands'] == 1
    assert query_statistics(manager._database, 'unknown')['hands'] == 0


def test_uncalled_refund_without_winning_any_pot():
    h = hand()
    h['players'][0].update(contributed_chips=100, payout_chips=60, net_chips=-40)
    h['players'][1].update(contributed_chips=40, payout_chips=80, net_chips=40)
    assert summarize([h], 'a')['collect_rate'] == 0
    assert summarize([h], 'b')['collect_rate'] == 100


def test_statistics_endpoints_scope_and_history_owner(monkeypatch):
    from types import SimpleNamespace
    from backend.app.api.endpoints import get_table_player_statistics
    from backend.app.services.room_manager import room_manager
    from backend.app.services.user_manager import user_manager
    from backend.app.services import player_statistics
    calls = []
    monkeypatch.setattr(player_statistics, 'query_statistics',
                        lambda db, pid, room_id=None: calls.append((pid, room_id)) or {'hands': 0})
    monkeypatch.setattr(room_manager, 'get_room', lambda rid: SimpleNamespace(
        table=SimpleNamespace(active_seated_players=[SimpleNamespace(player_id='u_test2')])) if rid == 'table' else None)
    assert get_table_player_statistics('table', 'u_test2') == {'hands': 0}
    assert calls[-1] == ('u_test2', 'table')
    with pytest.raises(HTTPException):
        get_table_player_statistics('table', 'u_test1')
    with pytest.raises(HTTPException):
        get_table_player_statistics('missing', 'u_test2')
    _, token = user_manager.authenticate('test1', '123')
    assert get_my_statistics(authorization=f'Bearer {token}', token=None) == {'hands': 0}
    assert calls[-1] == ('u_test1', None)


def test_full_luck_public_table_matches_history_and_cache_survives_restart(tmp_path, monkeypatch):
    from backend.app.services.hand_history_manager import HandHistoryManager
    from backend.app.services import player_statistics
    manager = HandHistoryManager(str(tmp_path / 'luck.sqlite3'))
    for number in range(1, 4):
        record = {**hand([action('a','FOLD')]), 'hand_id':f'one:{number}',
                  'room_id':'one', 'room_name':'one', 'hand_number':number,
                  'ended_at':number, 'small_blind':5}
        record['players'][0]['hole_cards'] = [Card.from_str(c).to_dict() for c in ('As','Ah')]
        manager.record_hand(record)
    table = query_statistics(manager._database,'a','one')
    lifetime = query_statistics(manager._database,'a')
    assert table == lifetime
    assert table['luck'] > 50 and table['luck_samples'] == 3
    assert table['luck_version'] == 2
    assert table['luck_dimensions']['starting']['samples'] == 3
    assert table['luck_dimensions']['board']['samples'] == 0
    assert 'luck_band' not in table
    assert not any(k in str(table) for k in ('hole_cards','shown_cards','As','Ah'))
    # Durable per-hand observations, not averages of previously rounded scores.
    restarted = HandHistoryManager(manager.storage_path)
    monkeypatch.setattr(player_statistics,'hand_luck',lambda *_: pytest.fail('unexpected cache miss'))
    assert query_statistics(restarted._database,'a') == lifetime
    manager.clear_all()
    with manager._database.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM poker_hand_luck').fetchone()[0] == 0
    assert query_statistics(manager._database,'a')['luck'] == 50


def test_other_user_overview_aggregates_without_private_records(tmp_path, monkeypatch):
    from backend.app.api import endpoints
    from backend.app.services.hand_history_manager import HandHistoryManager
    from backend.app.services.user_manager import user_manager
    manager = HandHistoryManager(str(tmp_path / 'overview.sqlite3'))
    monkeypatch.setattr(endpoints, 'hand_history_manager', manager)
    for number, net in enumerate((30, -10), 1):
        record = {**hand(), 'hand_id': f'private:{number}', 'room_id': 'private',
                  'room_name': 'private table', 'hand_number': number, 'ended_at': number,
                  'small_blind': 5, 'money_mode': 'real'}
        record['players'][0].update(player_id='u_test2', net_chips=net, net_cash=net / 10,
                                    hole_cards=[Card.from_str('As').to_dict()])
        manager.record_hand(record)
    _, token = user_manager.authenticate('test1', '123')
    manager.refresh_user_overviews(['u_test2'])
    result = endpoints.get_user_overview('u_test2', authorization=f'Bearer {token}', token=None)
    assert result['total'] == result['statistics']['hands'] == 2
    assert result['summary'] == {'net_chips': 20, 'net_cash': 2, 'biggest_win': {'net_chips': 30}}
    assert not any(key in str(result) for key in (
        'hole_cards', 'shown_cards', 'hand_id', 'room_id', 'room_name', 'actions', 'private table'))
    empty = endpoints.get_user_overview('u_test1', authorization=f'Bearer {token}', token=None)
    assert empty['total'] == 0
    assert empty['summary'] == {'net_chips': 0, 'net_cash': 0, 'biggest_win': None}
    with pytest.raises(HTTPException) as exc:
        endpoints.get_user_overview('u_test2', authorization=None, token=None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        endpoints.get_user_overview('missing', authorization=f'Bearer {token}', token=None)
    assert exc.value.status_code == 404
    # Selecting another profile never changes ownership of the private history API.
    own = endpoints.get_my_statistics(authorization=f'Bearer {token}', token=None, room_id=None)
    assert own['hands'] == 0
