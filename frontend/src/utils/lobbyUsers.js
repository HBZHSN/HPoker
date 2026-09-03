/**
 * Return users that may be shown in the public lobby presence list.
 * Test accounts remain available to authentication and game flows, but are
 * intentionally hidden from the lobby user list.
 */
export function filterVisibleLobbyUsers(users = []) {
  if (!Array.isArray(users)) return [];
  return users.filter((user) => !user?.is_test);
}
