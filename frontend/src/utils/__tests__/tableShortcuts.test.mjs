import test from 'node:test';
import assert from 'node:assert/strict';
import {
  POT_PRESETS,
  BB_PRESETS,
  ALL_QUICK_PRESETS,
  parseFKey,
  getPresetByShortcut,
  calculatePresetAmount,
  resolveTableHotkey,
  isIgnoredInputTarget,
} from '../tableShortcuts.js';

test('POT_PRESETS and BB_PRESETS define exactly 12 1-to-1 shortcuts F1-F12', () => {
  assert.equal(POT_PRESETS.length, 8);
  assert.equal(BB_PRESETS.length, 4);
  assert.equal(ALL_QUICK_PRESETS.length, 12);

  for (let i = 0; i < 12; i++) {
    const expectedKey = `F${i + 1}`;
    assert.equal(ALL_QUICK_PRESETS[i].shortcut, expectedKey);
    const retrieved = getPresetByShortcut(expectedKey);
    assert.ok(retrieved);
    assert.equal(retrieved.shortcut, expectedKey);
  }

  // F1 to F8 are pot presets ending in All-in
  assert.equal(ALL_QUICK_PRESETS[0].label, '1/3 底池');
  assert.equal(ALL_QUICK_PRESETS[1].label, '1/2 底池');
  assert.equal(ALL_QUICK_PRESETS[2].label, '2/3 底池');
  assert.equal(ALL_QUICK_PRESETS[3].label, '底池');
  assert.equal(ALL_QUICK_PRESETS[4].label, '1.5底池');
  assert.equal(ALL_QUICK_PRESETS[5].label, '2底池');
  assert.equal(ALL_QUICK_PRESETS[6].label, '3底池');
  assert.equal(ALL_QUICK_PRESETS[7].label, '全下');
  assert.equal(ALL_QUICK_PRESETS[7].isMax, true);

  // F9 to F12 are BB presets
  assert.equal(ALL_QUICK_PRESETS[8].label, '2.5 BB');
  assert.equal(ALL_QUICK_PRESETS[9].label, '3 BB');
  assert.equal(ALL_QUICK_PRESETS[10].label, '4 BB');
  assert.equal(ALL_QUICK_PRESETS[11].label, '5 BB');
});

test('parseFKey accurately identifies F1 through F12 from KeyboardEvent', () => {
  for (let i = 1; i <= 12; i++) {
    assert.equal(parseFKey({ code: `F${i}` }), i);
    assert.equal(parseFKey({ key: `F${i}` }), i);
  }

  assert.equal(parseFKey({ code: 'F13' }), null);
  assert.equal(parseFKey({ code: 'KeyF' }), null);
  assert.equal(parseFKey({ code: 'Digit1' }), null);
  assert.equal(parseFKey(null), null);
});

test('isIgnoredInputTarget returns true for text input fields and false for buttons/table', () => {
  assert.equal(isIgnoredInputTarget({ target: { tagName: 'INPUT' } }), true);
  assert.equal(isIgnoredInputTarget({ target: { tagName: 'TEXTAREA' } }), true);
  assert.equal(isIgnoredInputTarget({ target: { tagName: 'DIV', isContentEditable: true } }), true);
  assert.equal(isIgnoredInputTarget({ target: { tagName: 'BUTTON' } }), false);
  assert.equal(isIgnoredInputTarget({ target: { tagName: 'DIV' } }), false);
  assert.equal(isIgnoredInputTarget(null), false);
});

test('calculatePresetAmount computes amounts accurately for pot and BB presets', () => {
  // Pot bet calculation: 1/2 pot of 100 with blind unit 10
  const halfPotPreset = getPresetByShortcut('F2');
  const amountHalf = calculatePresetAmount({
    preset: halfPotPreset,
    totalPot: 100,
    blindUnit: 10,
    minVal: 20,
    maxVal: 1000,
  });
  assert.equal(amountHalf, 50);

  // All-in preset F8 returns maxVal
  const allInPreset = getPresetByShortcut('F8');
  const amountAllIn = calculatePresetAmount({
    preset: allInPreset,
    totalPot: 100,
    minVal: 20,
    maxVal: 850,
  });
  assert.equal(amountAllIn, 850);

  // 3 BB preset F10 with BB 20
  const threeBBPreset = getPresetByShortcut('F10');
  const amount3BB = calculatePresetAmount({
    preset: threeBBPreset,
    bigBlind: 20,
    blindUnit: 10,
    minVal: 20,
    maxVal: 1000,
  });
  assert.equal(amount3BB, 60);

  // Raise pot calculation: pot 100, callCost 20, raise 1.0 pot
  const fullPotPreset = getPresetByShortcut('F4');
  const amountRaisePot = calculatePresetAmount({
    preset: fullPotPreset,
    totalPot: 100,
    callCost: 20,
    isRaise: true,
    selfRoundBet: 10,
    blindUnit: 10,
    minVal: 40,
    maxVal: 1000,
  });
  // target = selfRoundBet (10) + callCost (20) + (100 + 20) * 1.0 (120) = 150
  assert.equal(amountRaisePot, 150);
});

