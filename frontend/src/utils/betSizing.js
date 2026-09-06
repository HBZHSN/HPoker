/**
 * Non-linear slider helpers for bet sizing.
 *
 * A quadratic curve gives players finer control near the minimum bet while
 * making each movement cover a larger chip span near the all-in end.
 */

export const BET_SLIDER_STEPS = 1000;
export const BET_SLIDER_CURVE_POWER = 2;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const normalizeBounds = (minAmount, maxAmount) => {
  const min = Number(minAmount);
  const max = Number(maxAmount);
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    return null;
  }
  return {
    min: Math.min(min, max),
    max: Math.max(min, max),
  };
};

export function nonlinearProgressToAmount(
  progress,
  minAmount,
  maxAmount,
  power = BET_SLIDER_CURVE_POWER,
  steps = BET_SLIDER_STEPS,
) {
  const bounds = normalizeBounds(minAmount, maxAmount);
  const curvePower = Number(power);
  const sliderSteps = Number(steps);
  if (!bounds || !Number.isFinite(curvePower) || curvePower <= 0 || !Number.isFinite(sliderSteps) || sliderSteps <= 0) {
    return Number(minAmount) || 0;
  }
  if (bounds.min === bounds.max) return bounds.min;

  const position = clamp(Number(progress) || 0, 0, sliderSteps) / sliderSteps;
  return bounds.min + ((bounds.max - bounds.min) * (position ** curvePower));
}

export function amountToNonlinearProgress(
  amount,
  minAmount,
  maxAmount,
  power = BET_SLIDER_CURVE_POWER,
  steps = BET_SLIDER_STEPS,
) {
  const bounds = normalizeBounds(minAmount, maxAmount);
  const curvePower = Number(power);
  const sliderSteps = Number(steps);
  if (!bounds || !Number.isFinite(curvePower) || curvePower <= 0 || !Number.isFinite(sliderSteps) || sliderSteps <= 0) {
    return 0;
  }
  if (bounds.min === bounds.max) return 0;

  const ratio = clamp((Number(amount) - bounds.min) / (bounds.max - bounds.min), 0, 1);
  return Math.round((ratio ** (1 / curvePower)) * sliderSteps);
}

/**
 * Calculate the default 1/2 pot bet/raise amount for slider initialization.
 */
export function calculateDefaultSliderAmount({
  totalPot = 0,
  callCost = 0,
  isRaise = false,
  selfRoundBet = 0,
  blindUnit = 1,
  minVal = 0,
  maxVal = 0,
}) {
  const unit = Math.max(1, Number(blindUnit) || 1);
  if (isRaise) {
    const effectivePot = Number(totalPot || 0) + Number(callCost || 0);
    const raiseAdd = Math.round((effectivePot * 0.5) / unit) * unit;
    const target = Number(selfRoundBet || 0) + Number(callCost || 0) + raiseAdd;
    const clamped = Math.max(Number(minVal || 0), target);
    return maxVal > 0 ? Math.min(maxVal, clamped) : clamped;
  }
  const target = Math.round((Number(totalPot || 0) * 0.5) / unit) * unit;
  const clamped = Math.max(Number(minVal || 0), target);
  return maxVal > 0 ? Math.min(maxVal, clamped) : clamped;
}

