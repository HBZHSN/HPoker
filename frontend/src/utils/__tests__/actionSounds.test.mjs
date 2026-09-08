import test from 'node:test';
import assert from 'node:assert/strict';
import { ActionSounds } from '../../sound/ActionSounds.js';

function setup() {
  const played = [], sent = [];
  const sounds = new ActionSounds({ play: sound => played.push(sound) });
  const socket = { readyState: 1, send: data => sent.push(JSON.parse(data)) };
  return { sounds, played, sent, socket };
}

test('actions play immediately and only their correlated server echo is suppressed', () => {
  const { sounds, played, sent, socket } = setup();
  for (const action of ['CHECK', 'CALL', 'BET', 'RAISE', 'FOLD', 'ALL_IN']) {
    sounds.send(socket, 'PLAYER_ACTION', { action }, 'me');
    const sound = action === 'ALL_IN' ? 'allin' : action.toLowerCase();
    assert.equal(played.at(-1), sound);
    const count = played.length;
    sounds.receive({ sound, player_id: 'me', sound_request_id: sent.at(-1).sound_request_id });
    assert.equal(played.length, count);
  }
  sounds.receive({ sound: 'fold', player_id: 'me' }); // timeout
  sounds.receive({ sound: 'raise', player_id: 'other' });
  sounds.receive({ sound: 'deal' });
  sounds.receive({ sound: 'win_pot' });
  assert.deepEqual(played.slice(-4), ['fold', 'raise', 'deal', 'win_pot']);
});

test('seat, rebuy and time card sounds play locally and deduplicate', () => {
  const { sounds, played, sent, socket } = setup();
  for (const [event, sound] of [['SIT_DOWN', 'sit'], ['REBUY', 'rebuy'], ['USE_TIME_CARD', 'time_card']]) {
    sounds.send(socket, event, {}, 'me');
    sounds.receive({ sound, player_id: 'me', sound_request_id: sent.at(-1).sound_request_id });
  }
  assert.deepEqual(played, ['sit', 'rebuy', 'time_card']);
});

test('disconnected, failed sends and unrelated controls do not play action sounds', () => {
  const { sounds, played, sent, socket } = setup();
  sounds.send(null, 'PLAYER_ACTION', { action: 'FOLD' }, 'me');
  sounds.send({ ...socket, readyState: 3 }, 'PLAYER_ACTION', { action: 'FOLD' }, 'me');
  assert.throws(() => sounds.send({ readyState: 1, send() { throw Error('closed'); } }, 'PLAYER_ACTION', { action: 'FOLD' }, 'me'));
  sounds.send(socket, 'SHOW_CARD', {}, 'me');
  assert.deepEqual(played, []);
  assert.equal(sent[0].sound_request_id, undefined);
});

test('other tabs are audible and reconnect clears pending requests', () => {
  const { sounds, played, sent, socket } = setup();
  sounds.send(socket, 'PLAYER_ACTION', { action: 'CHECK' }, 'me');
  sounds.receive({ sound: 'check', player_id: 'me', sound_request_id: 'another-tab' });
  sounds.receive({ sound: 'check', player_id: 'other', sound_request_id: sent[0].sound_request_id });
  assert.equal(played.length, 3);
  sounds.reset();
  assert.equal(sounds.pending.size, 0);
  for (let i = 0; i < 150; i++) sounds.send(socket, 'PLAYER_ACTION', { action: 'CHECK' }, 'me');
  assert.equal(sounds.pending.size, 128);
});
