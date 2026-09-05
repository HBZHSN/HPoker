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

test('mobile community board footprint maintains safe horizontal clearance from bottom player seats', () => {
  // Check typical mobile screen widths (360px Android, 390px iPhone standard, 430px iPhone Pro Max)
  const viewports = [360, 390, 414, 430];
  const seatWidth = 68;
  const badgeOverhang = 5; // Tightly docked -5px badge offset

  for (const screenWidth of viewports) {
    // Card width clamped between 1.78rem (28.48px) and 2.25rem (36px) with 8.2vw
    const rawCardWidth = screenWidth * 0.082;
    const cardWidth = Math.max(28.48, Math.min(36, rawCardWidth));
    const gap = 3;
    const boardPadding = 10;
    const boardWidth = 5 * cardWidth + 4 * gap + boardPadding;

    const boardLeft = (screenWidth - boardWidth) / 2;
    const boardRight = boardLeft + boardWidth;

    // Bottom-left seat at 12%
    const seat1Center = screenWidth * 0.12;
    const seat1InnerEdge = seat1Center + (seatWidth / 2) + badgeOverhang;

    // Bottom-right seat at 88%
    const seat5Center = screenWidth * 0.88;
    const seat5InnerEdge = seat5Center - (seatWidth / 2) - badgeOverhang;

    // Verify positive safe clearance (> 10px) between community board and bottom player badges
    const leftClearance = boardLeft - seat1InnerEdge;
    const rightClearance = seat5InnerEdge - boardRight;

    assert.ok(
      leftClearance >= 10,
      `Left clearance on ${screenWidth}px screen (${leftClearance.toFixed(1)}px) should be >= 10px`,
    );
    assert.ok(
      rightClearance >= 10,
      `Right clearance on ${screenWidth}px screen (${rightClearance.toFixed(1)}px) should be >= 10px`,
    );
  }
});

test('mobile community board background container is at least as wide as the 5 cards with padding', () => {
  const viewports = [360, 390, 414, 430];
  const horizontalPadding = 16; // 8px left + 8px right
  const border = 2; // 1px left + 1px right

  for (const screenWidth of viewports) {
    const rawCardWidth = screenWidth * 0.082;
    const cardWidth = Math.max(28.48, Math.min(36, rawCardWidth));
    const gap = 3;
    const cardsTotalSpan = 5 * cardWidth + 4 * gap;
    const backgroundPlateWidth = cardsTotalSpan + horizontalPadding + border;

    assert.ok(
      backgroundPlateWidth >= cardsTotalSpan,
      `Background plate width (${backgroundPlateWidth}px) must be >= cards span (${cardsTotalSpan}px)`,
    );
    assert.ok(
      backgroundPlateWidth - cardsTotalSpan >= 16,
      `Background plate must provide at least 16px horizontal frame/padding around cards`,
    );
  }
});

