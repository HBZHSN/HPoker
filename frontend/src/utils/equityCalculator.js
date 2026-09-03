/**
 * Monte Carlo Equity Calculator for Texas Hold'em.
 *
 * Simulates random opponent hands + remaining board cards and compares
 * hero's best-5-card hand against each opponent.
 */

import { generateDeck, shuffle, evaluateHand, compareEval, HandCategory } from './pokerEvaluator';

/** Determine the street stage from board card count. */
export function stageFromBoardCount(count) {
  if (count === 0) return 'PREFLOP';
  if (count === 3) return 'FLOP';
  if (count === 4) return 'TURN';
  if (count === 5) return 'RIVER';
  return null;
}

/**
 * Run Monte Carlo equity simulation.
 *
 * @param {Array} heroCards - hero's 2 hole cards [{rank, suit}]
 * @param {Array} boardCards - known community cards (0..5)
 * @param {number} numOpponents - number of active opponents to simulate
 * @param {number} iterations - number of Monte Carlo iterations (default 5000)
 * @returns {{winRate: number, tieRate: number, loseRate: number, handCategory: number, handCategoryName: string, description: string, stage: string, projected: {PREFLOP, FLOP, TURN, RIVER}}}
 */
export function calculateEquity(heroCards, boardCards, numOpponents, iterations = 5000) {
  if (!heroCards || heroCards.length !== 2) {
    return { error: '需要 2 张手牌' };
  }
  const stage = stageFromBoardCount(boardCards?.length || 0);

  // Build "dead cards" set (hero + known board)
  const dead = new Set();
  for (const c of heroCards) dead.add(`${c.rank}${c.suit}`);
  for (const c of boardCards || []) dead.add(`${c.rank}${c.suit}`);

  // Current hero hand strength (7 cards if possible)
  let currentHandEval = null;
  if ((boardCards?.length || 0) >= 3) {
    currentHandEval = evaluateHand([...heroCards, ...(boardCards || [])]);
  } else if ((boardCards?.length || 0) >= 1) {
    // Can't form 5 cards yet, but evaluate hero's 2 + any 3 from board doesn't exist yet
    // Show as pair/high based on hole cards only -> skip
    currentHandEval = evaluateHandIfPossible([...heroCards, ...(boardCards || [])]);
  } else {
    currentHandEval = evaluateHandIfPossible([...heroCards]);
  }

  const results = runMonteCarlo(heroCards, boardCards, numOpponents, iterations, dead);

  return {
    stage,
    winRate: results.wins / results.total,
    tieRate: results.ties / results.total,
    loseRate: results.losses / results.total,
    total: results.total,
    // category distribution at showdown (counting hero's winning hand type)
    categoryDistribution: results.categoryDistribution,
    // Hero's current hand strength description
    handCategory: currentHandEval?.category || HandCategory.HIGH_CARD,
    handCategoryName: currentHandEval ? categoryName(currentHandEval.category) : '-',
    description: currentHandEval?.description || '-',
    // Stage projection: what's the equity if we were at each stage
    projected: {
      PREFLOP: null, // computed below
      FLOP: null,
      TURN: null,
      RIVER: null,
    },
  };
}

/** Convenience — try to evaluate, or return minimal result if < 5 cards. */
function evaluateHandIfPossible(cards) {
  if (cards.length >= 5) return evaluateHand(cards);
  // For < 5 cards: build a fake eval using the highest card rank as "high card"
  const ranks = cards.map((c) => c.rank).sort((a, b) => b - a);
  return {
    category: HandCategory.HIGH_CARD,
    scoreVector: [HandCategory.HIGH_CARD, ...ranks, 0, 0, 0],
    description: `${cards.length === 2 ? '手牌' : '当前'}`,
  };
}

function categoryName(cat) {
  const names = {
    1: '高牌', 2: '一对', 3: '两对', 4: '三条', 5: '顺子',
    6: '同花', 7: '葫芦', 8: '四条', 9: '同花顺', 10: '皇家同花顺',
  };
  return names[cat] || '-';
}

