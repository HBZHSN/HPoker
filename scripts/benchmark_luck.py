"""Cold-cache CPU benchmark; optionally compare a git revision without checking it out.

Run: .venv/bin/python -m scripts.benchmark_luck --baseline-ref <revision>
Uses synthetic cards only; never imports database service singletons.
"""
import argparse
from pathlib import Path
from statistics import median
import subprocess
from time import perf_counter
from types import ModuleType

from backend.app.engine.card import Card
from backend.app.services import comprehensive_luck as current


def cases(module):
    cards = lambda text: tuple(Card.from_str(c) for c in text.split())
    hero = cards('As Ah')
    holdings = (hero, cards('Ks Kh'), cards('Qs Qh'))
    for board in ('', '2s 7h 9d', '2s 7h 9d Jc', '2s 7h 9d Jc Qc'):
        for opponents in (1, 2, 8):
            yield f'random/{len(board.split())}/{opponents}', module.random_equity, (hero, cards(board), opponents)
        yield f'fixed/{len(board.split())}/3', module.fixed_equity, (holdings, cards(board))


def measure(module):
    timings, results = {}, {}
    for name, function, args in cases(module):
        samples = []
        for _ in range(5):
            function.cache_clear()
            start = perf_counter()
            results[name] = function(*args)
            samples.append(perf_counter() - start)
        timings[name] = median(samples)
    return timings, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref')
    args = parser.parse_args()
    before = None
    if args.baseline_ref:
        root = Path(__file__).resolve().parents[1]
        path = 'backend/app/services/comprehensive_luck.py'
        source = subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{path}'], cwd=root, text=True)
        baseline = ModuleType('luck_baseline')
        baseline.__file__ = str(root / path)
        exec(compile(source, str(root / path), 'exec'), baseline.__dict__)
        before, expected = measure(baseline)
    after, actual = measure(current)
    if before is not None:
        assert actual == expected, 'Simulation results changed'
    for name, elapsed in after.items():
        comparison = f' (before {before[name] * 1000:.2f} ms, {before[name] / elapsed:.2f}x)' if before else ''
        print(f'{name}: {elapsed * 1000:.2f} ms{comparison}')
    if before:
        print(f'Total: {sum(before.values()):.3f}s -> {sum(after.values()):.3f}s '
              f'({sum(before.values()) / sum(after.values()):.2f}x); all results identical')


if __name__ == '__main__':
    main()
