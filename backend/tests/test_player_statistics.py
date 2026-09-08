import pytest
from fastapi import HTTPException
from backend.app.services.player_statistics import summarize, river_luck, query_statistics
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
    assert summarize([], 'a')['luck'] == 50
    s = summarize([hand([action('a','POST_BB',10), action('a','CHECK'), action('b','FOLD')])], 'a')
    assert s['vpip'] == s['pfr'] == 0
    assert s['three_bet'] is None
    assert s['win_rate'] == s['collect_rate'] == 100
    assert s['luck_samples'] == 0


def test_three_bet_denominator_calls_short_allins_and_fourbets():
    hands = [hand([action('b','RAISE',30), action('a','ALL_IN',20)]),
             hand([action('b','RAISE',30), action('a','RAISE',60), action('b','RAISE',120), action('a','CALL',60)]),
             hand([action('a','CALL',10), action('b','RAISE',30), action('a','FOLD')]),
             hand([action('a','RAISE',30), action('b','RAISE',60), action('a','RAISE',120)])]
    s = summarize(hands, 'a')
    assert s['vpip'] == 100
    assert s['pfr'] == 50
    assert s['three_bet_hands'] == 1
    assert s['three_bet_opportunities'] == 3
    assert s['three_bet'] == 33.3


def test_folded_refund_does_not_collect_and_postflop_not_vpip():
    s = summarize([hand([action('a','BET',20,'FLOP'), action('a','FOLD',0,'TURN')])], 'a')
    assert s['vpip'] == s['collect_rate'] == 0


def test_exact_river_luck_symmetric_tie_and_privacy():
    board = ('2c','3d','7h','9s','Kd')
    luck = river_luck(board, (('As','Ah'), ('Ks','Kh')))
    assert luck[0] == pytest.approx(-42/44)
    assert sum(luck) == pytest.approx(0)
    s = summarize([hand(board=board)], 'b')
    assert 50 < s['luck'] < 55
    assert s['luck_samples'] == 1
    assert summarize([hand(board=board, shown=False)], 'b')['luck_samples'] == 0
    rit = hand(board=board)
    rit['board_2'] = rit['board']
    assert summarize([rit], 'a')['luck_samples'] == 0
    assert river_luck(('As','Ks','Qs','Js','Ts'), (('2c','3c'), ('2d','3d'))) == pytest.approx((0, 0))
    assert not any('cards' in key or 'actions' in key for key in s)


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
