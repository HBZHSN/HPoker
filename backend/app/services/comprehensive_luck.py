"""Versioned, deterministic descriptive luck estimates; never used for dealing.

Monte Carlo estimates use a local seeded RNG for reproducible analysis only.
Live dealing remains secrets-based. Scores describe selected observed samples,
not a causal separation of skill and luck or a prediction of the next hand.
"""
from collections import Counter
from functools import lru_cache
from itertools import combinations
from pathlib import Path
import hashlib
import json
import math
import random

from backend.app.engine.card import Card, Rank, Suit
from backend.app.engine.pot import PotManager

VERSION = 1
WEIGHTS = {'starting': .35, 'board': .25, 'matchup': .20, 'all_in': .20}
STREETS = {'PREFLOP': 0, 'FLOP': 3, 'TURN': 4, 'RIVER': 5}
DECK = tuple(Card(r, s) for s in Suit for r in Rank)


def score(cards):
    """Allocation-light 5–7 card comparison, differential-tested against engine."""
    counts = Counter(c.rank.value for c in cards)
    ranks = sorted(counts, reverse=True)
    def straight(values):
        values = set(values)
        if 14 in values:
            values.add(1)
        return next((r for r in range(14, 4, -1) if all(r-i in values for i in range(5))), 0)
    flush = next((sorted((c.rank.value for c in cards if c.suit == s), reverse=True)
                  for s in Suit if sum(c.suit == s for c in cards) >= 5), None)
    if flush and (top := straight(flush)):
        return (10 if top == 14 else 9, top)
    fours = [r for r in ranks if counts[r] == 4]
    trips = [r for r in ranks if counts[r] >= 3]
    if fours:
        return (8, fours[0], next(r for r in ranks if r != fours[0]))
    if trips and (pairs := [r for r in ranks if r != trips[0] and counts[r] >= 2]):
        return (7, trips[0], pairs[0])
    if flush:
        return (6, *flush[:5])
    if top := straight(ranks):
        return (5, top)
    if trips:
        return (4, trips[0], *[r for r in ranks if r != trips[0]][:2])
    pairs = [r for r in ranks if counts[r] >= 2]
    if len(pairs) >= 2:
        return (3, *pairs[:2], next(r for r in ranks if r not in pairs[:2]))
    if pairs:
        return (2, pairs[0], *[r for r in ranks if r != pairs[0]][:3])
    return (1, *ranks[:5])


def rng_for(value):
    return random.Random(int.from_bytes(hashlib.sha256(repr(value).encode()).digest()[:8], 'big'))


def parse(cards):
    return tuple(Card.from_str(c['notation']) for c in cards)


def shares(holdings, board):
    scores = [score(h + board) for h in holdings]
    best = max(scores)
    winners = scores.count(best)
    return tuple(1 / winners if s == best else 0 for s in scores)


@lru_cache(maxsize=8192)
def random_equity(hero, board=(), opponents=1, iterations=768):
    remaining = [c for c in DECK if c not in hero + board]
    rng = rng_for((hero, board, opponents, iterations))
    total = 0.0
    for _ in range(iterations):
        draw = rng.sample(remaining, 5 - len(board) + 2 * opponents)
        completed = board + tuple(draw[:5-len(board)])
        other = draw[5-len(board):]
        holdings = (hero,) + tuple(tuple(other[i:i+2]) for i in range(0, len(other), 2))
        total += shares(holdings, completed)[0]
    return total / iterations


def starting_key(hero):
    a, b = sorted(hero, key=lambda c: c.rank.value, reverse=True)
    return f'{a.rank.symbol}{b.rank.symbol}' + ('' if a.rank == b.rank else 's' if a.suit == b.suit else 'o')


@lru_cache(maxsize=1)
def starting_table():
    return json.loads(Path(__file__).with_name('starting_luck_table.json').read_text())['hands']


def starting_values(hero):
    item = starting_table()[starting_key(hero)]
    return item['equity'], 2 * item['percentile'] - 1


