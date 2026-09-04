import test from 'node:test';
import assert from 'node:assert/strict';
import { preflopChenScore } from '../equityCalculator.js';

test('preflopChenScore gives highest score to Pocket Aces', () => {
  const aa = preflopChenScore({ rank: 14, suit: 's' }, { rank: 14, suit: 'h' });
  assert.ok(aa >= 80, `Expected AA score >= 80, got ${aa}`);
});

test('preflopChenScore awards wheel straight bonus for A-5 suited vs unsuited', () => {
  const a5s = preflopChenScore({ rank: 14, suit: 's' }, { rank: 5, suit: 's' });
  const a5o = preflopChenScore({ rank: 14, suit: 's' }, { rank: 5, suit: 'h' });
  assert.ok(a5s > a5o, 'A5s should score higher than A5o');
  // Both should be positive and reasonably scored
  assert.ok(a5s >= 40);
});

test('preflopChenScore scores trash hands low', () => {
  const trash = preflopChenScore({ rank: 7, suit: 's' }, { rank: 2, suit: 'h' });
  assert.ok(trash <= 15, `Expected 72o score <= 15, got ${trash}`);
});
