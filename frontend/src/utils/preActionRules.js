/**
 * Poker pre-action helper logic and rule evaluation.
 */

export const PRE_ACTIONS = {
  CHECK_FOLD: 'CHECK_FOLD',
  CHECK_CALL: 'CHECK_CALL',
  RAISE: 'RAISE',
};

/**
 * Determines whether a seated player is eligible to select pre-actions.
 */
export function isEligibleForPreAction({
  disabled = false,
  isMyTurn = false,
  selfSeat = null,
  street = 'IDLE',
}) {
  if (disabled || isMyTurn || !selfSeat) return false;
  const hasCards = Boolean(selfSeat.has_cards || (selfSeat.hole_cards && selfSeat.hole_cards.length > 0));
  if (!hasCards) return false;
  if (selfSeat.is_folded || selfSeat.is_all_in || selfSeat.is_sitting_out) return false;
  if (!['PREFLOP', 'FLOP', 'TURN', 'RIVER'].includes(street)) return false;
  return true;
}

/**
 * Calculates effective highest bet on the table from currentRoundHighestBet and seats.
 */
export function getEffectiveHighestBet(currentRoundHighestBet = 0, seats = []) {
  const seatBets = (seats || []).map((s) => Number(s?.current_round_bet) || 0);
  return Math.max(Number(currentRoundHighestBet) || 0, ...seatBets, 0);
}

/**
 * Calculates pre-action betting/raising boundaries when not the player's turn.
 */
export function calculatePreActionBounds({
  effectiveHighestBet = 0,
  selfChips = 0,
  selfRoundBet = 0,
  bigBlind = 20,
}) {
  const chips = Math.max(0, Number(selfChips) || 0);
  const roundBet = Math.max(0, Number(selfRoundBet) || 0);
  const highestBet = Math.max(0, Number(effectiveHighestBet) || 0);
  const bb = Math.max(1, Number(bigBlind) || 1);

  if (chips === 0) {
    return { minVal: 0, maxVal: 0 };
  }

  if (highestBet === 0) {
    // No bet in round yet: min bet is min(bigBlind, chips), max is chips
    return {
      minVal: Math.min(bb, chips),
      maxVal: chips,
    };
  }

  // There is an existing bet: min raise is 2x highest bet (or all-in), max is roundBet + chips
  const totalAvailable = roundBet + chips;
  const minRaiseTo = Math.min(highestBet * 2, totalAvailable);
  return {
    minVal: minRaiseTo,
    maxVal: totalAvailable,
  };
}

/**
 * Determines whether an active pre-action should be cancelled based on incoming table updates.
 *
 * Rules:
 * 1. Street changes: always cancel (new betting round).
 * 2. If someone raises higher than the highest bet when pre-action was selected:
 *    - CHECK_CALL: CANCEL (let user decide manually).
 *    - RAISE: CANCEL (let user decide manually).
 *    - CHECK_FOLD: DO NOT CANCEL (user will fold if raised, check if unraised).
 */
export function shouldCancelPreAction({
  preAction,
  preActionData,
  currentStreet,
  effectiveHighestBet,
}) {
  if (!preAction || !preActionData) return false;

  // Street transition
  if (currentStreet !== preActionData.street) {
    return true;
  }

  // Someone raised higher than the baseline at selection time
  if (effectiveHighestBet > (preActionData.highestBet || 0)) {
    if (preAction === PRE_ACTIONS.CHECK_CALL || preAction === PRE_ACTIONS.RAISE) {
      return true;
    }
    // CHECK_FOLD persists on raise
  }

  return false;
}

/**
 * Resolves the concrete action to execute when it becomes the player's turn.
 * Returns { action, amount } or null if condition failed / no action.
 */
export function determineAutoAction({
  preAction,
  preActionData,
  legalActions,
  effectiveHighestBet = 0,
  selfChips = 0,
}) {
  if (!preAction || !legalActions) return null;

  if (preAction === PRE_ACTIONS.CHECK_FOLD) {
    // If no one raised, check; if any raise, fold
    if (legalActions.can_check) {
      return { action: 'CHECK', amount: 0 };
    }
    if (legalActions.can_fold) {
      return { action: 'FOLD', amount: 0 };
    }
    return null;
  }

  if (preAction === PRE_ACTIONS.CHECK_CALL) {
    // If someone raised beyond what was expected, do not execute (let user decide)
    if (preActionData && effectiveHighestBet > (preActionData.highestBet || 0)) {
      return null;
    }
    if (legalActions.can_check) {
      return { action: 'CHECK', amount: 0 };
    }
    if (legalActions.can_call) {
      return { action: 'CALL', amount: legalActions.call_amount || 0 };
    }
    if (legalActions.can_all_in && selfChips <= (legalActions.call_amount || 0)) {
      return { action: 'ALL_IN', amount: legalActions.all_in_amount || selfChips };
    }
    return null;
  }

  if (preAction === PRE_ACTIONS.RAISE) {
    // If someone raised beyond what was expected, do not execute (let user decide)
    if (preActionData && effectiveHighestBet > (preActionData.highestBet || 0)) {
      return null;
    }

    const target = preActionData?.targetAmount || 0;

    if (legalActions.can_bet) {
      const minBet = legalActions.min_bet || 0;
      const maxBet = legalActions.max_bet || 0;
      const clamped = Math.max(minBet, Math.min(maxBet, target));
      if (clamped >= maxBet && legalActions.can_all_in) {
        return { action: 'ALL_IN', amount: legalActions.all_in_amount || clamped };
      }
      return { action: 'BET', amount: clamped };
    }

    if (legalActions.can_raise) {
      const minRaise = legalActions.min_raise_to || 0;
      const maxRaise = legalActions.max_raise_to || 0;
      // Target must satisfy min_raise_to
      if (target >= minRaise) {
        const clamped = Math.min(maxRaise, target);
        if (clamped >= maxRaise && legalActions.can_all_in) {
          return { action: 'ALL_IN', amount: legalActions.all_in_amount || clamped };
        }
        return { action: 'RAISE', amount: clamped };
      }
      // Sizing is below legal min raise, cancel and let user decide
      return null;
    }

    return null;
  }

  return null;
}
