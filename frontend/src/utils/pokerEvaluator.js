/**
 * Texas Hold'em 5/7-Card Hand Evaluator (JavaScript port of backend evaluator.py)
 *
 * Supports 10 hand categories with precise tie-breakers and
 * best-5-card extraction via C(n,5) brute force.
 */

// HandCategory enum
export const HandCategory = {
  HIGH_CARD: 1,
  ONE_PAIR: 2,
  TWO_PAIR: 3,
  THREE_OF_A_KIND: 4,
  STRAIGHT: 5,
  FLUSH: 6,
  FULL_HOUSE: 7,
  FOUR_OF_A_KIND: 8,
  STRAIGHT_FLUSH: 9,
  ROYAL_FLUSH: 10,
};

export const HandCategoryNames = {
  [HandCategory.HIGH_CARD]: '高牌',
  [HandCategory.ONE_PAIR]: '一对',
  [HandCategory.TWO_PAIR]: '两对',
  [HandCategory.THREE_OF_A_KIND]: '三条',
  [HandCategory.STRAIGHT]: '顺子',
  [HandCategory.FLUSH]: '同花',
  [HandCategory.FULL_HOUSE]: '葫芦',
  [HandCategory.FOUR_OF_A_KIND]: '四条',
  [HandCategory.STRAIGHT_FLUSH]: '同花顺',
  [HandCategory.ROYAL_FLUSH]: '皇家同花顺',
};

const SUIT_SYMBOL_MAP = { s: '♠', h: '♥', c: '♣', d: '♦' };

// ---------- Internal helpers ----------

function getRankSymbol(value) {
  if (value <= 9) return String(value);
  const map = { 10: '10', 11: 'J', 12: 'Q', 13: 'K', 14: 'A' };
  return map[value] || '?';
}

function getRankDisplayName(value) {
  return getRankSymbol(value);
}

/** Check if distinct descending ranks form a straight. Returns the highest rank or null.
 *  Handles standard straights and Wheel (A-2-3-4-5 -> returns 5). */
function checkStraight(ranksDesc) {
  const unique = [...new Set(ranksDesc)].sort((a, b) => b - a);
  if (unique.length < 5) return null;
  for (let i = 0; i <= unique.length - 5; i++) {
    if (unique[i] - unique[i + 4] === 4) return unique[i];
  }
  // Wheel A-2-3-4-5
  const set = new Set(unique);
  if (set.has(14) && set.has(5) && set.has(4) && set.has(3) && set.has(2)) return 5;
  return null;
}

