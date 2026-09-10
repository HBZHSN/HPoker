import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_ROOM_CONFIG,
  normalizeRoomDefaults,
} from '../roomDefaults.js';

test('room defaults keep the shared fallback values and derive blind metadata', () => {
  const normalized = normalizeRoomDefaults();

  assert.deepEqual(normalized, {
    ...DEFAULT_ROOM_CONFIG,
    big_blind: 20,
    assistant_win_pct: 70,
  });
});

test('room defaults normalize administrator values for the creation form', () => {
  const normalized = normalizeRoomDefaults({
    buyin_chips: 2500.8,
    cash_value: 375.567,
    small_blind: 25.4,
    action_timeout: 35.6,
    max_seats: 8,
    assistant_win_ratio: 0.856,
  });

  assert.equal(normalized.buyin_chips, 2501);
  assert.equal(normalized.cash_value, 375.57);
  assert.equal(normalized.small_blind, 25);
  assert.equal(normalized.big_blind, 50);
  assert.equal(normalized.action_timeout, 36);
  assert.equal(normalized.max_seats, 8);
  assert.equal(normalized.assistant_win_ratio, 0.856);
  assert.equal(normalized.assistant_win_pct, 86);
});

test('room defaults clamp malformed values to supported form ranges', () => {
  const normalized = normalizeRoomDefaults({
    buyin_chips: 1,
    cash_value: -5,
    small_blind: 0,
    action_timeout: 999,
    max_seats: 99,
    assistant_win_ratio: 0,
  });

  assert.equal(normalized.buyin_chips, 10);
  assert.equal(normalized.cash_value, 0);
  assert.equal(normalized.small_blind, 1);
  assert.equal(normalized.action_timeout, 60);
  assert.equal(normalized.max_seats, 9);
  assert.equal(normalized.assistant_win_ratio, 0.1);
  assert.equal(normalized.assistant_win_pct, 10);
});
