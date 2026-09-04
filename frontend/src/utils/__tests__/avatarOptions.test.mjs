import test from 'node:test';
import assert from 'node:assert/strict';
import { AVATAR_OPTIONS } from '../avatarOptions.js';

test('avatar options provide a broad, unique selection', () => {
  assert.ok(AVATAR_OPTIONS.length >= 60);
  assert.equal(AVATAR_OPTIONS.length, new Set(AVATAR_OPTIONS).size);
  for (const avatar of ['🐸', '🦖', '🤖', '🎲', '🃏']) {
    assert.ok(AVATAR_OPTIONS.includes(avatar));
  }
});
