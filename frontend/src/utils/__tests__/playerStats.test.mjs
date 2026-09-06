import test from 'node:test';
import assert from 'node:assert/strict';
import {
  formatVpip,
  formatTimeCards,
  getVpipTooltip,
  getTimeCardsTooltip,
} from '../playerStats.js';

test('formatVpip: resolves direct vpip property or computes from hands', () => {
  // Empty or null
  assert.equal(formatVpip(null), 0);
  assert.equal(formatVpip({}), 0);

  // Direct vpip property
  assert.equal(formatVpip({ vpip: 28 }), 28);
  assert.equal(formatVpip({ vpip: 0 }), 0);
  assert.equal(formatVpip({ vpip: 100 }), 100);
  assert.equal(formatVpip({ vpip: 33.3 }), 33);

  // Fallback calculation from vpip_hands / hands_played
  assert.equal(formatVpip({ hands_played: 10, vpip_hands: 3 }), 30);
  assert.equal(formatVpip({ hands_played: 3, vpip_hands: 1 }), 33);
  assert.equal(formatVpip({ hands_played: 0, vpip_hands: 0 }), 0);

  // Clamping
  assert.equal(formatVpip({ vpip: -5 }), 0);
  assert.equal(formatVpip({ vpip: 120 }), 100);
});

test('formatTimeCards: resolves time_bank_cards or defaults to 3', () => {
  // Empty or null
  assert.equal(formatTimeCards(null), 3);
  assert.equal(formatTimeCards({}, 3), 3);
  assert.equal(formatTimeCards({}, 5), 5);

  // Explicit values
  assert.equal(formatTimeCards({ time_bank_cards: 0 }), 0);
  assert.equal(formatTimeCards({ time_bank_cards: 1 }), 1);
  assert.equal(formatTimeCards({ time_bank_cards: 3 }), 3);
  assert.equal(formatTimeCards({ time_bank_cards: 5 }), 5);
});

test('getVpipTooltip: builds descriptive VPIP string', () => {
  const tooltip = getVpipTooltip({ vpip: 30, vpip_hands: 3, hands_played: 10 });
  assert.equal(tooltip, 'VPIP: 30% (入池 3/10 手)');

  const zeroTooltip = getVpipTooltip(null);
  assert.equal(zeroTooltip, 'VPIP: 0% (入池 0/0 手)');
});

test('getTimeCardsTooltip: distinguishes self vs other players', () => {
  const otherTooltip = getTimeCardsTooltip({ time_bank_cards: 2, hands_played: 10 }, false);
  assert.equal(otherTooltip, '时间卡: 2张');

  const selfTooltip = getTimeCardsTooltip({ time_bank_cards: 2, hands_played: 10 }, true);
  assert.equal(selfTooltip, '时间卡: 2张 (已玩 10 手，每15手送1张)');
});
