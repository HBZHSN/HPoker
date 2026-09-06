/**
 * Table Hotkeys & Shortcut Helpers for PC Poker Table Operations
 *
 * Maps keyboard events to game actions:
 * - F1 - F12: 1-to-1 mapping to 12 quick bet presets (8 pot presets + 4 BB presets)
 * - Space: Check / Call during turn, Check/Call during pre-action, Ready during game-ended / idle
 * - F: Fold during turn, Check/Fold during pre-action
 * - R: Bet / Raise during turn, Raise during pre-action
 * - A: All-in during turn / pre-action
 * - T: Time card (+30s)
 * - Enter: Submit bet / raise or start next hand (host)
 * - ArrowUp / ArrowRight: +1BB
 * - ArrowDown / ArrowLeft: -1BB
 */

export const POT_PRESETS = [
  { label: '1/3 底池', ratio: 1 / 3, shortcut: 'F1', type: 'pot' },
  { label: '1/2 底池', ratio: 1 / 2, shortcut: 'F2', type: 'pot' },
  { label: '2/3 底池', ratio: 2 / 3, shortcut: 'F3', type: 'pot' },
  { label: '底池', ratio: 1.0, shortcut: 'F4', type: 'pot' },
  { label: '1.5底池', ratio: 1.5, shortcut: 'F5', type: 'pot' },
  { label: '2底池', ratio: 2.0, shortcut: 'F6', type: 'pot' },
  { label: '3底池', ratio: 3.0, shortcut: 'F7', type: 'pot' },
  { label: '全下', isMax: true, shortcut: 'F8', type: 'allin' },
];

export const BB_PRESETS = [
  { label: '2.5 BB', mult: 2.5, shortcut: 'F9', type: 'bb' },
  { label: '3 BB', mult: 3, shortcut: 'F10', type: 'bb' },
  { label: '4 BB', mult: 4, shortcut: 'F11', type: 'bb' },
  { label: '5 BB', mult: 5, shortcut: 'F12', type: 'bb' },
];

export const ALL_QUICK_PRESETS = [...POT_PRESETS, ...BB_PRESETS];

/**
 * Check if the keydown event originated inside an input, textarea, or contentEditable element.
 */
export function isIgnoredInputTarget(event) {
  if (!event || !event.target) return false;
  const tagName = event.target.tagName?.toLowerCase();
  return tagName === 'input' || tagName === 'textarea' || Boolean(event.target.isContentEditable);
}

/**
 * Parses function keys F1 to F12 from a KeyboardEvent.
 * Returns the 1-based number (1..12) or null if not an F1..F12 key.
 */
export function parseFKey(event) {
  if (!event) return null;
  const code = event.code;
  const key = event.key;
  const match =
    (typeof code === 'string' && code.match(/^F([1-9]|1[0-2])$/)) ||
    (typeof key === 'string' && key.match(/^F([1-9]|1[0-2])$/));
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Get preset definition by shortcut string (e.g. 'F1'..'F12').
 */
export function getPresetByShortcut(shortcut) {
  if (!shortcut) return null;
  return ALL_QUICK_PRESETS.find((p) => p.shortcut === shortcut.toUpperCase()) || null;
}

/**
 * Calculate the exact chip amount for a given preset.
 */
export function calculatePresetAmount({
  preset,
  totalPot = 0,
  callCost = 0,
  isRaise = false,
  selfRoundBet = 0,
  blindUnit = 1,
  bigBlind = 20,
  minVal = 0,
  maxVal = 0,
}) {
  if (!preset) return 0;
  if (preset.isMax) return maxVal;

  const unit = Math.max(1, Number(blindUnit) || 1);

  if (preset.type === 'bb') {
    const raw = Math.round(((Number(preset.mult) || 0) * (Number(bigBlind) || 0)) / unit) * unit;
    return Math.max(0, maxVal > 0 ? Math.min(maxVal, raw) : raw);
  }

  if (isRaise) {
    const effectivePot = Number(totalPot || 0) + Number(callCost || 0);
    const raiseAdd = Math.round((effectivePot * (Number(preset.ratio) || 0)) / unit) * unit;
    const target = Number(selfRoundBet || 0) + Number(callCost || 0) + raiseAdd;
    const clamped = Math.max(Number(minVal || 0), target);
    return maxVal > 0 ? Math.min(maxVal, clamped) : clamped;
  }

  const target = Math.round((Number(totalPot || 0) * (Number(preset.ratio) || 0)) / unit) * unit;
  const clamped = Math.max(Number(minVal || 0), target);
  return maxVal > 0 ? Math.min(maxVal, clamped) : clamped;
}

/**
 * Categorize a KeyboardEvent into an action identifier.
 */
export function resolveTableHotkey(event) {
  if (!event || isIgnoredInputTarget(event)) return null;

  const fNum = parseFKey(event);
  if (fNum !== null) {
    return { type: 'F_KEY', fNum, presetIndex: fNum - 1, shortcut: `F${fNum}` };
  }

  const code = event.code;
  if (code === 'Space') return { type: 'SPACE' };
  if (code === 'KeyF') return { type: 'FOLD' };
  if (code === 'KeyR') return { type: 'RAISE' };
  if (code === 'KeyA') return { type: 'ALL_IN' };
  if (code === 'KeyT') return { type: 'TIME_CARD' };
  if (code === 'Enter' || code === 'NumpadEnter') return { type: 'ENTER' };
  if (code === 'Escape') return { type: 'ESCAPE' };
  if (code === 'ArrowUp' || code === 'ArrowRight') return { type: 'ADJUST_UP' };
  if (code === 'ArrowDown' || code === 'ArrowLeft') return { type: 'ADJUST_DOWN' };

  return null;
}
