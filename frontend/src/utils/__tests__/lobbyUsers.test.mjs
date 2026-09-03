import test from 'node:test';
import assert from 'node:assert/strict';
import { filterVisibleLobbyUsers } from '../lobbyUsers.js';

test('filterVisibleLobbyUsers: hides test accounts from the lobby list', () => {
  const users = [
    { user_id: 'u_real', nickname: 'Real player', is_test: false },
    { user_id: 'u_test1', nickname: 'Test player', is_test: true },
    { user_id: 'u_legacy', nickname: 'Legacy player' },
  ];

  assert.deepEqual(filterVisibleLobbyUsers(users), [users[0], users[2]]);
});

test('filterVisibleLobbyUsers: safely handles a missing user list', () => {
  assert.deepEqual(filterVisibleLobbyUsers(), []);
  assert.deepEqual(filterVisibleLobbyUsers(null), []);
});
