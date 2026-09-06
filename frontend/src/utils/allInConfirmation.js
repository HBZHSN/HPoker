/**
 * All-In confirmation logic utilities.
 * Mobile requires secondary confirmation for All-in actions to prevent misclicks.
 * PC does not require secondary confirmation.
 */

/**
 * Check if a bet preset represents an All-In action.
 *
 * @param {Object} params
 * @param {boolean} [params.isMax=false] - Whether the preset is explicitly marked as max (e.g. '全下')
 * @param {number} [params.amount=0] - The computed amount for the preset
 * @param {number} [params.maxVal=0] - The maximum valid bet/raise amount
 * @param {number} [params.sizingMax=0] - The slider maximum sizing amount
 * @returns {boolean}
 */
export function isPresetAllIn({ isMax = false, amount = 0, maxVal = 0, sizingMax = 0 } = {}) {
  if (isMax) return true;
  if (maxVal > 0 && amount >= maxVal) return true;
  if (sizingMax > 0 && amount >= sizingMax) return true;
  return false;
}

/**
 * Determines whether an All-in action requires secondary confirmation.
 * Mobile requires secondary confirmation; PC does not.
 *
 * @param {Object} params
 * @param {boolean} [params.isMobile=false] - Whether the action is on mobile
 * @param {boolean} [params.isAllInAction=false] - Whether the action is an All-in attempt
 * @param {boolean} [params.canAllIn=false] - Whether the player can legally All-in
 * @returns {boolean}
 */
export function shouldRequireAllInConfirmation({
  isMobile = false,
  isAllInAction = false,
  canAllIn = false,
} = {}) {
  if (!isMobile) return false;
  return Boolean(isAllInAction && canAllIn);
}

/**
 * Resolves the display/submission amount for an All-In action.
 *
 * @param {Object} params
 * @param {Object} [params.legalActions] - The table's legal actions object
 * @param {number} [params.maxVal=0] - The player's maximum bet/raise
 * @param {number} [params.currentAmount=0] - The currently selected bet amount
 * @param {number} [params.presetAmount=0] - The preset target amount
 * @returns {number}
 */
export function resolveAllInAmount({
  legalActions = null,
  maxVal = 0,
  currentAmount = 0,
  presetAmount = 0,
} = {}) {
  return (
    Number(legalActions?.all_in_amount) ||
    Number(maxVal) ||
    Number(presetAmount) ||
    Number(currentAmount) ||
    0
  );
}
