import test from 'node:test';
import assert from 'node:assert/strict';
import { SoundEngine } from '../../sound/SoundEngine.js';

// Helper mock AudioContext
class MockAudioContext {
  constructor(initialState = 'running', shouldFailResume = false) {
    this.state = initialState;
    this.shouldFailResume = shouldFailResume;
    this.currentTime = 1.0;
    this.destination = {};
    this.onstatechange = null;
    this.closed = false;
    this.resumeCalled = 0;
    this.suspendCalled = 0;
    this.closeCalled = 0;
    this.buffersCreated = 0;
  }

  async resume() {
    this.resumeCalled += 1;
    if (this.shouldFailResume) {
      throw new Error('InvalidStateError: Failed to start the audio device');
    }
    if (this.state !== 'closed') {
      this.state = 'running';
    }
    if (this.onstatechange) this.onstatechange();
  }

  async suspend() {
    this.suspendCalled += 1;
    if (this.state !== 'closed') {
      this.state = 'suspended';
    }
    if (this.onstatechange) this.onstatechange();
  }

  async close() {
    this.closeCalled += 1;
    this.closed = true;
    this.state = 'closed';
    if (this.onstatechange) this.onstatechange();
  }

  createBuffer(channels, length, sampleRate) {
    this.buffersCreated += 1;
    return { channels, length, sampleRate };
  }

  createBufferSource() {
    return {
      buffer: null,
      connect: () => {},
      start: () => {},
      stop: () => {},
    };
  }

  createOscillator() {
    return {
      type: 'sine',
      frequency: {
        setValueAtTime: () => {},
        exponentialRampToValueAtTime: () => {},
      },
      connect: () => {},
      start: () => {},
      stop: () => {},
    };
  }

  createGain() {
    return {
      gain: {
        setValueAtTime: () => {},
        exponentialRampToValueAtTime: () => {},
      },
      connect: () => {},
    };
  }

  createBiquadFilter() {
    return {
      type: 'lowpass',
      frequency: {
        setValueAtTime: () => {},
      },
      connect: () => {},
    };
  }
}

test('SoundEngine: instantiates cleanly and sets default properties', () => {
  const engine = new SoundEngine();
  assert.equal(engine.muted, false);
  assert.equal(engine.volume, 0.7);
  assert.equal(engine.ctx, null);

  engine.setVolume(0.5);
  assert.equal(engine.volume, 0.5);

  engine.setVolume(1.5);
  assert.equal(engine.volume, 1.0);

  engine.setVolume(-0.2);
  assert.equal(engine.volume, 0.0);
});

test('SoundEngine: handles background and foreground transitions correctly', async () => {
  const engine = new SoundEngine();
  const mockCtx = new MockAudioContext('running');
  engine.ctx = mockCtx;

  // Simulate switching to background (e.g. user switches to WeChat / locks phone)
  engine._handleBackground();
  assert.equal(engine._wasBackgrounded, true);
  assert.equal(engine._needsHardwareWakeup, true);
  assert.equal(mockCtx.suspendCalled, 1);
  assert.equal(mockCtx.state, 'suspended');

  // Simulate returning to foreground
  engine._handleForeground();
  assert.equal(engine._needsHardwareWakeup, true);
  // Programmatic resume should have been called
  assert.equal(mockCtx.resumeCalled, 1);
  assert.equal(mockCtx.state, 'running');
});

test('SoundEngine: unlock resumes suspended context and plays silent hardware wake-up buffer', async () => {
  const engine = new SoundEngine();
  const mockCtx = new MockAudioContext('suspended');
  engine.ctx = mockCtx;
  engine._needsHardwareWakeup = true;
  engine._wasBackgrounded = true;

  await engine.unlock();

  assert.equal(mockCtx.resumeCalled, 1);
  assert.equal(mockCtx.state, 'running');
  assert.equal(mockCtx.buffersCreated, 1); // 1-sample silent buffer was created & played
  assert.equal(engine._needsHardwareWakeup, false);
  assert.equal(engine._wasBackgrounded, false);
});

test('SoundEngine: recovers from iOS interrupted state when resume succeeds', async () => {
  const engine = new SoundEngine();
  const mockCtx = new MockAudioContext('interrupted');
  engine.ctx = mockCtx;
  engine._needsHardwareWakeup = true;

  await engine.unlock();

  assert.equal(mockCtx.resumeCalled, 1);
  assert.equal(mockCtx.state, 'running');
  assert.equal(mockCtx.buffersCreated, 1);
  assert.equal(engine._needsHardwareWakeup, false);
});

test('SoundEngine: recreates AudioContext if resume throws InvalidStateError on iOS', async () => {
  const engine = new SoundEngine();
  const brokenCtx = new MockAudioContext('interrupted', true); // shouldFailResume = true
  engine.ctx = brokenCtx;

  // Mock global AudioContext for recreation
  globalThis.window = {
    AudioContext: class extends MockAudioContext {
      constructor() {
        super('running');
      }
    },
  };

  try {
    await engine.unlock();

    // The old broken context must have been closed
    assert.equal(brokenCtx.closeCalled, 1);
    // engine.ctx must now be a new instance
    assert.notEqual(engine.ctx, brokenCtx);
    assert.equal(engine.ctx.state, 'running');
  } finally {
    delete globalThis.window;
  }
});

test('SoundEngine: recreates AudioContext if previous context was closed', async () => {
  const engine = new SoundEngine();
  const closedCtx = new MockAudioContext('closed');
  engine.ctx = closedCtx;

  globalThis.window = {
    AudioContext: class extends MockAudioContext {
      constructor() {
        super('running');
      }
    },
  };

  try {
    await engine.unlock();
    assert.notEqual(engine.ctx, closedCtx);
    assert.equal(engine.ctx.state, 'running');
  } finally {
    delete globalThis.window;
  }
});

test('SoundEngine: unmuting via setMuted(false) triggers unlock', async () => {
  const engine = new SoundEngine();
  let unlocked = false;
  engine.unlock = async () => {
    unlocked = true;
  };

  engine.setMuted(true);
  assert.equal(engine.muted, true);
  assert.equal(unlocked, false);

  engine.setMuted(false);
  assert.equal(engine.muted, false);
  assert.equal(unlocked, true);
});

test('SoundEngine: configures navigator.audioSession to playback if available', () => {
  const engine = new SoundEngine();
  const fakeSession = { type: 'ambient' };

  if (typeof globalThis.navigator !== 'undefined') {
    Object.defineProperty(globalThis.navigator, 'audioSession', {
      value: fakeSession,
      configurable: true,
      writable: true,
    });
  }

  try {
    engine._configureAudioSession();
    assert.equal(fakeSession.type, 'playback');
  } finally {
    if (typeof globalThis.navigator !== 'undefined') {
      delete globalThis.navigator.audioSession;
    }
  }
});

test('SoundEngine: play safely executes sound effects with mock context', () => {
  const engine = new SoundEngine();
  const mockCtx = new MockAudioContext('running');
  engine.ctx = mockCtx;

  // Testing all sound actions
  const sounds = ['deal', 'check', 'call', 'bet', 'raise', 'fold', 'allin', 'win_pot', 'countdown', 'sit', 'rebuy', 'time_card', 'time_card_gain'];
  for (const s of sounds) {
    assert.doesNotThrow(() => {
      engine.play(s);
    });
  }

  // When muted, play does nothing
  engine.setMuted(true);
  assert.doesNotThrow(() => {
    engine.play('deal');
  });
});