/** Evaluate exactly 5 cards. Returns score vector for comparison. */
export function evaluate5Cards(cards) {
  if (!cards || cards.length !== 5) {
    throw new Error(`evaluate5Cards requires exactly 5 cards, got ${cards?.length}`);
  }

  // Sort descending by rank
  const sorted = [...cards].sort((a, b) => (b.rank ?? 0) - (a.rank ?? 0));
  const ranks = sorted.map((c) => c.rank);
  const suits = sorted.map((c) => c.suit);

  const isFlush = new Set(suits).size === 1;
  const straightTop = checkStraight(ranks);
  const isStraight = straightTop !== null;

  // Count rank frequencies
  const freq = new Map();
  for (const r of ranks) freq.set(r, (freq.get(r) || 0) + 1);
  const freqSorted = [...freq.entries()].sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1];
    return b[0] - a[0];
  });

  // 1. Royal / Straight Flush
  if (isFlush && isStraight) {
    if (straightTop === 14 && ranks.includes(10)) {
      return {
        category: HandCategory.ROYAL_FLUSH,
        scoreVector: [HandCategory.ROYAL_FLUSH, 14],
        description: '皇家同花顺',
      };
    }
    if (straightTop === 5) {
      return {
        category: HandCategory.STRAIGHT_FLUSH,
        scoreVector: [HandCategory.STRAIGHT_FLUSH, 5],
        description: '同花顺 (A-2-3-4-5)',
      };
    }
    return {
      category: HandCategory.STRAIGHT_FLUSH,
      scoreVector: [HandCategory.STRAIGHT_FLUSH, straightTop],
      description: `同花顺 (${getRankSymbol(straightTop)}高)`,
    };
  }

  // 2. Four of a Kind
  if (freqSorted[0][1] === 4) {
    const quad = freqSorted[0][0];
    const kicker = freqSorted[1][0];
    return {
      category: HandCategory.FOUR_OF_A_KIND,
      scoreVector: [HandCategory.FOUR_OF_A_KIND, quad, kicker],
      description: `四条 (${getRankSymbol(quad)})`,
    };
  }

  // 3. Full House
  if (freqSorted[0][1] === 3 && freqSorted[1][1] === 2) {
    const trips = freqSorted[0][0];
    const pair = freqSorted[1][0];
    return {
      category: HandCategory.FULL_HOUSE,
      scoreVector: [HandCategory.FULL_HOUSE, trips, pair],
      description: `葫芦 (${getRankSymbol(trips)}带${getRankSymbol(pair)})`,
    };
  }

  // 4. Flush
  if (isFlush) {
    return {
      category: HandCategory.FLUSH,
      scoreVector: [HandCategory.FLUSH, ...ranks],
      description: `同花 (${getRankSymbol(ranks[0])}高)`,
    };
  }

  // 5. Straight
  if (isStraight) {
    if (straightTop === 5) {
      return {
        category: HandCategory.STRAIGHT,
        scoreVector: [HandCategory.STRAIGHT, 5],
        description: '顺子 (A-2-3-4-5)',
      };
    }
    return {
      category: HandCategory.STRAIGHT,
      scoreVector: [HandCategory.STRAIGHT, straightTop],
      description: `顺子 (${getRankSymbol(straightTop)}高)`,
    };
  }

  // 6. Three of a Kind
  if (freqSorted[0][1] === 3) {
    const trips = freqSorted[0][0];
    const kickers = freqSorted.slice(1).map(([r]) => r);
    return {
      category: HandCategory.THREE_OF_A_KIND,
      scoreVector: [HandCategory.THREE_OF_A_KIND, trips, ...kickers],
      description: `三条 (${getRankSymbol(trips)})`,
    };
  }

  // 7. Two Pair
  if (freqSorted[0][1] === 2 && freqSorted[1][1] === 2) {
    const highPair = Math.max(freqSorted[0][0], freqSorted[1][0]);
    const lowPair = Math.min(freqSorted[0][0], freqSorted[1][0]);
    const kicker = freqSorted[2][0];
    return {
      category: HandCategory.TWO_PAIR,
      scoreVector: [HandCategory.TWO_PAIR, highPair, lowPair, kicker],
      description: `两对 (${getRankSymbol(highPair)}与${getRankSymbol(lowPair)})`,
    };
  }

  // 8. One Pair
  if (freqSorted[0][1] === 2) {
    const pair = freqSorted[0][0];
    const kickers = freqSorted.slice(1).map(([r]) => r);
    return {
      category: HandCategory.ONE_PAIR,
      scoreVector: [HandCategory.ONE_PAIR, pair, ...kickers],
      description: `一对 (${getRankSymbol(pair)})`,
    };
  }

  // 9. High Card
  return {
    category: HandCategory.HIGH_CARD,
    scoreVector: [HandCategory.HIGH_CARD, ...ranks],
    description: `高牌 (${getRankSymbol(ranks[0])}高)`,
  };
}

// ---------- Combination generator ----------

function* combinations(arr, k) {
  const n = arr.length;
  if (k > n) return;
  const indices = Array.from({ length: k }, (_, i) => i);
  yield indices.map((i) => arr[i]);
  while (true) {
    let i = k - 1;
    while (i >= 0 && indices[i] === i + n - k) i--;
    if (i < 0) return;
    indices[i]++;
    for (let j = i + 1; j < k; j++) indices[j] = indices[j - 1] + 1;
    yield indices.map((idx) => arr[idx]);
  }
}

/** Evaluate 5~7 cards, finding the best 5-card hand. */
export function evaluateHand(cards) {
  if (!cards || cards.length < 5) {
    return { category: 0, scoreVector: [0], description: '牌数不足' };
  }
  if (cards.length === 5) return evaluate5Cards(cards);

  let best = null;
  for (const combo of combinations(cards, 5)) {
    const evalResult = evaluate5Cards(combo);
    if (!best || compareEval(evalResult, best) > 0) {
      best = evalResult;
    }
  }
  return best;
}

/** Compare two evaluation results. Returns positive if a > b, negative if a < b, 0 if tie. */
export function compareEval(a, b) {
  const va = a.scoreVector;
  const vb = b.scoreVector;
  const len = Math.max(va.length, vb.length);
  for (let i = 0; i < len; i++) {
    const da = va[i] ?? 0;
    const db = vb[i] ?? 0;
    if (da !== db) return da - db;
  }
  return 0;
}

/** Generate a full 52-card deck. */
export function generateDeck() {
  const suits = ['s', 'h', 'c', 'd'];
  const deck = [];
  for (const s of suits) {
    for (let r = 2; r <= 14; r++) {
      deck.push({ rank: r, suit: s, key: `${r}${s}` });
    }
  }
  return deck;
}

/** Fisher-Yates shuffle (in place). */
export function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Evaluate the current best hand type given 2 hole cards and 0~5 board cards.
 * Returns { category: number, name: string, description: string } or null.
 */
