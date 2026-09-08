import random
import pytest
from backend.app.engine.card import Card
from backend.app.engine.evaluator import evaluate_hand
from backend.app.services.comprehensive_luck import (
    DECK, WEIGHTS, score, shares, starting_table, starting_values, fixed_equity,
    hand_luck, aggregate_luck, action_snapshots, all_in_samples,
)


def cards(*values):
    return tuple(Card.from_str(c) for c in values)


def serial(values):
    return [c.to_dict() for c in cards(*values)]


def make_hand(board=('2c','3d','7h','9s','Kd'), second=()):
    return {'big_blind': 10, 'board': serial(board), 'board_2': serial(second),
            'actions': [dict(player_id='a', action='ALL_IN', amount=100, street='TURN'),
                        dict(player_id='b', action='CALL', amount=100, street='TURN')],
            'players': [dict(player_id=pid, hole_cards=serial(hole), shown_cards=serial(hole),
                             starting_chips=100, contributed_chips=100)
                        for pid, hole in [('a',('As','Ah')), ('b',('Ks','Kh'))]]}


def test_fast_simulation_evaluator_matches_engine():
    rng = random.Random(29)
    for size in (5, 6, 7):
        for _ in range(500):
            hand = rng.sample(DECK, size)
            assert score(hand) == evaluate_hand(hand).score_vector
    for value in [('As','2s','3s','4s','5s','Kh','Kd'),
                  ('As','Ks','Qs','Js','Ts','2d','2h'),
                  ('As','Ah','Ad','Ks','Kh','Kd','2c'),
                  ('As','Ah','Ks','Kh','Qs','Qh','2c'),
                  ('As','Ah','Ad','Ac','Ks','Kh','2c')]:
        assert score(cards(*value)) == evaluate_hand(cards(*value)).score_vector


def test_starting_calibration_combo_weighting_and_neutrality():
    table = starting_table()
    assert len(table) == 169
    assert sum(v['combinations'] for v in table.values()) == 1326
    assert sum((2*v['percentile']-1)*v['combinations'] for v in table.values()) == pytest.approx(0)
    assert starting_values(cards('As','Ah'))[1] > .98
    assert starting_values(cards('7s','2h'))[1] < -.8
    assert starting_values(cards('As','Ah')) == starting_values(cards('Ad','Ac'))


def test_exact_turn_equity_ties_and_blockers():
    holdings = (cards('As','Ah'), cards('Ks','Kh'))
    assert fixed_equity(holdings, cards('2c','3d','7h','9s')) == pytest.approx((42/44,2/44))
    assert fixed_equity(holdings, cards('2c','3d','7h','9s'), cards('Kd')) == pytest.approx((42/43,1/43))
    assert shares((cards('2c','3c'),cards('2d','3d')),cards('As','Ks','Qs','Js','Ts')) == (.5,.5)
    assert sum(fixed_equity(holdings, ())) == pytest.approx(1)


def test_starting_includes_preflop_folds_but_no_future_board():
    h = make_hand()
    h['actions'] = [dict(player_id='a', action='FOLD', amount=0, street='PREFLOP')]
    result = hand_luck(h, 'a')
    assert result['starting'][0] > .98
    assert result['starting'][2] == 1
    assert all(result[k][2] == 0 for k in ('board','matchup','all_in'))
    h['actions'][0]['street'] = 'FLOP'
    first = hand_luck(h, 'a')
    h['board'][-1] = serial(('Ac',))[0]
    assert hand_luck(h, 'a') == first  # unseen river cannot affect folded hero


def test_allin_turn_badbeat_and_river_commitment_not_luck():
    h = make_hand()
    samples = all_in_samples(h, 'a')
    assert samples == pytest.approx([(-42/44, 4)])
    assert all_in_samples(h, 'b') == pytest.approx([(42/44,4)])
    h['actions'][0]['street'] = h['actions'][1]['street'] = 'RIVER'
    assert all_in_samples(h, 'a') == []


