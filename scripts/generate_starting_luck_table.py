"""Run with project .venv Python; offline reproducible 169-class equity calibration."""
import json
from pathlib import Path
from backend.app.engine.card import Card
from backend.app.services.comprehensive_luck import random_equity, starting_key

entries = {}
for high in '23456789TJQKA':
    for low in '23456789TJQKA':
        a, b = Card.from_str(high+'s'), Card.from_str(low+'h')
        if a.rank < b.rank:
            continue
        for suited in ([False] if high == low else [False, True]):
            hero = (a, Card.from_str(low + ('s' if suited else 'h')))
            key = starting_key(hero)
            entries[key] = {'equity': random_equity(hero, iterations=8192),
                            'combinations': 6 if high == low else 4 if suited else 12}
    print(f'Calibrated through {high}', flush=True)
for item in entries.values():
    below = sum(e['combinations'] for e in entries.values() if e['equity'] < item['equity'])
    tied = sum(e['combinations'] for e in entries.values() if e['equity'] == item['equity'])
    item['percentile'] = (below + tied / 2) / 1326
Path('backend/app/services/starting_luck_table.json').write_text(json.dumps({
    'version': 1, 'iterations_per_class': 8192, 'method': 'deterministic heads-up random-opponent Monte Carlo; combo-weighted midrank',
    'hands': entries}, indent=2) + '\n')