@lru_cache(maxsize=4096)
def fixed_equity(holdings, board, blockers=()):
    """Exact turn/river, deterministic 2048-runout estimate on earlier streets."""
    known = set(board + blockers + tuple(c for h in holdings for c in h))
    remaining = [c for c in DECK if c not in known]
    missing = 5 - len(board)
    if missing <= 1:
        runouts = combinations(remaining, missing)
    else:
        rng = rng_for((holdings, board, blockers))
        runouts = (tuple(rng.sample(remaining, missing)) for _ in range(2048))
    total = [0.0] * len(holdings)
    count = 0
    for runout in runouts:
        count += 1
        for i, value in enumerate(shares(holdings, board + tuple(runout))):
            total[i] += value
    return tuple(value / count for value in total)


def action_snapshots(hand):
    """Replay immutable actions (CALL is delta; RAISE/ALL_IN are street totals)."""
    paid = {p['player_id']: 0 for p in hand['players']}
    starts = {p['player_id']: p.get('starting_chips', 0) for p in hand['players']}
    bets, folded, previous = {}, set(), None
    for action in hand['actions']:
        street, pid, kind = action['street'], action['player_id'], action['action']
        if street not in STREETS or pid not in paid:
            continue
        if street != previous:
            bets = {}
            previous = street
        amount = action['amount']
        delta = 0
        if kind in ('POST_SB', 'POST_BB', 'CALL'):
            delta = amount
        elif kind in ('RAISE', 'BET', 'ALL_IN'):
            delta = max(0, amount - bets.get(pid, 0))
        elif kind == 'FOLD':
            folded.add(pid)
        paid[pid] += delta
        bets[pid] = bets.get(pid, 0) + delta
        allin = {p for p in paid if starts[p] > 0 and paid[p] >= starts[p]}
        pending = {p for p in paid if p not in folded | allin and bets.get(p, 0) < max(bets.values(), default=0)}
        yield STREETS[street], dict(paid), set(folded), allin, pending


def all_in_samples(hand, hero_id):
    """Per-pot frozen exposure, excluding refunds and post-river commitments.

    Require final tier funding and final eligibility to be settled; do not
    pretend an early shove fixes equity while side-pot opponents can still act.
    """
    players = {p['player_id']: p for p in hand['players']}
    manager = PotManager()
    manager.total_contributions.update({pid: p.get('contributed_chips', 0) for pid, p in players.items()})
    manager.folded_players.update(a['player_id'] for a in hand['actions'] if a['action'] == 'FOLD')
    pots, _ = manager.calculate_pots()
    boards = [parse(hand['board'])]
    if hand.get('board_2'):
        boards.append(parse(hand['board_2']))
    if any(len(b) != 5 for b in boards):
        return []
    snapshots = list(action_snapshots(hand))
    samples = []
    for pot in pots:
        ids = sorted(pot.eligible_players)
        if hero_id not in ids or len(ids) < 2:
            continue
        if any(len(players[pid].get('shown_cards', [])) != 2 for pid in ids):
            continue
        holdings = tuple(parse(players[pid]['shown_cards']) for pid in ids)
        # A merged pot's funding threshold is its highest eligible commitment.
        cap = max(players[pid].get('contributed_chips', 0) for pid in ids)
        # Lowest all-in seat bounds the current tier; derive the actual upper
        # boundary from all contribution levels having this same eligibility.
        levels = sorted(set(manager.total_contributions.values()))
        tiers = [level for level in levels if {p for p in players if p not in manager.folded_players and manager.total_contributions[p] >= level} == set(ids)]
        if tiers:
            cap = max(tiers)
        lock = None
        for street, paid, folded, allin, pending in snapshots:
            if street >= 5:
                break
            funded = all(paid[pid] >= min(manager.total_contributions[pid], cap) for pid in players)
            eligibility_fixed = all(pid in folded for pid in manager.folded_players)
            if funded and eligibility_fixed and not pending and len(set(ids) - allin) <= 1 and set(ids) & allin:
                lock = street
                break
        if lock is None:
            continue
        # RIT boards share their initial prefix. No later board is treated as
        # known at lock; by symmetry each runout has the same marginal equity.
        if any(b[:lock] != boards[0][:lock] for b in boards):
            continue
        blockers = tuple(c for pid, p in players.items() if pid not in ids and pid not in manager.folded_players
                         for c in parse(p.get('shown_cards', [])))
        expected = fixed_equity(holdings, boards[0][:lock], blockers)[ids.index(hero_id)]
        actual = sum(shares(holdings, b)[ids.index(hero_id)] for b in boards) / len(boards)
        weight = min(4.0, math.sqrt(pot.amount / max(1, hand['big_blind'])))
        samples.append((actual - expected, weight))
    return samples


