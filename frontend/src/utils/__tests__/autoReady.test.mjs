import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getInitialAutoReady,
  saveAutoReadyPreference,
  shouldTriggerAutoReady,
  formatAutoReadyCheckboxLabel,
  formatReadyButtonLabel,
  AUTO_READY_STORAGE_KEY,
} from '../autoReady.js';

test('getInitialAutoReady defaults to true when storage is empty or unavailable', () => {
  assert.equal(getInitialAutoReady(null), true);

  const emptyMockStorage = {
    getItem: () => null,
    setItem: () => {},
  };
  assert.equal(getInitialAutoReady(emptyMockStorage), true);
});

test('getInitialAutoReady respects saved boolean values in storage', () => {
  const mockStorageTrue = {
    getItem: (key) => (key === AUTO_READY_STORAGE_KEY ? 'true' : null),
  };
  assert.equal(getInitialAutoReady(mockStorageTrue), true);

  const mockStorageFalse = {
    getItem: (key) => (key === AUTO_READY_STORAGE_KEY ? 'false' : null),
  };
  assert.equal(getInitialAutoReady(mockStorageFalse), false);
});

test('saveAutoReadyPreference persists values to storage correctly', () => {
  const store = {};
  const mockStorage = {
    getItem: (k) => store[k] ?? null,
    setItem: (k, v) => { store[k] = String(v); },
  };

  saveAutoReadyPreference(false, mockStorage);
  assert.equal(mockStorage.getItem(AUTO_READY_STORAGE_KEY), 'false');

  saveAutoReadyPreference(true, mockStorage);
  assert.equal(mockStorage.getItem(AUTO_READY_STORAGE_KEY), 'true');
});

test('shouldTriggerAutoReady evaluates all readiness criteria', () => {
  // Positive case: open, autoReady, seated, not ready, not busted, countdown 0, not yet triggered
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: false,
      isBusted: false,
      hasSeat: true,
      hasAutoReadied: false,
      countdown: 0,
    }),
    true
  );

  // Negative case: countdown not yet reached 0
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: false,
      isBusted: false,
      hasSeat: true,
      hasAutoReadied: false,
      countdown: 3,
    }),
    false
  );

  // Negative case: already self-ready
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: true,
      isBusted: false,
      hasSeat: true,
      hasAutoReadied: false,
      countdown: 0,
    }),
    false
  );

  // Negative case: busted player
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: false,
      isBusted: true,
      hasSeat: true,
      hasAutoReadied: false,
      countdown: 0,
    }),
    false
  );

  // Negative case: spectator (no seat)
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: false,
      isBusted: false,
      hasSeat: false,
      hasAutoReadied: false,
      countdown: 0,
    }),
    false
  );

  // Negative case: autoReady turned off
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: false,
      isSelfReady: false,
      isBusted: false,
      hasSeat: true,
      hasAutoReadied: false,
      countdown: 0,
    }),
    false
  );

  // Negative case: already triggered once
  assert.equal(
    shouldTriggerAutoReady({
      isOpen: true,
      autoReady: true,
      isSelfReady: false,
      isBusted: false,
      hasSeat: true,
      hasAutoReadied: true,
      countdown: 0,
    }),
    false
  );
});

test('formatAutoReadyCheckboxLabel displays active countdown or default text', () => {
  assert.equal(
    formatAutoReadyCheckboxLabel({ autoReady: true, isSelfReady: false, countdown: 4 }),
    '4s 后自动准备'
  );
  assert.equal(
    formatAutoReadyCheckboxLabel({ autoReady: true, isSelfReady: true, countdown: 0 }),
    '5秒后自动准备'
  );
  assert.equal(
    formatAutoReadyCheckboxLabel({ autoReady: false, isSelfReady: false, countdown: 5 }),
    '5秒后自动准备'
  );
});

test('formatReadyButtonLabel displays state according to readiness and countdown', () => {
  assert.equal(
    formatReadyButtonLabel({ isSelfReady: true, autoReady: true, countdown: 0 }),
    '已准备'
  );
  assert.equal(
    formatReadyButtonLabel({ isSelfReady: false, autoReady: true, countdown: 3 }),
    '准备 (3s)'
  );
  assert.equal(
    formatReadyButtonLabel({ isSelfReady: false, autoReady: false, countdown: 0 }),
    '准备'
  );
});
