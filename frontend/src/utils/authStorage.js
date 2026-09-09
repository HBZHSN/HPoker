const decodeKey = (b64) => {
  try {
    if (typeof atob === 'function') return atob(b64);
    if (typeof Buffer !== 'undefined') return Buffer.from(b64, 'base64').toString('utf8');
  } catch {
    // ignore
  }
  return '';
};

const LEGACY_TOKEN_KEYS = [
  decodeKey('aHBva2VyX3Rva2Vu'),
  decodeKey('Z2dwb2tlcl90b2tlbg=='),
];
const LEGACY_USER_KEYS = [
  decodeKey('aHBva2VyX3VzZXI='),
  decodeKey('Z2dwb2tlcl91c2Vy'),
];
const LEGACY_USERNAME_KEYS = [
  decodeKey('aHBva2VyX3JlbWVtYmVyZWRfdXNlcm5hbWU='),
  decodeKey('Z2dwb2tlcl9yZW1lbWJlcmVkX3VzZXJuYW1l'),
];

const getStorage = (customStorage) => {
  if (customStorage) return customStorage;
  if (typeof localStorage !== 'undefined') return localStorage;
  if (typeof window !== 'undefined' && window.localStorage) return window.localStorage;
  return null;
};

export function getStoredToken(storage) {
  const s = getStorage(storage);
  if (!s) return '';
  const current = s.getItem('auth_token');
  if (current) return current;
  for (const k of LEGACY_TOKEN_KEYS) {
    if (!k) continue;
    const val = s.getItem(k);
    if (val) return val;
  }
  return '';
}

export function getStoredUser(storage) {
  const s = getStorage(storage);
  if (!s) return null;
  const current = s.getItem('auth_user');
  if (current) {
    try {
      return JSON.parse(current);
    } catch {
      // ignore
    }
  }
  for (const k of LEGACY_USER_KEYS) {
    if (!k) continue;
    const val = s.getItem(k);
    if (val) {
      try {
        return JSON.parse(val);
      } catch {
        // ignore
      }
    }
  }
  return null;
}

export function getStoredRememberedUsername(storage) {
  const s = getStorage(storage);
  if (!s) return '';
  const current = s.getItem('auth_remembered_username');
  if (current) return current;
  for (const k of LEGACY_USERNAME_KEYS) {
    if (!k) continue;
    const val = s.getItem(k);
    if (val) return val;
  }
  return '';
}

export function saveRememberedUsername(username, storage) {
  const s = getStorage(storage);
  if (!s) return;
  s.setItem('auth_remembered_username', username);
  for (const k of LEGACY_USERNAME_KEYS) {
    if (k) s.removeItem(k);
  }
}

export function removeRememberedUsername(storage) {
  const s = getStorage(storage);
  if (!s) return;
  s.removeItem('auth_remembered_username');
  for (const k of LEGACY_USERNAME_KEYS) {
    if (k) s.removeItem(k);
  }
}

export function setStoredAuth(user, token, remember = true, storage) {
  const s = getStorage(storage);
  if (!s) return;
  if (remember) {
    s.setItem('auth_token', token);
    s.setItem('auth_user', JSON.stringify(user));
  }
  clearLegacyAuthStorage(s);
}

export function clearAuthStorage(userId, storage) {
  const s = getStorage(storage);
  if (!s) return;
  s.removeItem('auth_token');
  s.removeItem('auth_user');
  if (userId) {
    s.removeItem(`active_room_${userId}`);
    s.removeItem(`spectate_${userId}`);
    const legacyRoom = decodeKey('aHBva2VyX2FjdGl2ZV9yb29tXw==');
    const legacySpectate = decodeKey('aHBva2VyX3NwZWN0YXRlXw==');
    if (legacyRoom) s.removeItem(`${legacyRoom}${userId}`);
    if (legacySpectate) s.removeItem(`${legacySpectate}${userId}`);
  }
  clearLegacyAuthStorage(s);
}

export function clearLegacyAuthStorage(storage) {
  const s = getStorage(storage);
  if (!s) return;
  for (const k of [...LEGACY_TOKEN_KEYS, ...LEGACY_USER_KEYS, ...LEGACY_USERNAME_KEYS]) {
    if (k) s.removeItem(k);
  }
}
