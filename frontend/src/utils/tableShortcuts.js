/**
 * Table Hotkeys & Shortcut Helpers for PC Poker Table Operations
 *
 * Maps keyboard events to game actions:
 * - Numbers 1 - 8: First two rows of quick bet presets (8 pot presets ending with All-in)
 * - F1 - F4: Third row of quick bet presets (4 BB multiplier presets: 2.5BB, 3BB, 4BB, 5BB)
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
  { label: '1/3 底池', ratio: 1 / 3, shortcut: '1', type: 'pot' },
  { label: '1/2 底池', ratio: 1 / 2, shortcut: '2', type: 'pot' },
  { label: '2/3 底池', ratio: 2 / 3, shortcut: '3', type: 'pot' },
  { label: '底池', ratio: 1.0, shortcut: '4', type: 'pot' },
  { label: '1.5底池', ratio: 1.5, shortcut: '5', type: 'pot' },
  { label: '2底池', ratio: 2.0, shortcut: '6', type: 'pot' },
  { label: '3底池', ratio: 3.0, shortcut: '7', type: 'pot' },
  { label: '全下', isMax: true, shortcut: '8', type: 'allin' },
];

export const BB_PRESETS = [
  { label: '2.5 BB', mult: 2.5, shortcut: 'F1', type: 'bb' },
  { label: '3 BB', mult: 3, shortcut: 'F2', type: 'bb' },
  { label: '4 BB', mult: 4, shortcut: 'F3', type: 'bb' },
  { label: '5 BB', mult: 5, shortcut: 'F4', type: 'bb' },
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
 * Parses quick bet shortcuts:
 * - Numbers 1-8 (Digit1-8, Numpad1-8) map to presets 0..7 (first 2 rows)
 * - Function keys F1-F4 map to presets 8..11 (last row)
 * Returns { index: number (0..11), shortcut: string, type: 'pot' | 'allin' | 'bb' } or null.
 */
export function parsePresetShortcut(event) {
  if (!event) return null;
  const code = event.code;
  const key = event.key;

  // 1. Numbers 1-8 for rows 1 & 2
  const digitMatch =
    (typeof code === 'string' && code.match(/^(?:Digit|Numpad)([1-8])$/)) ||
    (typeof key === 'string' && key.match(/^([1-8])$/));

  if (digitMatch) {
    const num = parseInt(digitMatch[1] || digitMatch[0], 10);
    return {
      index: num - 1, // 0..7
      shortcut: String(num),
      type: num === 8 ? 'allin' : 'pot',
    };
  }

  // 2. Function keys F1-F4 for row 3
  const fMatch =
    (typeof code === 'string' && code.match(/^F([1-4])$/i)) ||
    (typeof key === 'string' && key.match(/^F([1-4])$/i));

  if (fMatch) {
    const fNum = parseInt(fMatch[1], 10);
    return {
      index: 7 + fNum, // 8..11
      shortcut: `F${fNum}`,
      type: 'bb',
    };
  }

  return null;
}

/**
 * Get preset definition by shortcut string (e.g. '1'..'8', 'F1'..'F4').
 */
export function getPresetByShortcut(shortcut) {
  if (!shortcut) return null;
  const norm = String(shortcut).toUpperCase();
  return ALL_QUICK_PRESETS.find((p) => p.shortcut.toUpperCase() === norm) || null;
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
 * Categorize a KeyboardEvent into an action identifier for turn/pre-action.
 */
export function resolveTableHotkey(event) {
  if (!event || isIgnoredInputTarget(event)) return null;

  const preset = parsePresetShortcut(event);
  if (preset !== null) {
    return { type: 'PRESET', index: preset.index, shortcut: preset.shortcut };
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
  if (code === 'KeyB' || code === 'KeyV') return { type: 'REVEAL_BOARD' };

  return null;
}

export const HAND_END_HOTKEYS = {
  READY: { key: 'Space', label: '准备' },
  START_NEXT: { key: 'Enter', label: '开始下一局' },
  CLOSE: { key: 'Esc', label: '关闭' },
  REOPEN_MODAL: { key: 'O', label: '查看本局结算' },
  CARD_1: { key: '1', altKey: 'Z', label: '亮左牌' },
  CARD_2: { key: '2', altKey: 'X', label: '亮右牌' },
  SHOW_ALL: { key: 'A', altKey: 'S', label: '全部亮出' },
  HIDE_ALL: { key: 'H', altKey: 'M', label: '不亮牌' },
  REVEAL_BOARD: { key: 'B', altKey: 'V', label: '查看' },
};

/**
 * Resolves keyboard events in the hand-end / showdown phase:
 * - Space: Toggle ready / rebuy
 * - Enter: Host starts next hand
 * - Escape: Close modal / return to table
 * - KeyO: Reopen hand result modal (when dismissed)
 * - Digit1 / Numpad1 / KeyZ: Toggle card 1
 * - Digit2 / Numpad2 / KeyX: Toggle card 2
 * - KeyA / KeyS: Show all cards
 * - KeyH / KeyM: Hide all cards (Muck)
 * - KeyB / KeyV / KeyC: Reveal unrevealed board cards
 */
export function resolveHandEndHotkey(event) {
  if (!event || isIgnoredInputTarget(event)) return null;

  const code = event.code;
  const key = typeof event.key === 'string' ? event.key.toLowerCase() : '';

  if (code === 'Space') return { type: 'READY' };
  if (code === 'Enter' || code === 'NumpadEnter') return { type: 'START_NEXT' };
  if (code === 'Escape') return { type: 'CLOSE' };
  if (code === 'KeyO' || key === 'o') return { type: 'REOPEN_MODAL' };

  // Reveal unrevealed board cards: B, V, C
  if (
    code === 'KeyB' ||
    code === 'KeyV' ||
    code === 'KeyC' ||
    key === 'b' ||
    key === 'v' ||
    key === 'c'
  ) {
    return { type: 'REVEAL_BOARD' };
  }

  // Toggle Card 1: 1 or Z
  if (code === 'Digit1' || code === 'Numpad1' || code === 'KeyZ' || key === '1' || key === 'z') {
    return { type: 'TOGGLE_CARD', cardIndex: 0 };
  }

  // Toggle Card 2: 2 or X
  if (code === 'Digit2' || code === 'Numpad2' || code === 'KeyX' || key === '2' || key === 'x') {
    return { type: 'TOGGLE_CARD', cardIndex: 1 };
  }

  // Show all cards: A or S
  if (code === 'KeyA' || code === 'KeyS' || key === 'a' || key === 's') {
    return { type: 'SHOW_ALL' };
  }

  // Hide all cards / Muck: H or M
  if (code === 'KeyH' || code === 'KeyM' || key === 'h' || key === 'm') {
    return { type: 'HIDE_ALL' };
  }

  return null;
}

