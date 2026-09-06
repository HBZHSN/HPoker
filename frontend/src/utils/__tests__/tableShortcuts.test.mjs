import test from 'node:test';
import assert from 'node:assert/strict';
import {
  POT_PRESETS,
  BB_PRESETS,
  ALL_QUICK_PRESETS,
  parsePresetShortcut,
  getPresetByShortcut,
  calculatePresetAmount,
  resolveTableHotkey,
  isIgnoredInputTarget,
} from '../tableShortcuts.js';

test('POT_PRESETS and BB_PRESETS define shortcuts 1-8 for rows 1-2 and F1-F4 for row 3', () => {
  assert.equal(POT_PRESETS.length, 8);
  assert.equal(BB_PRESETS.length, 4);
  assert.equal(ALL_QUICK_PRESETS.length, 12);

  // Rows 1-2: 1 to 8
  const expectedPotKeys = ['1', '2', '3', '4', '5', '6', '7', '8'];
  for (let i = 0; i < 8; i++) {
    assert.equal(POT_PRESETS[i].shortcut, expectedPotKeys[i]);
    const retrieved = getPresetByShortcut(expectedPotKeys[i]);
    assert.ok(retrieved);
    assert.equal(retrieved.shortcut, expectedPotKeys[i]);
  }

  // Row 3: F1 to F4
  const expectedBBKeys = ['F1', 'F2', 'F3', 'F4'];
  for (let i = 0; i < 4; i++) {
    assert.equal(BB_PRESETS[i].shortcut, expectedBBKeys[i]);
    const retrieved = getPresetByShortcut(expectedBBKeys[i]);
    assert.ok(retrieved);
    assert.equal(retrieved.shortcut, expectedBBKeys[i]);
  }

  // Row 1 & 2 pot presets ending in All-in
  assert.equal(ALL_QUICK_PRESETS[0].label, '1/3 底池');
  assert.equal(ALL_QUICK_PRESETS[1].label, '1/2 底池');
  assert.equal(ALL_QUICK_PRESETS[2].label, '2/3 底池');
  assert.equal(ALL_QUICK_PRESETS[3].label, '底池');
  assert.equal(ALL_QUICK_PRESETS[4].label, '1.5底池');
  assert.equal(ALL_QUICK_PRESETS[5].label, '2底池');
  assert.equal(ALL_QUICK_PRESETS[6].label, '3底池');
  assert.equal(ALL_QUICK_PRESETS[7].label, '全下');
  assert.equal(ALL_QUICK_PRESETS[7].isMax, true);

  // Row 3 BB presets
  assert.equal(ALL_QUICK_PRESETS[8].label, '2.5 BB');
  assert.equal(ALL_QUICK_PRESETS[9].label, '3 BB');
  assert.equal(ALL_QUICK_PRESETS[10].label, '4 BB');
  assert.equal(ALL_QUICK_PRESETS[11].label, '5 BB');
});

