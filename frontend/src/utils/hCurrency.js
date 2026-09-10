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
    /\u4f59\u989d\u4e0d\u8db3|\u53ef\u7528\u4f59\u989d\u4e0d\u8db3|\u8d44\u91d1\u4e0d\u8db3|\u73b0\u91d1\u4e0d\u8db3|insufficient\s+(?:balance|funds|cash)/i.test(text) ||
    /\u8bf7\u8054\u7cfb\u7ba1\u7406\u5458(?:\u5145\u503c|\u91cd\u7f6e)/.test(text)
  ) {
    return `${H_COIN_LABEL}不足`;
  }
  return text;
}
