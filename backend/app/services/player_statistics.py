"""Aggregate completed hands; never return cards or individual action records."""
import json
from functools import lru_cache

from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.evaluator import evaluate_hand


@lru_cache(maxsize=4096)
def river_luck(board, holdings):
    """Equal-share showdown result minus exact turn equity, using PUBLIC cards only.

    This measures river runout luck, not skill, money EV, or all-in EV. RIT is
    excluded because its second runout has a different conditional card pool.
    """
    cards = [Card.from_str(c) for c in board]
    hands = [[Card.from_str(c) for c in hand] for hand in holdings]
    known = set(cards[:4] + [c for hand in hands for c in hand])
    if len(known) != 4 + 2 * len(hands) or cards[4] in known:
        return None
    def shares(river):
        scores = [evaluate_hand(h + cards[:4] + [river]).score_vector for h in hands]
        best = max(scores)
        count = scores.count(best)
        return [1 / count if score == best else 0 for score in scores]
    possible = [Card(r, s) for s in Suit for r in Rank if Card(r, s) not in known]
    expected = [0.0] * len(hands)
    for river in possible:
        for i, share in enumerate(shares(river)):
            expected[i] += share / len(possible)
    return tuple(a - e for a, e in zip(shares(cards[4]), expected))


def summarize(hands, player_id):
    totals = dict(hands=0, vpip_hands=0, pfr_hands=0, three_bet_hands=0,
                  three_bet_opportunities=0, winning_hands=0, collected_hands=0,
                  showdown_hands=0, luck_samples=0)
    luck_sum = 0.0
    for hand in hands:
        players = hand['players']
        hero = next((p for p in players if p['player_id'] == player_id), None)
        if hero is None:
            continue
        totals['hands'] += 1
        totals['winning_hands'] += hero['net_chips'] > 0
        # Uncalled excess alone is a refund, not a collected pot. A folded
        # player cannot win a pot, even when a refund is recorded as payout.
        folded = {a['player_id'] for a in hand['actions'] if a['action'] == 'FOLD'}
        totals['collected_hands'] += hero['payout_chips'] > 0 and player_id not in folded
        highest = hand['big_blind']
        raises = 0
        vpip = pfr = opportunity = three_bet = False
        for a in hand['actions']:
            if a['street'] != 'PREFLOP':
                continue
            action, amount = a['action'], a['amount']
            if action.startswith('POST_'):
                continue
            is_raise = action in ('BET', 'RAISE', 'ALL_IN') and amount > highest
            if a['player_id'] == player_id:
                if raises == 1 and hero.get('starting_chips', float('inf')) > highest:
                    opportunity = True
                    three_bet |= is_raise
                vpip |= action in ('CALL', 'BET', 'RAISE', 'ALL_IN') and amount > 0
                pfr |= is_raise
            if is_raise:
                highest = amount
                raises += 1
        for key, value in [('vpip_hands', vpip), ('pfr_hands', pfr),
                           ('three_bet_opportunities', opportunity), ('three_bet_hands', three_bet)]:
            totals[key] += value
        contenders = [p for p in players if p['player_id'] not in folded]
        showdown = len(contenders) > 1 and len(hand['board']) == 5
        totals['showdown_hands'] += showdown and player_id not in folded
        if (showdown and not hand['board_2'] and player_id not in folded
                and all(len(p['shown_cards']) == 2 for p in contenders)):
            residuals = river_luck(tuple(c['notation'] for c in hand['board']),
                                  tuple(tuple(c['notation'] for c in p['shown_cards']) for p in contenders))
            if residuals is not None:
                totals['luck_samples'] += 1
                luck_sum += residuals[next(i for i, p in enumerate(contenders) if p['player_id'] == player_id)]
    def rate(n, d):
        return round(100 * n / d, 1) if d else None
    return {**totals,
            'vpip': rate(totals['vpip_hands'], totals['hands']),
            'pfr': rate(totals['pfr_hands'], totals['hands']),
            'three_bet': rate(totals['three_bet_hands'], totals['three_bet_opportunities']),
            'win_rate': rate(totals['winning_hands'], totals['hands']),
            'collect_rate': rate(totals['collected_hands'], totals['hands']),
            'showdown_rate': rate(totals['showdown_hands'], totals['hands']),
            'luck': round(max(0, min(100, 50 + 50 * luck_sum / (totals['luck_samples'] + 10))), 1)}


def query_statistics(database, player_id, room_id=None):
    # No LIMIT: lifetime counters include the entire durable history. Only
    # public shown cards are selected; private hole_cards_json is never read.
    scope = ' AND h.room_id = ?' if room_id is not None else ''
    params = [player_id] + ([room_id] if room_id is not None else [])
    with database.connection() as connection:
        rows = connection.execute('''SELECT h.hand_id, h.big_blind, h.board_json,
            h.board_2_json, h.actions_json, p.player_id, p.shown_cards_json,
            p.net_chips, p.payout_chips, p.starting_chips FROM poker_hands h
            JOIN poker_hand_players p ON p.hand_id = h.hand_id
            WHERE EXISTS (SELECT 1 FROM poker_hand_players hero
                WHERE hero.hand_id = h.hand_id AND hero.player_id = ?)''' + scope, params).fetchall()
    hands = {}
    for row in rows:
        hand = hands.setdefault(row['hand_id'], {
            'big_blind': row['big_blind'], 'board': json.loads(row['board_json'])['cards'],
            'board_2': json.loads(row['board_2_json'])['cards'],
            'actions': json.loads(row['actions_json'])['actions'], 'players': []})
        hand['players'].append({'player_id': row['player_id'], 'net_chips': row['net_chips'],
                               'payout_chips': row['payout_chips'], 'starting_chips': row['starting_chips'],
                               'shown_cards': json.loads(row['shown_cards_json'])['cards']})
    return summarize(hands.values(), player_id)