def hand_luck(hand, player_id):
    result = {key: [0.0, 0.0, 0] for key in WEIGHTS}  # weighted sum, weight, observations
    hero = next(p for p in hand['players'] if p['player_id'] == player_id)
    hole = parse(hero.get('hole_cards', []))
    if len(hole) != 2:
        return result  # Old incomplete records are not fabricated as neutral samples.
    baseline, starting = starting_values(hole)
    result['starting'] = [starting, 1.0, 1]
    fold = next((STREETS.get(a['street'], 0) for a in hand['actions']
                 if a['player_id'] == player_id and a['action'] == 'FOLD'), None)
    boards = [parse(hand['board'])]
    if hand.get('board_2'):
        boards.append(parse(hand['board_2']))
    improvements = []
    for board in boards:
        reached = min(len(board), fold if fold is not None else 5)
        # Equity is a martingale under random board reveals. Endpoint minus
        # preflop equity equals the sum of street changes, with no triple count.
        if reached >= 3:
            improvements.append(random_equity(hole, board[:reached]) - baseline)
    if improvements:
        result['board'] = [sum(improvements) / len(improvements), 1.0, 1]
    folded = {a['player_id'] for a in hand['actions'] if a['action'] == 'FOLD'}
    contenders = [p for p in hand['players'] if p['player_id'] not in folded]
    if (fold is None and len(contenders) >= 2 and all(len(b) == 5 for b in boards)
            and all(len(p.get('shown_cards', [])) == 2 for p in contenders)):
        holdings = tuple(parse(p['shown_cards']) for p in contenders)
        index = next(i for i, p in enumerate(contenders) if p['player_id'] == player_id)
        residual = sum(shares(holdings, b)[index] - random_equity(hole, b, len(contenders)-1) for b in boards) / len(boards)
        result['matchup'] = [residual, 1.0, 1]
    samples = all_in_samples(hand, player_id)
    if samples:
        result['all_in'] = [sum(v*w for v, w in samples), sum(w for _, w in samples), 1]
    return result


def aggregate_luck(records):
    dimensions = {}
    for key, weight in WEIGHTS.items():
        total = sum(r[key][0] for r in records)
        exposure = sum(r[key][1] for r in records)
        samples = sum(r[key][2] for r in records)
        # Ten neutral pseudo-hands. All-in weighting uses bounded exposure;
        # one giant pot never overwhelms the historical score.
        value = max(0, min(100, 50 + 50 * total / (exposure + 10)))
        dimensions[key] = {'score': round(value, 1), 'samples': samples, 'weight': weight}
    overall = sum(dimensions[k]['score'] * w for k, w in WEIGHTS.items())
    return {'luck': round(overall, 1), 'luck_samples': dimensions['starting']['samples'],
            'luck_dimensions': dimensions, 'luck_version': VERSION, 'luck_visibility': 'private'}


def public_luck(records):
    # Keep the latest 20 hands private; publish only complete 20-hand batches.
    count = max(0, (len(records) - 20) // 20 * 20)
    if not count:
        return {'luck': None, 'luck_band': None, 'luck_samples': 0, 'luck_visibility': 'public', 'luck_version': VERSION}
    value = aggregate_luck(records[:count])['luck']
    low, high, label = next((lo, hi, name) for lo, hi, name in
        [(0, 29, '偏背'), (30, 44, '稍背'), (45, 54, '平常'), (55, 69, '较顺'), (70, 100, '很顺')]
        if value < hi + 1)
    return {'luck': None, 'luck_band': {'min': low, 'max': high, 'label': label},
            'luck_samples': count, 'luck_visibility': 'public', 'luck_version': VERSION}
