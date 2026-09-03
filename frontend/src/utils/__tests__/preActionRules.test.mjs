import test from 'node:test';
import assert from 'node:assert/strict';
import {
  PRE_ACTIONS,
  isEligibleForPreAction,
  getEffectiveHighestBet,
  calculatePreActionBounds,
  shouldCancelPreAction,
  determineAutoAction,
} from '../preActionRules.js';

test('isEligibleForPreAction: correctly checks eligibility', () => {
  const baseSeat = {
    player_id: 'u1',
    has_cards: true,
    is_folded: false,
    is_all_in: false,
    is_sitting_out: false,
    chips: 1000,
  };

  // Eligible when not my turn and in active street
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: false,
      selfSeat: baseSeat,
      street: 'FLOP',
    }),
    true
  );

  // Ineligible if it is my turn
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: true,
      selfSeat: baseSeat,
      street: 'FLOP',
    }),
    false
  );

  // Ineligible if folded
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: false,
      selfSeat: { ...baseSeat, is_folded: true },
      street: 'FLOP',
    }),
    false
  );

  // Ineligible if all-in
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: false,
      selfSeat: { ...baseSeat, is_all_in: true },
      street: 'FLOP',
    }),
    false
  );

  // Ineligible if idle or hand end
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: false,
      selfSeat: baseSeat,
      street: 'IDLE',
    }),
    false
  );
  assert.equal(
    isEligibleForPreAction({
      disabled: false,
      isMyTurn: false,
      selfSeat: baseSeat,
      street: 'HAND_END',
    }),
    false
  );
});

test('calculatePreActionBounds: unraised street', () => {
  const bounds = calculatePreActionBounds({
    effectiveHighestBet: 0,
    selfChips: 500,
    selfRoundBet: 0,
    bigBlind: 20,
  });
  assert.deepEqual(bounds, { minVal: 20, maxVal: 500 });
});

test('calculatePreActionBounds: facing bet with 2x min raise rule', () => {
  const bounds = calculatePreActionBounds({
    effectiveHighestBet: 50,
    selfChips: 400,
    selfRoundBet: 10,
    bigBlind: 20,
  });
  // min raise to: 50 * 2 = 100, max raise to: 10 + 400 = 410
  assert.deepEqual(bounds, { minVal: 100, maxVal: 410 });
});

test('calculatePreActionBounds: short stack cap', () => {
  const bounds = calculatePreActionBounds({
    effectiveHighestBet: 100,
    selfChips: 80,
    selfRoundBet: 0,
    bigBlind: 20,
  });
  // min raise to: min(200, 80) = 80
  assert.deepEqual(bounds, { minVal: 80, maxVal: 80 });
});

test('shouldCancelPreAction: street change cancels all pre-actions', () => {
  const preData = { street: 'FLOP', highestBet: 20, targetAmount: 60 };
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_CALL,
      preActionData: preData,
      currentStreet: 'TURN',
      effectiveHighestBet: 20,
    }),
    true
  );
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_FOLD,
      preActionData: preData,
      currentStreet: 'TURN',
      effectiveHighestBet: 20,
    }),
    true
  );
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.RAISE,
      preActionData: preData,
      currentStreet: 'TURN',
      effectiveHighestBet: 20,
    }),
    true
  );
});

test('shouldCancelPreAction: opponent raises higher', () => {
  const preData = { street: 'FLOP', highestBet: 20, targetAmount: 60 };

  // CHECK_CALL cancels when someone raises higher
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_CALL,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 60,
    }),
    true
  );

  // RAISE cancels when someone raises higher
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.RAISE,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 60,
    }),
    true
  );

  // CHECK_FOLD does NOT cancel on raise (folds when turn comes)
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_FOLD,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 60,
    }),
    false
  );
});

