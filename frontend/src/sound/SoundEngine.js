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
  }

  _initContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  setMuted(muted) {
    this.muted = muted;
  }

  setVolume(vol) {
    this.volume = Math.max(0, Math.min(1, vol));
  }

  play(soundName) {
    if (this.muted) return;
    try {
      this._initContext();
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
          this.playCountdownTick();
          break;
        case 'sit':
        case 'rebuy':
          this.playChime();
          break;
        default:
          break;
      }
    } catch (e) {
      console.warn("Audio play error:", e);
    }
  }

  playDealCard() {
    const ctx = this.ctx;
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
    setTimeout(() => this.playChipsClink(), 80);
  }

  playWinPot() {
    const ctx = this.ctx;
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

    setTimeout(() => this.playChipsClink(), 250);
  }

  playCountdownTick() {
    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);

    gain.gain.setValueAtTime(0.15 * this.volume, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.04);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.04);
  }

  playChime() {
    const ctx = this.ctx;
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
}

export const soundEngine = new SoundEngine();
