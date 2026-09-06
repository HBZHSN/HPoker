import test from 'node:test';
import assert from 'node:assert/strict';
import {
  shouldMarkSocialActivityUnread,
  resolveSeatBubblePlacement,
} from '../socialNotifications.js';

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

test('resolveSeatBubblePlacement places left seats rightward and right seats leftward', () => {
  // Screen positions 1 and 2 are always on table left -> float rightward into table
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 1, seatLeftPercent: 12 }), 'right');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 2, seatLeftPercent: 13 }), 'right');

  // Screen positions 4 and 5 are always on table right -> float leftward into table
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 4, seatLeftPercent: 87 }), 'left');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 5, seatLeftPercent: 88 }), 'left');

  // Non-6-max edge cases: even if percentage math differed, screen positions 4 and 5 map to left
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 4, seatLeftPercent: 35 }), 'left');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 1, seatLeftPercent: 65 }), 'right');

  // Center / general seats
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 0, seatLeftPercent: 50 }), 'right');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 3, seatLeftPercent: 50 }), 'right');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 6, seatLeftPercent: 75 }), 'left');
  assert.equal(resolveSeatBubblePlacement({ screenIdx: 7, seatLeftPercent: 25 }), 'right');
});