test('shouldCancelPreAction: unraised action keeps pre-actions active', () => {
  const preData = { street: 'FLOP', highestBet: 20, targetAmount: 60 };

  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_CALL,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 20,
    }),
    false
  );
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.RAISE,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 20,
    }),
    false
  );
  assert.equal(
    shouldCancelPreAction({
      preAction: PRE_ACTIONS.CHECK_FOLD,
      preActionData: preData,
      currentStreet: 'FLOP',
      effectiveHighestBet: 20,
    }),
    false
  );
});

test('determineAutoAction: CHECK_FOLD checks if unraised, folds if raised', () => {
  const preData = { street: 'FLOP', highestBet: 0 };

  // Case 1: unraised -> can_check
  const unraisedResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_FOLD,
    preActionData: preData,
    legalActions: { can_check: true, can_fold: true },
    effectiveHighestBet: 0,
    selfChips: 500,
  });
  assert.deepEqual(unraisedResult, { action: 'CHECK', amount: 0 });

  // Case 2: raised -> can_fold (cannot check)
  const raisedResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_FOLD,
    preActionData: preData,
    legalActions: { can_check: false, can_fold: true, can_call: true, call_amount: 50 },
    effectiveHighestBet: 50,
    selfChips: 500,
  });
  assert.deepEqual(raisedResult, { action: 'FOLD', amount: 0 });
});

test('determineAutoAction: CHECK_CALL checks if unraised, calls if unraised-further, aborts if re-raised', () => {
  // Scenario A: Selected when unraised (highestBet = 0)
  const preData0 = { street: 'FLOP', highestBet: 0 };

  // Unraised -> checks
  const checkResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_CALL,
    preActionData: preData0,
    legalActions: { can_check: true, can_fold: true },
    effectiveHighestBet: 0,
    selfChips: 500,
  });
  assert.deepEqual(checkResult, { action: 'CHECK', amount: 0 });

  // Raised before my turn -> aborts (returns null)
  const abortResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_CALL,
    preActionData: preData0,
    legalActions: { can_check: false, can_fold: true, can_call: true, call_amount: 30 },
    effectiveHighestBet: 30,
    selfChips: 500,
  });
  assert.equal(abortResult, null);

  // Scenario B: Selected facing a raise (highestBet = 40)
  const preData40 = { street: 'FLOP', highestBet: 40 };

  // No one re-raised -> calls 40
  const callResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_CALL,
    preActionData: preData40,
    legalActions: { can_check: false, can_fold: true, can_call: true, call_amount: 40 },
    effectiveHighestBet: 40,
    selfChips: 500,
  });
  assert.deepEqual(callResult, { action: 'CALL', amount: 40 });

  // Someone re-raised to 100 -> aborts
  const reRaisedResult = determineAutoAction({
    preAction: PRE_ACTIONS.CHECK_CALL,
    preActionData: preData40,
    legalActions: { can_check: false, can_fold: true, can_call: true, call_amount: 100 },
    effectiveHighestBet: 100,
    selfChips: 500,
  });
  assert.equal(reRaisedResult, null);
});

test('determineAutoAction: RAISE raises when unraised, aborts when opponent raised', () => {
  const preData = { street: 'FLOP', highestBet: 20, targetAmount: 80 };

  // No one raised higher -> raises to 80
  const raiseResult = determineAutoAction({
    preAction: PRE_ACTIONS.RAISE,
    preActionData: preData,
    legalActions: {
      can_raise: true,
      min_raise_to: 40,
      max_raise_to: 1000,
    },
    effectiveHighestBet: 20,
    selfChips: 1000,
  });
  assert.deepEqual(raiseResult, { action: 'RAISE', amount: 80 });

  // Someone re-raised to 120 -> aborts
  const abortRaiseResult = determineAutoAction({
    preAction: PRE_ACTIONS.RAISE,
    preActionData: preData,
    legalActions: {
      can_raise: true,
      min_raise_to: 240,
      max_raise_to: 1000,
    },
    effectiveHighestBet: 120,
    selfChips: 1000,
  });
  assert.equal(abortRaiseResult, null);
});
