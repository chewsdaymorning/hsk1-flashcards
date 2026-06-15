// In-app playback preview on a canvas at the chosen speed.
import { getState } from './state.js';
import { $, blobToImage, drawContain, projectSize, toast } from './util.js';

export function setupPlayer() {
  const modal = $('#playerModal');
  const canvas = $('#playerCanvas');
  const ctx = canvas.getContext('2d');
  const toggleBtn = $('#playerToggle');

  let bitmaps = [];
  let idx = 0;
  let timer = null;
  let playing = false;

  function drawAt(i) {
    const img = bitmaps[i];
    if (img) drawContain(ctx, img, canvas.width, canvas.height);
  }

  function step() {
    if (idx >= bitmaps.length) {
      if (getState().loop) { idx = 0; }
      else { pause(); return; }
    }
    drawAt(idx);
    idx++;
  }

  function play() {
    if (!bitmaps.length) return;
    playing = true;
    toggleBtn.textContent = '⏸ Pause';
    clearInterval(timer);
    step();
    timer = setInterval(step, 1000 / getState().fps);
  }

  function pause() {
    playing = false;
    clearInterval(timer);
    timer = null;
    toggleBtn.textContent = '▶ Play';
  }

  function stop() {
    pause();
    modal.classList.add('hidden');
  }

  function refreshSpeed() {
    if (playing) { clearInterval(timer); timer = setInterval(step, 1000 / getState().fps); }
  }

  toggleBtn.addEventListener('click', () => (playing ? pause() : play()));

  async function open() {
    const { frames, aspect } = getState();
    if (!frames.length) { toast('No frames to play yet'); return; }
    const [w, h] = projectSize(aspect);
    canvas.width = w; canvas.height = h;
    modal.classList.remove('hidden');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, w, h);
    bitmaps = await Promise.all(frames.map((f) => blobToImage(f.renderBlob)));
    idx = 0;
    play();
  }

  return { open, stop, refreshSpeed };
}
