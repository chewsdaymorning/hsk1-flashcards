// Dictionary loading + prompt-pool construction.
//
// A "prompt" is a 2–3 letter sequence the player must embed in a word.
// Difficulty pools are built from how many dictionary words contain each
// sequence: a prompt in the "hard" pool may appear in as few as 80 words,
// while "easy" prompts appear in at least 800.

export const THRESHOLDS = { easy: 800, medium: 250, hard: 80 };

export async function loadDictionary(url = 'words.txt') {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`);
  const text = await res.text();
  const list = text.split('\n').map((w) => w.trim()).filter(Boolean);

  const counts = new Map();
  for (const word of list) {
    const seen = new Set();
    for (let len = 2; len <= 3; len++) {
      for (let i = 0; i + len <= word.length; i++) {
        seen.add(word.slice(i, i + len));
      }
    }
    for (const s of seen) counts.set(s, (counts.get(s) || 0) + 1);
  }

  const pools = { easy: [], medium: [], hard: [] };
  for (const [prompt, count] of counts) {
    for (const tier of Object.keys(THRESHOLDS)) {
      if (count >= THRESHOLDS[tier]) pools[tier].push(prompt);
    }
  }

  return { words: new Set(list), list, pools };
}

// Up to `limit` of the shortest unused words containing `prompt` — shown on
// the game-over screen so the player learns what would have saved them.
export function exampleWords(dict, prompt, used, limit = 3) {
  const found = [];
  for (const word of dict.list) {
    if (used.has(word) || !word.includes(prompt)) continue;
    found.push(word);
  }
  found.sort((a, b) => a.length - b.length || (a < b ? -1 : 1));
  return found.slice(0, limit);
}
