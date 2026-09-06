/**
 * Web Audio API Poker Sound Engine.
 * Provides realistic procedural sound effects for Texas Hold'em actions
 * without requiring external heavy audio files.
 */

class SoundEngine {
  constructor() {
    this.ctx = null;
    this.muted = false;
    this.volume = 0.7;
    this._wasBackgrounded = false;
    this._needsHardwareWakeup = false;
    this._listenersAttached = false;
    this._isUnlocking = false;

    if (typeof window !== 'undefined') {
      this._setupLifecycleListeners();
      this._setupUserGestureListeners();
    }
  }

  _setupLifecycleListeners() {
    if (typeof document === 'undefined' || typeof window === 'undefined') return;

    // Visibility change: background / foreground
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this._handleBackground();
      } else {
        this._handleForeground();
      }
    });

    // Mobile bfcache and focus/blur lifecycle
    window.addEventListener('pageshow', () => this._handleForeground());
    window.addEventListener('focus', () => this._handleForeground());
    window.addEventListener('pagehide', () => this._handleBackground());
    window.addEventListener('blur', () => {
      if (typeof document !== 'undefined' && document.hidden) {
        this._handleBackground();
      }
    });
  }

  _setupUserGestureListeners() {
    if (typeof window === 'undefined') return;
    if (this._listenersAttached) return;
    this._listenersAttached = true;

    const unlockHandler = () => {
      if (!this.muted) {
        if (!this.ctx || this.ctx.state !== 'running' || this._needsHardwareWakeup) {
          this.unlock();
        }
      }
    };

    const events = ['touchstart', 'touchend', 'pointerdown', 'click', 'keydown'];
    events.forEach((evt) => {
      window.addEventListener(evt, unlockHandler, { capture: true, passive: true });
    });
  }

  _handleBackground() {
    this._wasBackgrounded = true;
    this._needsHardwareWakeup = true;

    // Proactively suspend active audio context before OS aggressively cuts hardware off
    if (this.ctx && this.ctx.state === 'running') {
      try {
        this.ctx.suspend().catch(() => {});
      } catch (_) {}
    }
  }

  _handleForeground() {
    this._needsHardwareWakeup = true;
    this._resumeOrRestore();
  }

  _configureAudioSession() {
    if (typeof navigator !== 'undefined' && navigator.audioSession) {
      try {
        // 'playback' category keeps audio session alive and bypasses silent switch in iOS 17+
        navigator.audioSession.type = 'playback';
      } catch (_) {}
    }
  }

  _bindContextStateListener() {
    if (!this.ctx) return;
    try {
      this.ctx.onstatechange = () => {
        if (!this.ctx) return;
        if (this.ctx.state === 'suspended' || this.ctx.state === 'interrupted') {
          this._needsHardwareWakeup = true;
        }
      };
    } catch (_) {}
  }

  _initContext() {
    if (typeof window === 'undefined') return;

    if (!this.ctx || this.ctx.state === 'closed') {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        try {
          this.ctx = new AudioCtx();
          this._bindContextStateListener();
        } catch (e) {
          console.warn("[SoundEngine] Failed to initialize AudioContext:", e);
          return;
        }
      }
    }

    this._configureAudioSession();

    if (this.ctx && (this.ctx.state === 'suspended' || this.ctx.state === 'interrupted')) {
      try {
        this.ctx.resume().catch(() => {});
      } catch (_) {}
    }
  }

  _recreateContext() {
    try {
      if (this.ctx && typeof this.ctx.close === 'function') {
        this.ctx.close().catch(() => {});
      }
    } catch (_) {}
    this.ctx = null;

    const AudioCtx = typeof window !== 'undefined' ? (window.AudioContext || window.webkitAudioContext) : null;
    if (AudioCtx) {
      try {
        this.ctx = new AudioCtx();
        this._bindContextStateListener();
        this._configureAudioSession();
        if (this.ctx.state === 'suspended') {
          this.ctx.resume().catch(() => {});
        }
      } catch (e) {
        console.warn("[SoundEngine] Failed to recreate AudioContext:", e);
      }
    }
  }

  async _resumeOrRestore() {
    if (this.muted) return;

    this._configureAudioSession();

    if (!this.ctx || this.ctx.state === 'closed') {
      this._initContext();
      return;
    }

    // Programmatic resume attempt upon returning to foreground
    if (this.ctx.state === 'suspended' || this.ctx.state === 'interrupted') {
      try {
        await this.ctx.resume();
      } catch (err) {
        // Autoplay policy prevented resume without user gesture.
        // User gesture listener will handle it on next touch.
      }
    }
  }

  /**
   * Explicitly unlock audio within a user gesture (touchstart/click/touchend).
   */
  async unlock() {
    if (this.muted || this._isUnlocking) return;
    this._isUnlocking = true;

    try {
      this._configureAudioSession();

      if (!this.ctx || this.ctx.state === 'closed') {
        this._initContext();
      }

      if (this.ctx) {
        if (this.ctx.state === 'suspended' || this.ctx.state === 'interrupted') {
          try {
            await this.ctx.resume();
          } catch (e) {
            // Resume failed or threw InvalidStateError on iOS, recreate context
            this._recreateContext();
          }
        }

        // If context remains stuck in interrupted state even after resume, force recreate
        if (this.ctx && this.ctx.state === 'interrupted') {
          this._recreateContext();
        }

        // Hardware kick: play a 1-sample silent buffer to activate the audio output unit
        if (this.ctx && (this.ctx.state === 'running' || this.ctx.state === 'suspended')) {
          try {
            const buffer = this.ctx.createBuffer(1, 1, 22050);
            const source = this.ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(this.ctx.destination);
            source.start(0);
          } catch (_) {}
        }

        if (this.ctx && this.ctx.state === 'running') {
          this._needsHardwareWakeup = false;
          this._wasBackgrounded = false;
        }
      }
    } finally {
      this._isUnlocking = false;
    }
  }

  setMuted(muted) {
    this.muted = muted;
    if (!muted) {
      this.unlock();
    }
  }

  setVolume(vol) {
    this.volume = Math.max(0, Math.min(1, vol));
  }

  play(soundName, options = {}) {
    if (this.muted) return;
    try {
      this._initContext();
      if (!this.ctx) return;

      if (this.ctx.state === 'closed') {
        this._recreateContext();
      } else if (this.ctx.state === 'suspended' || this.ctx.state === 'interrupted') {
        this.ctx.resume().catch(() => {});
      }

      if (!this.ctx) return;

      switch (soundName) {
        case 'deal':
          this.playDealCard();
          break;
        case 'check':
          this.playCheckKnock();
          break;
        case 'call':
        case 'bet':
          this.playChipsClink();
          break;
        case 'raise':
          this.playRaise();
          break;
        case 'fold':
          this.playFold();
          break;
        case 'allin':
          this.playAllIn();
          break;
        case 'win_pot':
          this.playWinPot();
          break;
        case 'countdown':
          this.playCountdownTick(options?.secondsLeft ?? 5, options?.isMyTurn ?? false);
          break;
        case 'sit':
        case 'rebuy':
          this.playChime();
          break;
        case 'time_card':
          this.playTimeCard();
          break;
        case 'time_card_gain':
          this.playTimeCardGain();
          break;
        default:
          break;
      }
    } catch (e) {
      console.warn("Audio play error:", e);
      // Attempt recovery on subsequent action
      this._recreateContext();
    }
  }

  playDealCard() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const filter = ctx.createBiquadFilter();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(450, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(150, ctx.currentTime + 0.08);

    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(800, ctx.currentTime);

    gain.gain.setValueAtTime(0.3 * this.volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.08);
  }

  playCheckKnock() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    // Two quick knocks
    [0, 0.09].forEach(delay => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(120, ctx.currentTime + delay);
      osc.frequency.exponentialRampToValueAtTime(40, ctx.currentTime + delay + 0.06);

      gain.gain.setValueAtTime(0.5 * this.volume, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.06);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.06);
    });
  }

  playChipsClink() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    // Multi-frequency metallic clink
    [2400, 3100, 4200].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq + (Math.random() * 200 - 100), ctx.currentTime + i * 0.02);

      gain.gain.setValueAtTime(0.15 * this.volume, ctx.currentTime + i * 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.02 + 0.1);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + i * 0.02);
      osc.stop(ctx.currentTime + i * 0.02 + 0.1);
    });
  }

  playRaise() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    this.playChipsClink();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(350, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(700, ctx.currentTime + 0.18);

    gain.gain.setValueAtTime(0.3 * this.volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.2);
  }

  playFold() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(280, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.12);

    gain.gain.setValueAtTime(0.2 * this.volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.12);
  }

  playAllIn() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    // Sub-bass heavy thump
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(150, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(30, ctx.currentTime + 0.35);

    gain.gain.setValueAtTime(0.8 * this.volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.4);

    // Followed by crisp chips stack
    setTimeout(() => {
      if (!this.muted && this.ctx && this.ctx.state !== 'closed') {
        this.playChipsClink();
      }
    }, 80);
  }

  playWinPot() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    const chords = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
    chords.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.08);

      gain.gain.setValueAtTime(0.25 * this.volume, ctx.currentTime + idx * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.08 + 0.35);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + idx * 0.08);
      osc.stop(ctx.currentTime + idx * 0.08 + 0.35);
    });

    setTimeout(() => {
      if (!this.muted && this.ctx && this.ctx.state !== 'closed') {
        this.playChipsClink();
      }
    }, 250);
  }

  playCountdownTick(secondsLeft = 5, isMyTurn = false) {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;

    const volMultiplier = isMyTurn ? 1.0 : 0.65;
    const pitchMap = {
      5: 659.25, // E5
      4: 783.99, // G5
      3: 880.00, // A5
      2: 1046.50, // C6
      1: 1318.51, // E6
    };
    const freq = pitchMap[secondsLeft] || 880;

    // 1. Crisp percussive transient click (woodblock / digital metronome attack)
    const clickOsc = ctx.createOscillator();
    const clickGain = ctx.createGain();
    clickOsc.type = 'triangle';
    clickOsc.frequency.setValueAtTime(freq * 1.8, ctx.currentTime);
    clickOsc.frequency.exponentialRampToValueAtTime(120, ctx.currentTime + 0.015);

    clickGain.gain.setValueAtTime(0.18 * this.volume * volMultiplier, ctx.currentTime);
    clickGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.015);

    clickOsc.connect(clickGain);
    clickGain.connect(ctx.destination);
    clickOsc.start(ctx.currentTime);
    clickOsc.stop(ctx.currentTime + 0.015);

    // 2. Resonant tonal tick body
    if (secondsLeft === 1) {
      // Urgent double-tick for final 1s
      [0, 0.07].forEach((delay) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime + delay);
        osc.frequency.exponentialRampToValueAtTime(freq * 1.15, ctx.currentTime + delay + 0.06);

        gain.gain.setValueAtTime(0.3 * this.volume * volMultiplier, ctx.currentTime + delay);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.07);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(ctx.currentTime + delay);
        osc.stop(ctx.currentTime + delay + 0.07);
      });
    } else {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq * 0.96, ctx.currentTime + 0.05);

      gain.gain.setValueAtTime(0.22 * this.volume * volMultiplier, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.05);
    }
  }

  playChime() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    [440, 660].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.08);

      gain.gain.setValueAtTime(0.2 * this.volume, ctx.currentTime + idx * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.08 + 0.2);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + idx * 0.08);
      osc.stop(ctx.currentTime + idx * 0.08 + 0.2);
    });
  }

  playTimeCard() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    // Dramatic resonant dual-bell clock / chime for time extension
    [587.33, 880.0, 1174.66].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.06);
      osc.frequency.exponentialRampToValueAtTime(freq * 1.5, ctx.currentTime + idx * 0.06 + 0.35);

      gain.gain.setValueAtTime(0.35 * this.volume, ctx.currentTime + idx * 0.06);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.06 + 0.4);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + idx * 0.06);
      osc.stop(ctx.currentTime + idx * 0.06 + 0.4);
    });
  }

  playTimeCardGain() {
    const ctx = this.ctx;
    if (!ctx || ctx.state === 'closed') return;
    // Pleasant reward arpeggio when gaining a periodic time card
    [523.25, 659.25, 783.99, 1046.5].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + idx * 0.07);

      gain.gain.setValueAtTime(0.22 * this.volume, ctx.currentTime + idx * 0.07);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + idx * 0.07 + 0.25);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(ctx.currentTime + idx * 0.07);
      osc.stop(ctx.currentTime + idx * 0.07 + 0.25);
    });
  }
}

export { SoundEngine };
export const soundEngine = new SoundEngine();
export default soundEngine;