/** Core Monte Carlo loop. */
function runMonteCarlo(heroCards, boardCards, numOpponents, iterations, deadSet) {
  let wins = 0;
  let ties = 0;
  let losses = 0;
  const categoryDistribution = new Map();

  for (let i = 0; i < iterations; i++) {
    // Build remaining deck
    const deck = generateDeck().filter((c) => !deadSet.has(`${c.rank}${c.suit}`));
    shuffle(deck);

    const remaining = 5 - (boardCards?.length || 0);
    const simulatedBoard = [...(boardCards || [])];
    for (let j = 0; j < remaining; j++) {
      simulatedBoard.push(deck.pop());
    }

    // Deal opponent hands
    const oppHands = [];
    for (let k = 0; k < numOpponents; k++) {
      oppHands.push([deck.pop(), deck.pop()]);
    }

    // Evaluate hero
    const heroEval = evaluateHand([...heroCards, ...simulatedBoard]);

    // Evaluate each opponent
    let heroBest = true;
    let tied = false;
    for (const opp of oppHands) {
      const oppEval = evaluateHand([...opp, ...simulatedBoard]);
      const cmp = compareEval(heroEval, oppEval);
      if (cmp < 0) { heroBest = false; break; }
      if (cmp === 0) { tied = true; }
    }

    if (heroBest) {
      if (tied) ties++; else wins++;
      categoryDistribution.set(heroEval.category, (categoryDistribution.get(heroEval.category) || 0) + 1);
    } else {
      losses++;
    }
  }

  return { wins, ties, losses, total: iterations, categoryDistribution };
}

/**
 * Compute "drawing probability" — chance of improving to each hand type
 * by river given current hero cards + board.
 *
 * For preflop & flop: simulates remaining board only (no opponents considered).
 * For turn: 1 remaining card.
 * For river: already complete.
 */
export function calculateDrawProbabilities(heroCards, boardCards, iterations = 3000) {
  const dead = new Set();
  for (const c of heroCards) dead.add(`${c.rank}${c.suit}`);
  for (const c of boardCards || []) dead.add(`${c.rank}${c.suit}`);

  const remaining = 5 - (boardCards?.length || 0);
  if (remaining === 0) {
    // River — just evaluate
    const ev = evaluateHand([...heroCards, ...(boardCards || [])]);
    const dist = new Map();
    dist.set(ev.category, 1);
    return { distribution: distToObj(dist), currentCategory: ev.category, currentDescription: ev.description };
  }

  const dist = new Map();
  for (let i = 0; i < iterations; i++) {
    const deck = generateDeck().filter((c) => !dead.has(`${c.rank}${c.suit}`));
    shuffle(deck);
    const simBoard = [...(boardCards || [])];
    for (let j = 0; j < remaining; j++) simBoard.push(deck.pop());
    const ev = evaluateHand([...heroCards, ...simBoard]);
    dist.set(ev.category, (dist.get(ev.category) || 0) + 1);
  }
  return {
    distribution: distToObj(dist),
    currentCategory: null,
    currentDescription: null,
    iterations,
  };
}

function distToObj(map) {
  const total = [...map.values()].reduce((a, b) => a + b, 0);
  const obj = {};
  for (const [cat, count] of map.entries()) {
    obj[cat] = { count, pct: count / total, name: categoryName(cat) };
  }
  return obj;
}

/** Hero's preflop hand strength score (Chen formula simplified).
 *  Returns 0-100 where higher is better. Used for instant visual before MC. */
export function preflopChenScore(card1, card2) {
  const hi = Math.max(card1.rank, card2.rank);
  const lo = Math.min(card1.rank, card2.rank);
  const suited = card1.suit === card2.suit;
  const gap = hi - lo;

  // High card points
  let score = 0;
  if (hi === 14) score += 10;
  else if (hi === 13) score += 8;
  else if (hi === 12) score += 7;
  else if (hi === 11) score += 6;
  else score += hi / 2;

  // Pair bonus
  if (hi === lo) score = Math.max(5, score) * 2;

  // Suited bonus
  if (suited) score += 2;

  // Connectedness
  if (hi !== lo) {
    if (gap === 1) score += 1;
    else if (gap === 2) score += 0.5;
    else if (gap === 3) score += 0;
    else score -= 1;
  }

  // A special bonus
  if (lo === 14) score += 1;

  // Normalize to 0-100
  return Math.min(100, Math.round((score / 25) * 100));
}
