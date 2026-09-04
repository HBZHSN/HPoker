import test from 'node:test';
import assert from 'node:assert/strict';
import {
  hasSecondCommunityBoard,
  getRitStageDescription,
  buildBoardSlots,
} from '../communityBoard.js';

test('RIT voting does not render a second board before the choice is finalized', () => {
  assert.equal(
    hasSecondCommunityBoard({
      ritEnabled: false,
      boardCards2: [],
      boardCards2Full: [],
    }),
    false,
  );
});

test('a confirmed RIT hand renders the second board', () => {
  assert.equal(hasSecondCommunityBoard({ ritEnabled: true }), true);
  assert.equal(hasSecondCommunityBoard({ boardCards2: [{ rank: 'A' }] }), true);
  assert.equal(hasSecondCommunityBoard({ boardCards2Full: [{ rank: 'K' }] }), true);
});

test('getRitStageDescription returns correct descriptions for each street', () => {
  assert.equal(getRitStageDescription([]), '翻牌前 (尚未发牌)');
  assert.equal(getRitStageDescription(null), '翻牌前 (尚未发牌)');
  assert.equal(getRitStageDescription(undefined), '翻牌前 (尚未发牌)');

  const flopCards = [{ notation: 'Ah' }, { notation: 'Kd' }, { notation: 'Qc' }];
  assert.equal(getRitStageDescription(flopCards), '翻牌圈 (已发 3 张)');

  const turnCards = [...flopCards, { notation: 'Js' }];
  assert.equal(getRitStageDescription(turnCards), '转牌圈 (已发 4 张)');

  const riverCards = [...turnCards, { notation: 'Ts' }];
  assert.equal(getRitStageDescription(riverCards), '河牌圈 (已发 5 张)');

  const customCards = [{ notation: '2h' }, { notation: '3d' }];
  assert.equal(getRitStageDescription(customCards), '已发 2 张');
});

test('buildBoardSlots generates 5 slots with cards and nulls for remaining', () => {
  // Empty cards
  const emptySlots = buildBoardSlots([]);
  assert.equal(emptySlots.length, 5);
  assert.deepEqual(emptySlots, [null, null, null, null, null]);

  // Null/undefined input
  assert.deepEqual(buildBoardSlots(null), [null, null, null, null, null]);

  // Flop: 3 cards
  const flopCards = [{ notation: 'Ah' }, { notation: 'Kd' }, { notation: 'Qc' }];
  const flopSlots = buildBoardSlots(flopCards);
  assert.equal(flopSlots.length, 5);
  assert.deepEqual(flopSlots, [flopCards[0], flopCards[1], flopCards[2], null, null]);

  // Turn: 4 cards
  const turnCards = [...flopCards, { notation: 'Js' }];
  const turnSlots = buildBoardSlots(turnCards);
  assert.equal(turnSlots.length, 5);
  assert.deepEqual(turnSlots, [turnCards[0], turnCards[1], turnCards[2], turnCards[3], null]);
});

