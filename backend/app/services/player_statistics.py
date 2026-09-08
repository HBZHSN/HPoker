"""Aggregate completed hands; never return cards or individual action records."""
import json
from backend.app.services.comprehensive_luck import (
    VERSION, aggregate_luck, hand_luck,
)


def summarize(hands, player_id):
    totals = dict(hands=0, vpip_hands=0, pfr_hands=0, three_bet_hands=0,
                  three_bet_opportunities=0, winning_hands=0, collected_hands=0,
                  showdown_hands=0)
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
        uncalled = max(0, hero.get('contributed_chips', 0) - max(
            (p.get('contributed_chips', 0) for p in players if p is not hero), default=0))
        totals['collected_hands'] += hero['payout_chips'] > uncalled and player_id not in folded
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
    def rate(n, d):
        return round(100 * n / d, 1) if d else None
    return {**totals,
            'vpip': rate(totals['vpip_hands'], totals['hands']),
            'pfr': rate(totals['pfr_hands'], totals['hands']),
            'three_bet': rate(totals['three_bet_hands'], totals['three_bet_opportunities']),
            'win_rate': rate(totals['winning_hands'], totals['hands']),
            'collect_rate': rate(totals['collected_hands'], totals['hands']),
            'showdown_rate': rate(totals['showdown_hands'], totals['hands'])}


def query_statistics(database, player_id, room_id=None):
    # Only the target's private cards are read internally, never opponents'.
    # Raw cards and per-hand luck observations must never enter an API response.
    scope = ' AND h.room_id = ?' if room_id is not None else ''
    params = [player_id, player_id] + ([room_id] if room_id is not None else [])
    with database.connection() as connection:
        rows = connection.execute('''SELECT h.hand_id, h.big_blind, h.board_json,
            h.board_2_json, h.actions_json, p.player_id, p.shown_cards_json,
            p.net_chips, p.payout_chips, p.starting_chips, p.contributed_chips,
            CASE WHEN p.player_id = ? THEN p.hole_cards_json ELSE '{"cards":[]}' END AS hero_cards_json FROM poker_hands h
            JOIN poker_hand_players p ON p.hand_id = h.hand_id
            WHERE EXISTS (SELECT 1 FROM poker_hand_players hero
                WHERE hero.hand_id = h.hand_id AND hero.player_id = ?)''' + scope + ' ORDER BY h.ended_at, h.hand_id, p.player_id', params).fetchall()
        cached = {r['hand_id']: json.loads(r['stats_json']) for r in connection.execute(
            'SELECT hand_id, stats_json FROM poker_hand_luck WHERE player_id = ? AND version = ?',
            (player_id, VERSION)).fetchall()}
    hands = {}
    for row in rows:
        hand = hands.setdefault(row['hand_id'], {
            'hand_id': row['hand_id'], 'big_blind': row['big_blind'], 'board': json.loads(row['board_json'])['cards'],
            'board_2': json.loads(row['board_2_json'])['cards'],
            'actions': json.loads(row['actions_json'])['actions'], 'players': []})
        hand['players'].append({'player_id': row['player_id'], 'net_chips': row['net_chips'],
                               'payout_chips': row['payout_chips'], 'starting_chips': row['starting_chips'],
                               'contributed_chips': row['contributed_chips'],
                               'hole_cards': json.loads(row['hero_cards_json'])['cards'],
                               'shown_cards': json.loads(row['shown_cards_json'])['cards']})
    completed = list(hands.values())
    observations, pending = [], []
    for hand in completed:
        hand_id = hand['hand_id']
        observation = cached.get(hand_id)
        if observation is None:
            observation = hand_luck(hand, player_id)
            pending.append((hand_id, player_id, VERSION, json.dumps(observation)))
        observations.append(observation)
    if pending:
        with database.connection(write=True) as connection:
            # Recheck existence in case history was cleared during computation.
            connection.executemany(
                """INSERT OR IGNORE INTO poker_hand_luck(hand_id, player_id, version, stats_json)
                   SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM poker_hand_players
                       WHERE hand_id = ? AND player_id = ?)""",
                [(*row, row[0], row[1]) for row in pending])
    luck = aggregate_luck(observations)
    return {**summarize(completed, player_id), **luck}
