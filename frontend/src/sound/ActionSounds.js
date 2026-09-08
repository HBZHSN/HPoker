const actionSounds = {
  FOLD: 'fold', CHECK: 'check', CALL: 'call', BET: 'bet', RAISE: 'raise', ALL_IN: 'allin',
};
const eventSounds = { SIT_DOWN: 'sit', REBUY: 'rebuy', USE_TIME_CARD: 'time_card' };

// Track requests, rather than suppressing all sounds attributed to the local player:
// timeouts and actions in another tab still need their server-generated sound.
export class ActionSounds {
  constructor(engine) {
    this.engine = engine;
    this.pending = new Map();
    this.sequence = 0;
    this.session = `${Date.now()}-${Math.random()}`;
  }

  send(socket, event, payload, playerId) {
    if (!socket || socket.readyState !== 1) return;
    const sound = event === 'PLAYER_ACTION' ? actionSounds[payload.action] : eventSounds[event];
    const requestId = sound ? `${this.session}-${++this.sequence}` : undefined;
    socket.send(JSON.stringify({ event, payload, ...(requestId ? { sound_request_id: requestId } : {}) }));
    if (sound) {
      this.pending.set(requestId, { playerId, sound });
      // Rejected requests have no sound echo; keep their storage bounded.
      if (this.pending.size > 128) this.pending.delete(this.pending.keys().next().value);
      this.engine.play(sound);
    }
  }

  receive(payload) {
    const pending = this.pending.get(payload.sound_request_id);
    if (pending && pending.playerId === payload.player_id && pending.sound === payload.sound) {
      this.pending.delete(payload.sound_request_id);
      return;
    }
    this.engine.play(payload.sound);
  }

  reset() {
    this.pending.clear();
  }
}
