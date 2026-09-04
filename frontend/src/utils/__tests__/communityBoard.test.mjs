import test from 'node:test';
import assert from 'node:assert/strict';
import { hasSecondCommunityBoard } from '../communityBoard.js';

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
