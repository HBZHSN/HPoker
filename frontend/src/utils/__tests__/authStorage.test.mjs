import test from 'node:test';
import assert from 'node:assert/strict';

// Mock localStorage for node:test environment
const store = new Map();
global.localStorage = {
  getItem: (k) => store.get(k) || null,
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
  clear: () => store.clear(),
};

const {
  getStoredToken,
  getStoredUser,
  getStoredRememberedUsername,
  saveRememberedUsername,
  removeRememberedUsername,
  setStoredAuth,
  clearAuthStorage,
  clearLegacyAuthStorage,
} = await import('../authStorage.js');

test('authStorage: retrieves stored neutral token and migrates legacy token', () => {
  store.clear();
  assert.equal(getStoredToken(), '');

  // Legacy hpoker token fallback
  store.set('hpoker_token', 'legacy_token_123');
  assert.equal(getStoredToken(), 'legacy_token_123');

  // Neutral token takes precedence
  store.set('auth_token', 'neutral_token_456');
  assert.equal(getStoredToken(), 'neutral_token_456');
});

test('authStorage: retrieves stored neutral user and legacy user fallback', () => {
  store.clear();
  assert.equal(getStoredUser(), null);

  const testUser = { user_id: 'u1', nickname: 'Alice' };
  store.set('hpoker_user', JSON.stringify(testUser));
  assert.deepEqual(getStoredUser(), testUser);

  const neutralUser = { user_id: 'u2', nickname: 'Bob' };
  store.set('auth_user', JSON.stringify(neutralUser));
  assert.deepEqual(getStoredUser(), neutralUser);
});

test('authStorage: saves and removes remembered username with legacy cleanup', () => {
  store.clear();
  store.set('hpoker_remembered_username', 'old_user');
  assert.equal(getStoredRememberedUsername(), 'old_user');

  saveRememberedUsername('new_user');
  assert.equal(store.get('auth_remembered_username'), 'new_user');
  assert.equal(store.has('hpoker_remembered_username'), false);
  assert.equal(getStoredRememberedUsername(), 'new_user');

  removeRememberedUsername();
  assert.equal(store.has('auth_remembered_username'), false);
  assert.equal(getStoredRememberedUsername(), '');
});

test('authStorage: setStoredAuth and clearAuthStorage cleans legacy storage', () => {
  store.clear();
  store.set('hpoker_token', 'old_tok');
  store.set('hpoker_user', '{"user_id":"old"}');

  const user = { user_id: 'u_test', nickname: 'Tester' };
  setStoredAuth(user, 'token_xyz', true);
  assert.equal(store.get('auth_token'), 'token_xyz');
  assert.equal(store.has('hpoker_token'), false);
  assert.equal(store.has('hpoker_user'), false);

  clearAuthStorage('u_test');
  assert.equal(store.has('auth_token'), false);
  assert.equal(store.has('auth_user'), false);
});
