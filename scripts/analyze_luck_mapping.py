"""Reproducible score-mapping diagnostic, not a simulation of player strategy.

Only starting-hand luck is sampled: uniform random deals from the calibrated
1326-combination distribution. Other dimensions have no observations.
Run from repo root with PYTHONPATH=. and the project .venv Python.
"""
import json
import random
from backend.app.services.comprehensive_luck import WEIGHTS, aggregate_luck, starting_table

rng = random.Random(103)
table = list(starting_table().values())
values = [2 * item['percentile'] - 1 for item in table]
weights = [item['combinations'] for item in table]

def summary(scores):
    scores = sorted(scores)
    return {'mean': round(sum(scores)/len(scores), 2),
            'p10': round(scores[len(scores)//10], 1),
            'p90': round(scores[9*len(scores)//10], 1),
            'within_40_60_percent': round(100*sum(40 <= s <= 60 for s in scores)/len(scores), 1)}

result = {'scenario': 'uniform random starting hands; no other dimension samples',
          'sessions_per_size': 1000, 'seed': 103, 'results': []}
for n in (20, 100, 500):
    old, new = [], []
    for _ in range(1000):
        draws = rng.choices(values, weights=weights, k=n)
        old.append(50 + .35 * 50 * sum(draws)/(n+10))
        records = [{k:[value,1,1] if k == 'starting' else [0,0,0] for k in WEIGHTS} for value in draws]
        new.append(aggregate_luck(records)['luck'])
    result['results'].append({'hands': n, 'old': summary(old), 'new': summary(new)})
print(json.dumps(result, ensure_ascii=False, indent=2))
