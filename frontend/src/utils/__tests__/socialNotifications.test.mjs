import test from 'node:test';
import assert from 'node:assert/strict';
import { shouldMarkSocialActivityUnread } from '../socialNotifications.js';

test('own social activity does not show an unread badge', () => {
  assert.equal(
    shouldMarkSocialActivityUnread({
      activityId: 'reaction-1',
      lastActivityId: null,
      playerId: 'me',
      currentUserId: 'me',
    }),
    false,
  );
});

test('another player activity shows an unread badge when chat is closed', () => {
  assert.equal(
    shouldMarkSocialActivityUnread({
      activityId: 'message-1',
      lastActivityId: null,
      playerId: 'other',
      currentUserId: 'me',
      chatOpen: false,
    }),
    true,
  );
  assert.equal(
    shouldMarkSocialActivityUnread({
      activityId: 'message-2',
      lastActivityId: null,
      playerId: 'other',
      currentUserId: 'me',
      chatOpen: true,
    }),
    false,
  );
});