test('resolveTableHotkey maps full set of poker table hotkeys', () => {
  // Function keys F1..F12
  for (let i = 1; i <= 12; i++) {
    const res = resolveTableHotkey({ code: `F${i}` });
    assert.deepEqual(res, { type: 'F_KEY', fNum: i, presetIndex: i - 1, shortcut: `F${i}` });
  }

  // Core game actions
  assert.deepEqual(resolveTableHotkey({ code: 'Space' }), { type: 'SPACE' });
  assert.deepEqual(resolveTableHotkey({ code: 'KeyF' }), { type: 'FOLD' });
  assert.deepEqual(resolveTableHotkey({ code: 'KeyR' }), { type: 'RAISE' });
  assert.deepEqual(resolveTableHotkey({ code: 'KeyA' }), { type: 'ALL_IN' });
  assert.deepEqual(resolveTableHotkey({ code: 'KeyT' }), { type: 'TIME_CARD' });
  assert.deepEqual(resolveTableHotkey({ code: 'Enter' }), { type: 'ENTER' });
  assert.deepEqual(resolveTableHotkey({ code: 'NumpadEnter' }), { type: 'ENTER' });
  assert.deepEqual(resolveTableHotkey({ code: 'Escape' }), { type: 'ESCAPE' });

  // Bet adjustments (+1BB / -1BB)
  assert.deepEqual(resolveTableHotkey({ code: 'ArrowUp' }), { type: 'ADJUST_UP' });
  assert.deepEqual(resolveTableHotkey({ code: 'ArrowRight' }), { type: 'ADJUST_UP' });
  assert.deepEqual(resolveTableHotkey({ code: 'ArrowDown' }), { type: 'ADJUST_DOWN' });
  assert.deepEqual(resolveTableHotkey({ code: 'ArrowLeft' }), { type: 'ADJUST_DOWN' });

  // Ignored in input fields
  assert.equal(resolveTableHotkey({ code: 'Space', target: { tagName: 'INPUT' } }), null);
  assert.equal(resolveTableHotkey({ code: 'KeyF', target: { tagName: 'TEXTAREA' } }), null);
  assert.equal(resolveTableHotkey({ code: 'F5', target: { tagName: 'INPUT' } }), null);
});

test('game-ended and idle area ready toggling semantics', () => {
  // Helper simulating table/modal Space behavior
  const handleSpaceInEndArea = ({ street, selfSeat, readyPlayerIds = [], isHost = false }) => {
    if (!['HAND_END', 'IDLE'].includes(street)) return null;
    if (!selfSeat) return null;
    if (selfSeat.chips === 0) return { action: 'REBUY' };
    const isReady = readyPlayerIds.includes(selfSeat.player_id);
    return { action: 'PLAYER_READY', ready: !isReady };
  };

  // Seated player with chips toggles ready
  const p1 = { player_id: 'u1', chips: 1000 };
  assert.deepEqual(
    handleSpaceInEndArea({ street: 'HAND_END', selfSeat: p1, readyPlayerIds: [] }),
    { action: 'PLAYER_READY', ready: true }
  );
  // Already ready player toggles unready
  assert.deepEqual(
    handleSpaceInEndArea({ street: 'HAND_END', selfSeat: p1, readyPlayerIds: ['u1'] }),
    { action: 'PLAYER_READY', ready: false }
  );
  // Idle street also supports readying
  assert.deepEqual(
    handleSpaceInEndArea({ street: 'IDLE', selfSeat: p1, readyPlayerIds: [] }),
    { action: 'PLAYER_READY', ready: true }
  );
  // Busted player (0 chips) triggers rebuy
  const busted = { player_id: 'u2', chips: 0 };
  assert.deepEqual(
    handleSpaceInEndArea({ street: 'HAND_END', selfSeat: busted }),
    { action: 'REBUY' }
  );
  // Spectator (no seat) does nothing
  assert.equal(
    handleSpaceInEndArea({ street: 'HAND_END', selfSeat: null }),
    null
  );
  // Active playing street does not trigger game-ended ready
  assert.equal(
    handleSpaceInEndArea({ street: 'FLOP', selfSeat: p1 }),
    null
  );
});

test('F1-F12 presets correctly arm pre-action raise when not yet my turn', () => {
  const setupPreAction = ({ presetShortcut, totalPot, callCost, maxVal, blindUnit }) => {
    const preset = getPresetByShortcut(presetShortcut);
    const amount = calculatePresetAmount({
      preset,
      totalPot,
      callCost,
      isRaise: true,
      blindUnit,
      minVal: 40,
      maxVal,
    });
    return {
      preAction: 'RAISE',
      targetAmount: amount,
    };
  };

  // F4 (Pot raise) in pre-action
  const prePot = setupPreAction({
    presetShortcut: 'F4',
    totalPot: 200,
    callCost: 40,
    maxVal: 1000,
    blindUnit: 10,
  });
  // effectivePot = 240, raiseAdd = 240, target = 0 + 40 + 240 = 280
  assert.equal(prePot.preAction, 'RAISE');
  assert.equal(prePot.targetAmount, 280);

  // F8 (All-in) in pre-action
  const preAllIn = setupPreAction({
    presetShortcut: 'F8',
    totalPot: 200,
    callCost: 40,
    maxVal: 650,
    blindUnit: 10,
  });
  assert.equal(preAllIn.preAction, 'RAISE');
  assert.equal(preAllIn.targetAmount, 650);
});

