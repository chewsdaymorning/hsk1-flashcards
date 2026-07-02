import { loadDictionary, THRESHOLDS, exampleWords } from './dictionary.js';
import { Game, DIFFICULTIES, MAX_LIVES, ALPHABET } from './game.js';

const $ = (id) => document.getElementById(id);

const screens = {
  loading: $('loadingScreen'),
  error: $('errorScreen'),
  menu: $('menuScreen'),
  game: $('gameScreen'),
  over: $('overScreen'),
};

function show(name) {
  for (const [key, el] of Object.entries(screens)) {
    el.classList.toggle('hidden', key !== name);
  }
}

const bestKey = (difficulty) => `bombparty.best.${difficulty}`;
const getBest = (difficulty) => Number(localStorage.getItem(bestKey(difficulty))) || 0;

let dict = null;
let game = null;
let difficulty = localStorage.getItem('bombparty.difficulty') || 'medium';

/* ---------- menu ---------- */

const DIFF_HINTS = {
  easy: `Common syllables (in ${THRESHOLDS.easy.toLocaleString()}+ words) · longer fuse`,
  medium: `Trickier syllables (in ${THRESHOLDS.medium.toLocaleString()}+ words) · shorter fuse`,
  hard: `Rare syllables (in as few as ${THRESHOLDS.hard.toLocaleString()} words) · short fuse`,
};

function buildMenu() {
  const seg = $('difficultySeg');
  seg.innerHTML = '';
  for (const [key, def] of Object.entries(DIFFICULTIES)) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'seg-btn';
    btn.textContent = def.label;
    btn.setAttribute('role', 'radio');
    btn.dataset.difficulty = key;
    btn.addEventListener('click', () => {
      difficulty = key;
      localStorage.setItem('bombparty.difficulty', key);
      refreshMenu();
    });
    seg.appendChild(btn);
  }
  refreshMenu();
}

function refreshMenu() {
  for (const btn of $('difficultySeg').children) {
    const active = btn.dataset.difficulty === difficulty;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-checked', String(active));
  }
  $('diffHint').textContent = DIFF_HINTS[difficulty];
  const best = getBest(difficulty);
  $('menuBest').textContent = best
    ? `Your best on ${DIFFICULTIES[difficulty].label.toLowerCase()}: ${best} words`
    : 'No games played on this difficulty yet.';
  $('topBest').textContent = '';
}

/* ---------- game screen ---------- */

const bomb = $('bomb');
const bombStage = $('bombStage');
const promptEl = $('prompt');
const input = $('answerInput');
const feedback = $('feedback');

function renderHearts(lives) {
  const el = $('hearts');
  el.innerHTML = '';
  for (let i = 0; i < MAX_LIVES; i++) {
    const span = document.createElement('span');
    span.className = 'heart' + (i < lives ? '' : ' empty');
    span.textContent = i < lives ? '❤️' : '🖤';
    el.appendChild(span);
  }
}

function buildAlphabet() {
  const el = $('alphabet');
  el.innerHTML = '';
  for (const ch of ALPHABET) {
    const span = document.createElement('span');
    span.className = 'letter';
    span.dataset.letter = ch;
    span.textContent = ch;
    el.appendChild(span);
  }
}

function renderLetters(usedLetters) {
  for (const el of $('alphabet').children) {
    el.classList.toggle('used', usedLetters.has(el.dataset.letter));
  }
}

let feedbackTimer = null;
function flashFeedback(text, kind) {
  feedback.textContent = text;
  feedback.className = `feedback ${kind}`;
  clearTimeout(feedbackTimer);
  feedbackTimer = setTimeout(() => {
    feedback.innerHTML = '&nbsp;';
    feedback.className = 'feedback';
  }, 2200);
}

const REJECT_MESSAGES = {
  letters: () => 'Letters only — no spaces or punctuation',
  missing: (prompt) => `Must contain “${prompt.toUpperCase()}”`,
  unknown: () => 'Not in the dictionary',
  used: () => 'Already played this game',
};

/* Bomb agitation: a continuous sine pulse whose frequency rises with fuse
   progress. Phase accumulates so speed changes never make it jump. */
let pulsePhase = 0;
let lastTick = 0;
let rafId = 0;

