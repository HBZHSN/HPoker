export const H_COIN_LABEL = 'H币';

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

export function formatHCoins(value, { showPlus = false, decimals = 2 } = {}) {
  const number = finiteNumber(value);
  const precision = Number.isInteger(decimals) ? Math.max(0, Math.min(6, decimals)) : 2;
  const amount = Math.abs(number).toFixed(precision);
  if (number > 0) return `${showPlus ? '+' : ''}${H_COIN_LABEL}${amount}`;
  if (number < 0) return `-${H_COIN_LABEL}${amount}`;
  return `${H_COIN_LABEL}${amount}`;
}

export function formatHChipAmount(value, showPlus = false) {
  return formatHCoins(value, { showPlus, decimals: 0 });
}

export function getDefaultRoomName(user) {
  const name = user?.nickname?.trim() || user?.username?.trim() || '房主';
  return `${name}的房间`;
}

export function normalizeHCoinsMessage(message, fallback = '请求失败') {
  const text = typeof message === 'string' ? message.trim() : '';
  if (!text) return fallback;
  if (
    /余额不足|可用余额不足|资金不足|现金不足|insufficient\s+(?:balance|funds|cash)/i.test(text) ||
    /请联系管理员(?:充值|重置)/.test(text)
  ) {
    return `${H_COIN_LABEL}不足`;
  }
  return text;
}
