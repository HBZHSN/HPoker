/**
 * Player statistics and badge helpers for Texas Hold'em table seats.
 */

/**
 * Resolves the player's VPIP (Voluntarily Put in Pot) integer number (0-100).
 *
 * @param {Object} seatData Seat data object from backend table state
 * @returns {number} VPIP percentage as an integer (e.g. 24 for 24%)
 */
export function formatVpip(seatData) {
  if (!seatData) return 0;
  if (seatData.vpip !== undefined && seatData.vpip !== null) {
    return Math.max(0, Math.min(100, Math.round(Number(seatData.vpip) || 0)));
  }
  const handsPlayed = Number(seatData.hands_played) || 0;
  const vpipHands = Number(seatData.vpip_hands) || 0;
  if (handsPlayed <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((vpipHands / handsPlayed) * 100)));
}

/**
 * Resolves the player's time bank cards count.
 *
 * @param {Object} seatData Seat data object from backend table state
 * @param {number} defaultCards Default card count when undefined (default: 3)
 * @returns {number} Number of time bank cards held by player
 */
export function formatTimeCards(seatData, defaultCards = 3) {
  if (!seatData) return defaultCards;
  if (seatData.time_bank_cards !== undefined && seatData.time_bank_cards !== null) {
    return Math.max(0, Math.round(Number(seatData.time_bank_cards) || 0));
  }
  return defaultCards;
}

/**
 * Generates an informative hover tooltip for the VPIP badge.
 *
 * @param {Object} seatData Seat data object
 * @returns {string} Tooltip string
 */
export function getVpipTooltip(seatData) {
  const vpip = formatVpip(seatData);
  const handsPlayed = Number(seatData?.hands_played) || 0;
  const vpipHands = Number(seatData?.vpip_hands) || 0;
  return `VPIP: ${vpip}% (入池 ${vpipHands}/${handsPlayed} 手)`;
}

/**
 * Generates an informative hover tooltip for the time bank cards badge.
 *
 * @param {Object} seatData Seat data object
 * @param {boolean} isSelf Whether the seat belongs to the current user
 * @returns {string} Tooltip string
 */
export function getTimeCardsTooltip(seatData, isSelf = false) {
  const cards = formatTimeCards(seatData);
  const handsPlayed = Number(seatData?.hands_played) || 0;
  if (isSelf) {
    return `时间卡: ${cards}张 (已玩 ${handsPlayed} 手，每15手送1张)`;
  }
  return `时间卡: ${cards}张`;
}
