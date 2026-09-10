import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatHCoins,
  formatHChipAmount,
  getDefaultRoomName,
  normalizeHCoinsMessage,
} from '../hCurrency.js';

test('formats H币 with signs and configurable precision', () => {
  assert.equal(formatHCoins(12.3), 'H币12.30');
  assert.equal(formatHCoins(12.3, { showPlus: true }), '+H币12.30');
  assert.equal(formatHCoins(-4.5), '-H币4.50');
  assert.equal(formatHCoins(0), 'H币0.00');
  assert.equal(formatHChipAmount(1200), 'H币1200');
});

test('builds a room name from the host identity', () => {
  assert.equal(getDefaultRoomName({ nickname: '小明', username: 'xiaoming' }), '小明的房间');
  assert.equal(getDefaultRoomName({ username: 'xiaoming' }), 'xiaoming的房间');
  assert.equal(getDefaultRoomName(), '房主的房间');
});

test('normalizes legacy insufficient-balance messages to H币不足', () => {
  assert.equal(normalizeHCoinsMessage('可用余额不足，请联系管理员充值'), 'H币不足');
  assert.equal(normalizeHCoinsMessage('Insufficient funds'), 'H币不足');
  assert.equal(normalizeHCoinsMessage('网络错误'), '网络错误');
  assert.equal(normalizeHCoinsMessage('', '加载失败'), '加载失败');
});
