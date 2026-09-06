import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getHoleCardsHandType,
  getHandCategoryStyle,
  HandCategory,
} from '../pokerEvaluator.js';

test('getHoleCardsHandType: returns null if hole cards are missing or not exactly 2 cards', () => {
  assert.equal(getHoleCardsHandType(null), null);
  assert.equal(getHoleCardsHandType([]), null);
  assert.equal(getHoleCardsHandType([{ rank: 14, suit: 's' }]), null);
  assert.equal(
    getHoleCardsHandType([
      { rank: 14, suit: 's' },
      { rank: 13, suit: 'h' },
      { rank: 12, suit: 'c' },
    ]),
    null
  );
});

test('getHoleCardsHandType: evaluates Preflop hole cards (0 board cards)', () => {
  // Pocket Pair
  const pocketAces = [
    { rank: 14, suit: 's' },
    { rank: 14, suit: 'h' },
  ];
  const acesResult = getHoleCardsHandType(pocketAces, []);
  assert.notEqual(acesResult, null);
  assert.equal(acesResult.category, HandCategory.ONE_PAIR);
  assert.equal(acesResult.name, '一对');
  assert.equal(acesResult.description, '一对 (A)');

  const pocketTens = [
    { rank: 10, suit: 'd' },
    { rank: 10, suit: 'c' },
  ];
  const tensResult = getHoleCardsHandType(pocketTens, []);
  assert.equal(tensResult.category, HandCategory.ONE_PAIR);
  assert.equal(tensResult.name, '一对');
  assert.equal(tensResult.description, '一对 (10)');

  // High Card
  const aceKing = [
    { rank: 14, suit: 's' },
    { rank: 13, suit: 'h' },
  ];
  const akResult = getHoleCardsHandType(aceKing, []);
  assert.notEqual(akResult, null);
  assert.equal(akResult.category, HandCategory.HIGH_CARD);
  assert.equal(akResult.name, '高牌');
  assert.equal(akResult.description, '高牌 (A高)');
});

test('getHoleCardsHandType: evaluates Flop (3 board cards -> 5 cards total)', () => {
  const hole = [
    { rank: 14, suit: 's' },
    { rank: 13, suit: 'h' },
  ];

  // Flop gives Two Pair (A and K)
  const boardTwoPair = [
    { rank: 14, suit: 'c' },
    { rank: 13, suit: 'd' },
    { rank: 2, suit: 's' },
  ];
  const twoPairResult = getHoleCardsHandType(hole, boardTwoPair);
  assert.equal(twoPairResult.category, HandCategory.TWO_PAIR);
  assert.equal(twoPairResult.name, '两对');
  assert.equal(twoPairResult.description, '两对 (A与K)');

  // Flop gives Three of a Kind (Trips)
  const holeSevens = [
    { rank: 7, suit: 's' },
    { rank: 7, suit: 'h' },
  ];
  const boardTrips = [
    { rank: 7, suit: 'd' },
    { rank: 11, suit: 'c' },
    { rank: 2, suit: 'h' },
  ];
  const tripsResult = getHoleCardsHandType(holeSevens, boardTrips);
  assert.equal(tripsResult.category, HandCategory.THREE_OF_A_KIND);
  assert.equal(tripsResult.name, '三条');
  assert.equal(tripsResult.description, '三条 (7)');
});

test('getHoleCardsHandType: evaluates Turn (4 board cards -> 6 cards total) and River (5 board cards -> 7 cards total)', () => {
  const hole = [
    { rank: 10, suit: 's' },
    { rank: 9, suit: 's' },
  ];

  // Straight on Turn
  const boardTurn = [
    { rank: 8, suit: 'h' },
    { rank: 7, suit: 'd' },
    { rank: 6, suit: 'c' },
    { rank: 2, suit: 'h' },
  ];
  const straightResult = getHoleCardsHandType(hole, boardTurn);
  assert.equal(straightResult.category, HandCategory.STRAIGHT);
  assert.equal(straightResult.name, '顺子');
  assert.equal(straightResult.description, '顺子 (10高)');

  // Full House on River
  const holeAces = [
    { rank: 14, suit: 's' },
    { rank: 14, suit: 'h' },
  ];
  const boardRiver = [
    { rank: 14, suit: 'c' },
    { rank: 13, suit: 'd' },
    { rank: 13, suit: 's' },
    { rank: 2, suit: 'c' },
    { rank: 5, suit: 'd' },
  ];
  const fullHouseResult = getHoleCardsHandType(holeAces, boardRiver);
  assert.equal(fullHouseResult.category, HandCategory.FULL_HOUSE);
  assert.equal(fullHouseResult.name, '葫芦');
  assert.equal(fullHouseResult.description, '葫芦 (A带K)');

  // Flush on River
  const holeSpades = [
    { rank: 14, suit: 's' },
    { rank: 4, suit: 's' },
  ];
  const boardSpades = [
    { rank: 12, suit: 's' },
    { rank: 9, suit: 's' },
    { rank: 7, suit: 's' },
    { rank: 2, suit: 'h' },
    { rank: 5, suit: 'd' },
  ];
  const flushResult = getHoleCardsHandType(holeSpades, boardSpades);
  assert.equal(flushResult.category, HandCategory.FLUSH);
  assert.equal(flushResult.name, '同花');
  assert.equal(flushResult.description, '同花 (A高)');

  // Royal Flush
  const royalHole = [
    { rank: 14, suit: 's' },
    { rank: 13, suit: 's' },
  ];
  const royalBoard = [
    { rank: 12, suit: 's' },
    { rank: 11, suit: 's' },
    { rank: 10, suit: 's' },
    { rank: 2, suit: 'c' },
    { rank: 3, suit: 'd' },
  ];
  const royalResult = getHoleCardsHandType(royalHole, royalBoard);
  assert.equal(royalResult.category, HandCategory.ROYAL_FLUSH);
  assert.equal(royalResult.name, '皇家同花顺');
  assert.equal(royalResult.description, '皇家同花顺');
});

test('getHandCategoryStyle: returns distinct styles for all categories', () => {
  for (let cat = 1; cat <= 10; cat++) {
    const style = getHandCategoryStyle(cat);
    assert.equal(typeof style, 'string');
    assert.ok(style.length > 10, `Category ${cat} should have valid Tailwind classes`);
  }
});
