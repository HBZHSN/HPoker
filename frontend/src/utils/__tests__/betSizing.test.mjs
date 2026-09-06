import test from 'node:test';
import assert from 'node:assert/strict';
import {
  amountToNonlinearProgress,
  nonlinearProgressToAmount,
  calculateDefaultSliderAmount,
} from '../betSizing.js';

test('nonlinear slider maps endpoints exactly', () => {
  assert.equal(nonlinearProgressToAmount(0, 20, 1000), 20);
  assert.equal(nonlinearProgressToAmount(1000, 20, 1000), 1000);
  assert.equal(amountToNonlinearProgress(20, 20, 1000), 0);
  assert.equal(amountToNonlinearProgress(1000, 20, 1000), 1000);
});

test('nonlinear slider creates progressively larger spans', () => {
  const values = [0, 250, 500, 750, 1000].map((progress) => (
    nonlinearProgressToAmount(progress, 20, 1000)
  ));
  const spans = values.slice(1).map((value, index) => value - values[index]);

  assert.ok(spans[1] > spans[0]);
  assert.ok(spans[2] > spans[1]);
  assert.ok(spans[3] > spans[2]);
});

test('nonlinear slider handles a collapsed or invalid range safely', () => {
  assert.equal(nonlinearProgressToAmount(500, 40, 40), 40);
  assert.equal(amountToNonlinearProgress(40, 40, 40), 0);
  assert.equal(nonlinearProgressToAmount(500, 'bad', 40), 0);
  assert.equal(amountToNonlinearProgress(40, 'bad', 40), 0);
});

test('amount conversion clamps out-of-range values', () => {
  assert.equal(amountToNonlinearProgress(-10, 20, 1000), 0);
  assert.equal(amountToNonlinearProgress(2000, 20, 1000), 1000);
  assert.equal(nonlinearProgressToAmount(-1, 20, 1000), 20);
  assert.equal(nonlinearProgressToAmount(2000, 20, 1000), 1000);
});

test('calculateDefaultSliderAmount defaults to 1/2 pot with proper clamping and raise math', () => {
  // 1. Unraised pot: pot = 100, minVal = 20, maxVal = 1000 -> 1/2 pot = 50
  assert.equal(
    calculateDefaultSliderAmount({ totalPot: 100, isRaise: false, blindUnit: 10, minVal: 20, maxVal: 1000 }),
    50
  );

  // 2. Small pot where 1/2 pot < minVal: pot = 30, minVal = 40 -> clamped to 40 (minVal)
  assert.equal(
    calculateDefaultSliderAmount({ totalPot: 30, isRaise: false, blindUnit: 10, minVal: 40, maxVal: 1000 }),
    40
  );

  // 3. Short stack where 1/2 pot > maxVal: pot = 500, maxVal = 150 -> clamped to 150 (maxVal)
  assert.equal(
    calculateDefaultSliderAmount({ totalPot: 500, isRaise: false, blindUnit: 10, minVal: 20, maxVal: 150 }),
    150
  );

  // 4. Raise situation: pot = 100, callCost = 40, effectivePot = 140, raiseAdd = 70, target = 0 + 40 + 70 = 110
  assert.equal(
    calculateDefaultSliderAmount({ totalPot: 100, callCost: 40, isRaise: true, selfRoundBet: 0, blindUnit: 10, minVal: 80, maxVal: 1000 }),
    110
  );
});

