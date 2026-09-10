export const DEFAULT_ROOM_CONFIG = Object.freeze({
  buyin_chips: 1000,
  cash_value: 100,
  small_blind: 10,
  action_timeout: 15,
  max_seats: 6,
  assistant_win_ratio: 0.7,
});

export const ROOM_DEFAULT_LIMITS = Object.freeze({
  buyin_chips: { min: 10 },
  cash_value: { min: 0 },
  small_blind: { min: 1 },
  action_timeout: { min: 5, max: 60 },
  max_seats: { min: 2, max: 9 },
  assistant_win_ratio: { min: 0.1, max: 1 },
});

function numberOrFallback(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function integerOrFallback(value, fallback, minimum, maximum) {
  const number = numberOrFallback(value, fallback);
  const integer = Math.round(number);
  const lowerBound = Math.max(minimum, integer);
  return maximum === undefined ? lowerBound : Math.min(maximum, lowerBound);
}

function boundedNumber(value, fallback, minimum, maximum) {
  const number = numberOrFallback(value, fallback);
  const lowerBound = Math.max(minimum, number);
  return maximum === undefined ? lowerBound : Math.min(maximum, lowerBound);
}

export function normalizeRoomDefaults(config = {}) {
  const source = config && typeof config === 'object' ? config : {};
  const buyinChips = integerOrFallback(
    source.buyin_chips,
    DEFAULT_ROOM_CONFIG.buyin_chips,
    ROOM_DEFAULT_LIMITS.buyin_chips.min,
  );
  const cashValue = boundedNumber(
    source.cash_value,
    DEFAULT_ROOM_CONFIG.cash_value,
    ROOM_DEFAULT_LIMITS.cash_value.min,
  );
  const smallBlind = integerOrFallback(
    source.small_blind,
    DEFAULT_ROOM_CONFIG.small_blind,
    ROOM_DEFAULT_LIMITS.small_blind.min,
  );
  const actionTimeout = integerOrFallback(
    source.action_timeout,
    DEFAULT_ROOM_CONFIG.action_timeout,
    ROOM_DEFAULT_LIMITS.action_timeout.min,
    ROOM_DEFAULT_LIMITS.action_timeout.max,
  );
  const maxSeats = integerOrFallback(
    source.max_seats,
    DEFAULT_ROOM_CONFIG.max_seats,
    ROOM_DEFAULT_LIMITS.max_seats.min,
    ROOM_DEFAULT_LIMITS.max_seats.max,
  );
  const assistantWinRatio = boundedNumber(
    source.assistant_win_ratio,
    DEFAULT_ROOM_CONFIG.assistant_win_ratio,
    ROOM_DEFAULT_LIMITS.assistant_win_ratio.min,
    ROOM_DEFAULT_LIMITS.assistant_win_ratio.max,
  );

  return {
    buyin_chips: buyinChips,
    cash_value: Math.round(cashValue * 100) / 100,
    small_blind: smallBlind,
    big_blind: smallBlind * 2,
    action_timeout: actionTimeout,
    max_seats: maxSeats,
    assistant_win_ratio: Math.round(assistantWinRatio * 1000) / 1000,
    assistant_win_pct: Math.round(assistantWinRatio * 100),
  };
}
