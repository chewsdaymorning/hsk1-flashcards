// Game state machine. Owns the fuse timer; talks to the UI via the
// `events` callbacks passed to the constructor:
//   onPrompt(prompt)            new prompt shown (start, after solve/explosion)
//   onSolved(word, score)       word accepted
//   onRejected(reason, detail)  word rejected: 'letters'|'missing'|'unknown'|'used'
//   onLetters(usedLetters)      alphabet progress changed
//   onLifeGained(lives)         alphabet completed and a life restored
//   onLivesChanged(lives)       lives changed for any reason
//   onExplode(lives)            bomb went off (lives already decremented)
//   onResume()                  next prompt incoming after an explosion
//   onGameOver(score)           no lives left

export const DIFFICULTIES = {
  easy:   { label: 'Easy',   fuse: [8000, 16000] },
  medium: { label: 'Medium', fuse: [6000, 13000] },
  hard:   { label: 'Hard',   fuse: [5000, 10000] },
};

export const START_LIVES = 2;
export const MAX_LIVES = 3;
const EXPLOSION_PAUSE_MS = 1600;
export const ALPHABET = 'abcdefghijklmnopqrstuvwxyz';

export class Game {
  constructor(dict, events) {
    this.dict = dict;
    this.events = events;
    this.state = 'idle'; // idle | playing | exploding | gameover
    this.paused = false;
    this.timer = null;
  }

  emit(name, ...args) {
    if (this.events[name]) this.events[name](...args);
  }

  start(difficulty) {
    this.difficulty = difficulty;
    this.pool = this.dict.pools[difficulty];
    this.lives = START_LIVES;
    this.score = 0;
    this.used = new Set();
    this.usedLetters = new Set();
    this.prompt = null;
    this.paused = false;
    this.state = 'playing';
    this.emit('onLivesChanged', this.lives);
    this.emit('onLetters', this.usedLetters);
    this.nextPrompt();
  }

  nextPrompt() {
    let prompt = this.prompt;
    while (prompt === this.prompt) {
      prompt = this.pool[Math.floor(Math.random() * this.pool.length)];
    }
    this.prompt = prompt;
    this.emit('onPrompt', prompt);
    this.armFuse();
  }

  armFuse() {
    const [min, max] = DIFFICULTIES[this.difficulty].fuse;
    this.fuseDuration = min + Math.random() * (max - min);
    this.fuseRemaining = this.fuseDuration;
    this.fuseStarted = performance.now();
    clearTimeout(this.timer);
    if (!this.paused) {
      this.timer = setTimeout(() => this.explode(), this.fuseRemaining);
    }
  }

  // 0 at a fresh fuse, 1 at the explosion. Drives the bomb's agitation.
  fuseProgress() {
    if (this.state !== 'playing') return 0;
    const elapsed = this.paused ? 0 : performance.now() - this.fuseStarted;
    const remaining = Math.max(0, this.fuseRemaining - elapsed);
    return 1 - remaining / this.fuseDuration;
  }

  pause() {
    if (this.state !== 'playing' || this.paused) return;
    this.paused = true;
    clearTimeout(this.timer);
    this.fuseRemaining = Math.max(0, this.fuseRemaining - (performance.now() - this.fuseStarted));
  }

  resume() {
    if (this.state !== 'playing' || !this.paused) return;
    this.paused = false;
    this.fuseStarted = performance.now();
    this.timer = setTimeout(() => this.explode(), this.fuseRemaining);
  }

  submit(raw) {
    if (this.state !== 'playing' || this.paused) return;
    const word = raw.trim().toLowerCase();
    if (!word) return;

    if (!/^[a-z]+$/.test(word)) return this.emit('onRejected', 'letters', word);
    if (!word.includes(this.prompt)) return this.emit('onRejected', 'missing', word);
    if (!this.dict.words.has(word)) return this.emit('onRejected', 'unknown', word);
    if (this.used.has(word)) return this.emit('onRejected', 'used', word);

    this.used.add(word);
    this.score += 1;
    for (const ch of word) this.usedLetters.add(ch);

    if (this.usedLetters.size === ALPHABET.length) {
      this.usedLetters = new Set();
      if (this.lives < MAX_LIVES) {
        this.lives += 1;
        this.emit('onLivesChanged', this.lives);
        this.emit('onLifeGained', this.lives);
      }
    }

    this.emit('onLetters', this.usedLetters);
    this.emit('onSolved', word, this.score);
    this.nextPrompt();
  }

  explode() {
    if (this.state !== 'playing') return;
    this.state = 'exploding';
    clearTimeout(this.timer);
    this.lives -= 1;
    this.emit('onLivesChanged', this.lives);
    this.emit('onExplode', this.lives);

    this.timer = setTimeout(() => {
      if (this.lives > 0) {
        this.state = 'playing';
        this.emit('onResume');
        this.nextPrompt();
      } else {
        this.state = 'gameover';
        this.emit('onGameOver', this.score);
      }
    }, EXPLOSION_PAUSE_MS);
  }

  stop() {
    clearTimeout(this.timer);
    this.state = 'idle';
  }
}
