import test from 'node:test';
import assert from 'node:assert/strict';
import {
  isPresetAllIn,
  shouldRequireAllInConfirmation,
  resolveAllInAmount,
} from '../allInConfirmation.js';

test('isPresetAllIn: correctly identifies all-in presets', () => {
  // 1. Explicit max preset ('全下')
  assert.equal(isPresetAllIn({ isMax: true }), true);
  assert.equal(isPresetAllIn({ isMax: true, amount: 500, maxVal: 1000 }), true);

  // 2. Preset amount exceeds or meets maxVal
  assert.equal(isPresetAllIn({ isMax: false, amount: 1000, maxVal: 1000 }), true);
  assert.equal(isPresetAllIn({ isMax: false, amount: 1200, maxVal: 1000 }), true);

  // 3. Preset amount exceeds sizingMax
  assert.equal(isPresetAllIn({ isMax: false, amount: 1000, maxVal: 0, sizingMax: 1000 }), true);

  // 4. Normal sub-all-in presets
  assert.equal(isPresetAllIn({ isMax: false, amount: 300, maxVal: 1000, sizingMax: 1000 }), false);
  assert.equal(isPresetAllIn({ isMax: false, amount: 0, maxVal: 1000 }), false);
  assert.equal(isPresetAllIn(), false);
});

test('shouldRequireAllInConfirmation: mobile requires confirmation, PC does NOT', () => {
  // Mobile scenarios: must confirm when going all-in
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: true,
      isAllInAction: true,
      canAllIn: true,
    }),
    true
  );

  // Mobile scenarios: normal bet/raise does not require confirmation
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: true,
      isAllInAction: false,
      canAllIn: true,
    }),
    false
  );

  // Mobile scenarios: cannot all-in legally
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: true,
      isAllInAction: true,
      canAllIn: false,
    }),
    false
  );

  // PC scenarios: PC NEVER requires secondary confirmation!
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: false,
      isAllInAction: true,
      canAllIn: true,
    }),
    false
  );
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: false,
      isAllInAction: true,
      canAllIn: false,
    }),
    false
  );
  assert.equal(
    shouldRequireAllInConfirmation({
      isMobile: false,
      isAllInAction: false,
      canAllIn: true,
    }),
    false
  );
});

test('resolveAllInAmount: resolves the accurate all-in chip amount', () => {
  assert.equal(
    resolveAllInAmount({
      legalActions: { all_in_amount: 1500 },
      maxVal: 1500,
      currentAmount: 800,
    }),
    1500
  );

  assert.equal(
    resolveAllInAmount({
      legalActions: null,
      maxVal: 1200,
      currentAmount: 600,
    }),
    1200
  );

  assert.equal(
    resolveAllInAmount({
      legalActions: null,
      maxVal: 0,
      presetAmount: 950,
      currentAmount: 500,
    }),
    950
  );

  assert.equal(
    resolveAllInAmount({
      legalActions: null,
      maxVal: 0,
      currentAmount: 400,
    }),
    400
  );
});
