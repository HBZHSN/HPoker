/**
 * Decide whether a newly received social activity should show the chat badge.
 * Activities sent by the current user are already visible to that user and do
 * not count as unread.
 */
export function shouldMarkSocialActivityUnread({
  activityId,
  lastActivityId,
  playerId,
  currentUserId,
  chatOpen = false,
} = {}) {
  const isOwnActivity = Boolean(currentUserId) && playerId === currentUserId;
  return Boolean(
    activityId &&
    activityId !== lastActivityId &&
    !chatOpen &&
    !isOwnActivity
  );
}

/**
 * Determine the chat/emoji bubble placement direction for a table seat.
 * On mobile 6-max layout:
 * - Seats 1 & 2 are physically on the left side, so their bubbles float to the 'right' (inward).
 * - Seats 4 & 5 are physically on the right side, so their bubbles float to the 'left' (inward).
 * General layout / desktop:
 * - Seats on the right half (seatLeftPercent > 50) float 'left' (inward).
 * - Seats on the left half (seatLeftPercent <= 50) float 'right' (inward).
 */
export function resolveSeatBubblePlacement({ screenIdx, seatLeftPercent = 50 } = {}) {
  if (screenIdx === 4 || screenIdx === 5) {
    return 'left';
  }
  if (screenIdx === 1 || screenIdx === 2) {
    return 'right';
  }
  return Number(seatLeftPercent) > 50 ? 'left' : 'right';
}