def test_rit_average_runouts():
    h = make_hand(second=('2c','3d','7h','9s','4d'))
    assert all_in_samples(h, 'a') == pytest.approx([(.5-42/44,4)])


def test_replay_delta_and_target_bets():
    h = make_hand()
    h['actions'] = [dict(player_id='a', action=act, amount=amount, street=street)
                    for act, amount, street in [('POST_SB',5,'PREFLOP'),('CALL',5,'PREFLOP'),
                                                ('RAISE',30,'PREFLOP'),('ALL_IN',70,'FLOP')]]
    snaps = list(action_snapshots(h))
    assert [s[1]['a'] for s in snaps] == [5,10,30,100]
    assert snaps[-1][3] == {'a'}


def test_side_pots_locks_and_refund_exclusion():
    h = make_hand()
    h['players'][1]['starting_chips'] = h['players'][1]['contributed_chips'] = 200
    h['players'].append(dict(player_id='c', hole_cards=serial(('Qs','Qh')),shown_cards=serial(('Qs','Qh')),
                             starting_chips=300, contributed_chips=250))
    h['actions'] = [dict(player_id=p, action=a, amount=v, street=s) for p,a,v,s in [
        ('a','ALL_IN',100,'FLOP'),('b','CALL',100,'FLOP'),('c','CALL',100,'FLOP'),
        ('b','ALL_IN',100,'TURN'),('c','RAISE',150,'TURN')]]
    assert len(all_in_samples(h,'a')) == 1
    assert len(all_in_samples(h,'b')) == 2
    assert len(all_in_samples(h,'c')) == 2  # excess 50 is a refund, no third sample
    # Main pot is not treated as fixed while two opponents can still act.
    results = all_in_samples(h,'a')
    h['actions'][-1]['street'] = 'RIVER'
    assert results and not all_in_samples(h,'a')


def test_missing_records_and_hidden_showdown_skip_dimensions():
    h = make_hand()
    h['players'][1]['shown_cards'] = []
    r = hand_luck(h,'a')
    assert r['starting'][2] == r['board'][2] == 1
    assert r['matchup'][2] == r['all_in'][2] == 0
    h['players'][0]['hole_cards'] = []
    assert all(v[2] == 0 for v in hand_luck(h,'a').values())


def test_aggregation_weights_shrinkage():
    neutral = {k:[0,1,1] for k in WEIGHTS}
    good = {k:[1,1,1] for k in WEIGHTS}
    assert aggregate_luck([])['luck'] == 50
    assert aggregate_luck([good])['luck'] == pytest.approx(54.5)
    assert aggregate_luck([good]*100)['luck'] > 95
    assert aggregate_luck([neutral]*100)['luck'] == 50


def test_same_allin_result_ignores_money_deductions_and_net_profit():
    h = make_hand()
    original = hand_luck(h, 'a')
    h['players'][0].update(net_chips=999999, payout_chips=999999)
    assert hand_luck(h, 'a') == original


def test_board_improvement_and_cooler_have_opposite_meaning():
    # Top set improving to quads is good board luck; a lower full house
    # losing to quads is bad matchup luck, despite strong absolute hand value.
    h = make_hand(board=('Ac','Ad','Kc','2s','2d'))
    a = hand_luck(h,'a')
    b = hand_luck(h,'b')
    assert a['board'][0] > 0
    assert b['board'][0] > 0
    assert b['matchup'][0] < -.9


def test_allin_folded_cards_not_used_as_known_blockers():
    h = make_hand()
    h['players'].append(dict(player_id='c', hole_cards=serial(('Kd','4s')),shown_cards=[],
                             starting_chips=100, contributed_chips=0))
    h['actions'].insert(0,dict(player_id='c',action='FOLD',amount=0,street='PREFLOP'))
    assert all_in_samples(h,'a') == pytest.approx([(-42/44,4)])