export function getHoleCardsHandType(holeCards, boardCards = []) {
  if (!holeCards || holeCards.length !== 2) return null;

  // Filter and normalize cards
  const normalizeCard = (c) => {
    if (!c) return null;
    let rank = c.rank;
    if (typeof rank === 'string') {
      const map = { '10': 10, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14 };
      rank = map[rank.toUpperCase()] || Number(rank);
    }
    const suit = c.suit ? String(c.suit).toLowerCase() : 's';
    return { rank, suit };
  };

  const validHole = holeCards.map(normalizeCard).filter((c) => c && c.rank >= 2 && c.rank <= 14);
  if (validHole.length !== 2) return null;

  const validBoard = (boardCards || []).map(normalizeCard).filter((c) => c && c.rank >= 2 && c.rank <= 14);
  const allCards = [...validHole, ...validBoard];

  const rankText = (r) => {
    if (r === 14) return 'A';
    if (r === 13) return 'K';
    if (r === 12) return 'Q';
    if (r === 11) return 'J';
    if (r === 10) return '10';
    return String(r);
  };

  // If 5 or more cards, use full Texas Hold'em 5~7 card evaluator
  if (allCards.length >= 5) {
    try {
      const ev = evaluateHand(allCards);
      const name = HandCategoryNames[ev.category] || '高牌';
      return {
        category: ev.category,
        name,
        description: ev.description || name,
      };
    } catch {
      // Fallback below
    }
  }

  // Preflop or under 5 cards (e.g. 2 hole cards + 0~2 board cards)
  const ranks = allCards.map((c) => c.rank);
  const freq = new Map();
  for (const r of ranks) freq.set(r, (freq.get(r) || 0) + 1);
  const freqSorted = [...freq.entries()].sort((a, b) => {
    if (b[1] !== a[1]) return b[1] - a[1];
    return b[0] - a[0];
  });

  if (freqSorted[0][1] === 4) {
    return {
      category: HandCategory.FOUR_OF_A_KIND,
      name: '四条',
      description: `四条 (${rankText(freqSorted[0][0])})`,
    };
  }
  if (freqSorted[0][1] === 3) {
    return {
      category: HandCategory.THREE_OF_A_KIND,
      name: '三条',
      description: `三条 (${rankText(freqSorted[0][0])})`,
    };
  }
  if (freqSorted[0][1] === 2 && freqSorted.length >= 2 && freqSorted[1][1] === 2) {
    const high = Math.max(freqSorted[0][0], freqSorted[1][0]);
    const low = Math.min(freqSorted[0][0], freqSorted[1][0]);
    return {
      category: HandCategory.TWO_PAIR,
      name: '两对',
      description: `两对 (${rankText(high)}与${rankText(low)})`,
    };
  }
  if (freqSorted[0][1] === 2) {
    return {
      category: HandCategory.ONE_PAIR,
      name: '一对',
      description: `一对 (${rankText(freqSorted[0][0])})`,
    };
  }

  const highest = Math.max(...ranks);
  return {
    category: HandCategory.HIGH_CARD,
    name: '高牌',
    description: `高牌 (${rankText(highest)}高)`,
  };
}

/** Get Tailwind badge styling based on hand category */
export function getHandCategoryStyle(category) {
  switch (category) {
    case HandCategory.ROYAL_FLUSH:
      return 'bg-gradient-to-r from-amber-600/90 to-yellow-500/90 text-slate-950 border-amber-300 font-black shadow-amber-500/30';
    case HandCategory.STRAIGHT_FLUSH:
      return 'bg-gradient-to-r from-red-600/90 to-amber-600/90 text-white border-amber-400 font-black shadow-red-500/30';
    case HandCategory.FOUR_OF_A_KIND:
      return 'bg-rose-950/80 text-rose-200 border-rose-500/60 shadow-rose-900/40';
    case HandCategory.FULL_HOUSE:
      return 'bg-purple-950/80 text-purple-200 border-purple-500/60 shadow-purple-900/40';
    case HandCategory.FLUSH:
      return 'bg-indigo-950/80 text-indigo-200 border-indigo-500/60 shadow-indigo-900/40';
    case HandCategory.STRAIGHT:
      return 'bg-cyan-950/80 text-cyan-200 border-cyan-500/60 shadow-cyan-900/40';
    case HandCategory.THREE_OF_A_KIND:
      return 'bg-emerald-950/80 text-emerald-200 border-emerald-500/60 shadow-emerald-900/40';
    case HandCategory.TWO_PAIR:
      return 'bg-amber-950/80 text-amber-200 border-amber-500/60 shadow-amber-900/40';
    case HandCategory.ONE_PAIR:
      return 'bg-amber-950/60 text-amber-300/90 border-amber-500/40';
    case HandCategory.HIGH_CARD:
    default:
      return 'bg-slate-800/80 text-slate-300 border-slate-700/60';
  }
}