function tick(now) {
  if (game && game.state === 'playing' && !game.paused) {
    const progress = game.fuseProgress();
    const dt = (now - lastTick) / 1000;
    const hz = 0.9 + progress * 4.2;
    pulsePhase += dt * hz * Math.PI * 2;
    const scale = 1 + (0.04 + progress * 0.1) * Math.sin(pulsePhase);
    const tilt = Math.sin(pulsePhase * 0.5) * progress * 6;
    bomb.style.transform = `scale(${scale.toFixed(4)}) rotate(${tilt.toFixed(2)}deg)`;
    bombStage.style.setProperty('--danger', progress.toFixed(3));
  }
  lastTick = now;
  rafId = requestAnimationFrame(tick);
}

/* ---------- flow ---------- */

function startGame() {
  game.start(difficulty);
  show('game');
  bomb.textContent = '💣';
  bombStage.classList.remove('exploded');
  input.value = '';
  input.disabled = false;
  input.focus();
  $('topBest').textContent = getBest(difficulty) ? `best ${getBest(difficulty)}` : '';
}

function makeGame() {
  return new Game(dict, {
    onPrompt(prompt) {
      promptEl.textContent = prompt.toUpperCase();
      promptEl.classList.remove('contained');
      bombStage.style.setProperty('--danger', '0');
    },
    onSolved() {
      $('score').textContent = game.score;
      input.value = '';
      promptEl.classList.remove('contained');
    },
    onRejected(reason, word) {
      flashFeedback(REJECT_MESSAGES[reason](game.prompt, word), 'bad');
      bombStage.classList.remove('shake');
      void bombStage.offsetWidth; // restart the animation
      bombStage.classList.add('shake');
      input.select();
    },
    onLetters: renderLetters,
    onLivesChanged: renderHearts,
    onLifeGained() {
      flashFeedback('Alphabet complete — extra life! ❤️', 'good');
    },
    onExplode() {
      bomb.textContent = '💥';
      bomb.style.transform = 'scale(1.25)';
      bombStage.classList.add('exploded');
      input.disabled = true;
      flashFeedback('Boom! The fuse ran out.', 'bad');
    },
    onResume() {
      bomb.textContent = '💣';
      bombStage.classList.remove('exploded');
      input.disabled = false;
      input.value = '';
      input.focus();
    },
    onGameOver(score) {
      const best = getBest(difficulty);
      const isBest = score > best;
      if (isBest) localStorage.setItem(bestKey(difficulty), String(score));

      $('overScore').textContent = score;
      $('overBest').textContent = isBest
        ? '🏆 New personal best!'
        : `Your best on ${DIFFICULTIES[difficulty].label.toLowerCase()}: ${best}`;

      const examples = exampleWords(dict, game.prompt, game.used);
      $('overHint').textContent = examples.length
        ? `“${game.prompt.toUpperCase()}” would have accepted: ${examples.join(', ')}`
        : '';
      show('over');
    },
  });
}

/* ---------- wiring ---------- */

$('answerForm').addEventListener('submit', (e) => {
  e.preventDefault();
  game.submit(input.value);
});

input.addEventListener('input', () => {
  const word = input.value.trim().toLowerCase();
  promptEl.classList.toggle('contained', Boolean(game.prompt) && word.includes(game.prompt));
});

$('startBtn').addEventListener('click', startGame);
$('againBtn').addEventListener('click', startGame);
$('menuBtn').addEventListener('click', () => {
  game.stop();
  refreshMenu();
  show('menu');
});
$('retryBtn').addEventListener('click', init);

document.addEventListener('visibilitychange', () => {
  if (!game) return;
  if (document.hidden) game.pause();
  else game.resume();
});

async function init() {
  show('loading');
  try {
    dict = await loadDictionary();
  } catch (err) {
    $('errorDetail').textContent = String(err.message || err);
    show('error');
    return;
  }
  game = makeGame();
  buildMenu();
  buildAlphabet();
  renderHearts(0);
  show('menu');
  // Exposed for automated smoke tests; not part of the game's API.
  window.__bombparty = { game, dict };
}

init();
rafId = requestAnimationFrame(tick);