test('parsePresetShortcut identifies numbers 1-8 and F1-F4', () => {
  // Numbers 1-8 via Digit and Numpad
  for (let i = 1; i <= 8; i++) {
    const digitRes = parsePresetShortcut({ code: `Digit${i}` });
    assert.ok(digitRes);
    assert.equal(digitRes.index, i - 1);
    assert.equal(digitRes.shortcut, String(i));

    const numpadRes = parsePresetShortcut({ code: `Numpad${i}` });
    assert.ok(numpadRes);
    assert.equal(numpadRes.index, i - 1);
    assert.equal(numpadRes.shortcut, String(i));

    const keyRes = parsePresetShortcut({ key: String(i) });
    assert.ok(keyRes);
    assert.equal(keyRes.index, i - 1);
  }

  // Function keys F1-F4 for row 3 (indices 8..11)
  for (let i = 1; i <= 4; i++) {
    const fRes = parsePresetShortcut({ code: `F${i}` });
    assert.ok(fRes);
    assert.equal(fRes.index, 7 + i);
    assert.equal(fRes.shortcut, `F${i}`);
    assert.equal(fRes.type, 'bb');

    const fKeyRes = parsePresetShortcut({ key: `F${i}` });
    assert.ok(fKeyRes);
    assert.equal(fKeyRes.index, 7 + i);
  }

  // 9, 0, and F5..F12 are not presets
  assert.equal(parsePresetShortcut({ code: 'Digit9' }), null);
  assert.equal(parsePresetShortcut({ code: 'Digit0' }), null);
  assert.equal(parsePresetShortcut({ code: 'F5' }), null);
  assert.equal(parsePresetShortcut({ code: 'F12' }), null);
  assert.equal(parsePresetShortcut({ code: 'KeyF' }), null);
  assert.equal(parsePresetShortcut(null), null);
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
  // Pot bet calculation: 1/2 pot of 100 with blind unit 10 (key '2')
  const halfPotPreset = getPresetByShortcut('2');
  const amountHalf = calculatePresetAmount({
    preset: halfPotPreset,
    totalPot: 100,
    blindUnit: 10,
    minVal: 20,
    maxVal: 1000,
  });
  assert.equal(amountHalf, 50);

  // All-in preset (key '8') returns maxVal
  const allInPreset = getPresetByShortcut('8');
  const amountAllIn = calculatePresetAmount({
    preset: allInPreset,
    totalPot: 100,
    minVal: 20,
    maxVal: 850,
  });
  assert.equal(amountAllIn, 850);

  // 3 BB preset (key 'F2') with BB 20
  const threeBBPreset = getPresetByShortcut('F2');
  const amount3BB = calculatePresetAmount({
    preset: threeBBPreset,
    bigBlind: 20,
    blindUnit: 10,
    minVal: 20,
    maxVal: 1000,
  });
  assert.equal(amount3BB, 60);

  // Raise pot calculation: pot 100, callCost 20, raise 1.0 pot (key '4')
  const fullPotPreset = getPresetByShortcut('4');
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
  // Numbers 1-8 for presets 0..7
  for (let i = 1; i <= 8; i++) {
    const res = resolveTableHotkey({ code: `Digit${i}` });
    assert.deepEqual(res, { type: 'PRESET', index: i - 1, shortcut: String(i) });
  }

  // F1-F4 for presets 8..11
  for (let i = 1; i <= 4; i++) {
    const res = resolveTableHotkey({ code: `F${i}` });
    assert.deepEqual(res, { type: 'PRESET', index: 7 + i, shortcut: `F${i}` });
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
  assert.equal(resolveTableHotkey({ code: 'Digit1', target: { tagName: 'INPUT' } }), null);
  assert.equal(resolveTableHotkey({ code: 'F1', target: { tagName: 'INPUT' } }), null);
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

test('presets correctly arm pre-action raise when not yet my turn', () => {
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

  // '4' (Pot raise) in pre-action
  const prePot = setupPreAction({
    presetShortcut: '4',
    totalPot: 200,
    callCost: 40,
    maxVal: 1000,
    blindUnit: 10,
  });
  // effectivePot = 240, raiseAdd = 240, target = 0 + 40 + 240 = 280
  assert.equal(prePot.preAction, 'RAISE');
  assert.equal(prePot.targetAmount, 280);

  // '8' (All-in) in pre-action
  const preAllIn = setupPreAction({
    presetShortcut: '8',
    totalPot: 200,
    callCost: 40,
    maxVal: 650,
    blindUnit: 10,
  });
  assert.equal(preAllIn.preAction, 'RAISE');
  assert.equal(preAllIn.targetAmount, 650);

  // 'F1' (2.5 BB) in pre-action
  const preBB = setupPreAction({
    presetShortcut: 'F1',
    totalPot: 200,
    callCost: 40,
    maxVal: 1000,
    blindUnit: 10,
  });
  assert.equal(preBB.preAction, 'RAISE');
  assert.equal(preBB.targetAmount, 50);
});
