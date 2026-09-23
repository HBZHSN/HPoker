import test from 'node:test';
import assert from 'node:assert/strict';
import { isConfirmed } from '../useConfirmAction.js';

test('destructive action needs the same second click within five seconds', () => {
  const pending = { key: 'delete:room-1', expires: 5000 };
  assert.equal(isConfirmed(pending, 'delete:room-1', 4999), true);
  assert.equal(isConfirmed(pending, 'delete:room-2', 4999), false);
  assert.equal(isConfirmed(pending, 'delete:room-1', 5000), false);
});
