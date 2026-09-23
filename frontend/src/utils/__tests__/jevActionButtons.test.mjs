import assert from 'node:assert/strict';
import test from 'node:test';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('Jev probabilities highlight only the best current action', async () => {
  const vite = await createServer({ server: { middlewareMode: true, hmr: false }, appType: 'custom' });
  try {
    const { default: ActionBar } = await vite.ssrLoadModule('/src/components/ActionBar.jsx');
    const props = {
      isMyTurn: true,
      selfSeat: { player_id: 'u1', name: 'Player', has_cards: true, hole_cards: [], chips: 1000 },
      legalActions: { can_fold: true, can_call: true, call_amount: 20, can_raise: true, min_raise_to: 40, max_raise_to: 1000 },
      jevProbabilities: { fold: 0.1, call: 0.7, raise: 0.2 },
      street: 'PREFLOP',
      onAction: () => {},
    };
    const render = (changes = {}) => renderToStaticMarkup(React.createElement(ActionBar, { ...props, ...changes }));
    const active = render();
    assert.equal((active.match(/70\.0%/g) || []).length, 2);
    assert.equal((active.match(/ring-purple-300/g) || []).length, 2);
    assert.doesNotMatch(render({ jevProbabilities: null }), /70\.0%|ring-purple-300/);
    assert.doesNotMatch(render({ isMyTurn: false }), /70\.0%|ring-purple-300/);

    const { default: EquityDrawer, EquityTrigger } = await vite.ssrLoadModule('/src/components/EquityDrawer.jsx');
    const drawer = renderToStaticMarkup(React.createElement(EquityDrawer, { isOpen: true, isMyTurn: true }));
    assert.match(drawer, /poker-table-equity hidden lg:flex/);
    assert.doesNotMatch(drawer, /bg-black\/60/);
    assert.match(renderToStaticMarkup(React.createElement(EquityTrigger, { isOpen: true, status: 'loading' })), /计算中/);
    assert.match(renderToStaticMarkup(React.createElement(EquityTrigger, { isOpen: true, status: 'error' })), /获取失败/);
  } finally {
    await vite.close();
  }
});
