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
