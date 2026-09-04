export const AUTO_READY_STORAGE_KEY = 'hpoker_auto_ready_hand_end';
export const DEFAULT_AUTO_READY_SECONDS = 5;

export function getInitialAutoReady(storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try {
    if (!storage) return true;
    const saved = storage.getItem(AUTO_READY_STORAGE_KEY);
    return saved !== null ? saved === 'true' : true;
  } catch {
    return true;
  }
}

export function saveAutoReadyPreference(enabled, storage = (typeof window !== 'undefined' ? window.localStorage : null)) {
  try {
    if (!storage) return;
    storage.setItem(AUTO_READY_STORAGE_KEY, String(enabled));
  } catch {
    // Ignore storage quota or security errors
  }
}

export function shouldTriggerAutoReady({
  isOpen = false,
  autoReady = false,
  isSelfReady = false,
  isBusted = false,
  hasSeat = false,
  hasAutoReadied = false,
  countdown = 0,
}) {
  return Boolean(
    isOpen &&
    autoReady &&
    !isSelfReady &&
    !isBusted &&
    hasSeat &&
    !hasAutoReadied &&
    countdown <= 0
  );
}

export function formatAutoReadyCheckboxLabel({
  autoReady = false,
  isSelfReady = false,
  countdown = 0,
}) {
  if (autoReady && !isSelfReady && countdown > 0) {
    return `${countdown}s 后自动准备`;
  }
  return '5秒后自动准备';
}

export function formatReadyButtonLabel({
  isSelfReady = false,
  autoReady = false,
  countdown = 0,
}) {
  if (isSelfReady) {
    return '已准备';
  }
  if (autoReady && countdown > 0) {
    return `准备 (${countdown}s)`;
  }
  return '准备';
}
