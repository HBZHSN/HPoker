/**
 * Return whether the table should render a second run-it-twice board.
 *
 * The RIT voting screen does not mean that a second board was agreed to:
 * until every contender votes, the final mode is still undecided.
 */
export function hasSecondCommunityBoard({
  ritEnabled = false,
  boardCards2 = [],
  boardCards2Full = [],
} = {}) {
  return Boolean(
    ritEnabled ||
    boardCards2.length > 0 ||
    boardCards2Full.length > 0
  );
}

/**
 * Return human-readable stage description for RIT voting based on dealt community cards.
 */
export function getRitStageDescription(boardCards = []) {
  const count = boardCards?.length || 0;
  if (count === 0) return '翻牌前 (尚未发牌)';
  if (count === 3) return '翻牌圈 (已发 3 张)';
  if (count === 4) return '转牌圈 (已发 4 张)';
  if (count >= 5) return '河牌圈 (已发 5 张)';
  return `已发 ${count} 张`;
}

/**
 * Return a fixed-length array of board slots (default 5 cards),
 * filled with dealt cards and null for remaining undealt slots.
 */
export function buildBoardSlots(boardCards = [], totalSlots = 5) {
  const safeCards = Array.isArray(boardCards) ? boardCards : [];
  return Array.from({ length: totalSlots }, (_, idx) => safeCards[idx] || null);
}

