// App entry point: wires camera, filmstrip, editor, playback, export, controls.
import {
  init, onChange, getState,
  addFrame, clearFrames,
  setAspect, setFps, setOnionOpacity, setOnionOn, setLoop,
} from './state.js';
import { startCamera, flipCamera, capture, isActive } from './camera.js';
import { setupFilmstrip } from './filmstrip.js';
import { setupEditor } from './editor.js';
import { setupPlayer } from './playback.js';
import { setupExporter } from './exporter.js';
import { $, toast } from './util.js';

const video = $('#video');
const onion = $('#onion');
const stage = $('#stage');

const editor = setupEditor();
const player = setupPlayer();
const exporter = setupExporter();
const filmstrip = setupFilmstrip($('#filmstrip'), { onEdit: (id) => editor.open(id) });

// ---------- camera ----------
async function initCamera() {
  $('#cameraError').classList.add('hidden');
  try {
    await startCamera(video);
  } catch (e) {
    showCamError(e.message || 'Unable to access camera');
  }
}

function showCamError(msg) {
  $('#cameraErrorMsg').textContent = msg;
  $('#cameraError').classList.remove('hidden');
}

async function doCapture() {
  if (!isActive()) { toast('Camera not ready'); return; }
  try {
    const blob = await capture(video, getState().aspect);
    flash();
    addFrame({ originalBlob: blob, renderBlob: blob });
    // Scroll filmstrip to the newest frame.
    requestAnimationFrame(() => {
      const strip = $('#filmstrip');
      strip.scrollLeft = strip.scrollWidth;
    });
  } catch (e) {
    toast(e.message || 'Capture failed');
  }
}

function flash() {
  const f = $('#flash');
  f.classList.remove('fire');
  void f.offsetWidth; // restart animation
  f.classList.add('fire');
}

// ---------- controls ----------
$('#captureBtn').addEventListener('click', doCapture);
$('#flipBtn').addEventListener('click', async () => {
  try { await flipCamera(video); } catch (e) { showCamError(e.message); }
});
$('#retryCamera').addEventListener('click', initCamera);

$('#aspectSelect').addEventListener('change', (e) => setAspect(e.target.value));

$('#onionToggle').addEventListener('click', () => setOnionOn(!getState().onionOn));
$('#onionOpacity').addEventListener('input', (e) => {
  const v = Number(e.target.value);
  $('#onionVal').textContent = v + '%';
  setOnionOpacity(v / 100);
  applyOnion();
});

$('#fps').addEventListener('input', (e) => {
  const v = Number(e.target.value);
  $('#fpsVal').textContent = v + ' fps';
  setFps(v);
  player.refreshSpeed();
});

$('#loopChk').addEventListener('change', (e) => setLoop(e.target.checked));
$('#playBtn').addEventListener('click', () => player.open());
$('#exportBtn').addEventListener('click', () => exporter.run());

$('#clearAll').addEventListener('click', () => {
  if (!getState().frames.length) return;
  if (confirm('Delete all frames? This cannot be undone.')) clearFrames();
});

// Generic modal close buttons.
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-close]');
  if (!btn) return;
  const id = btn.dataset.close;
  if (id === 'playerModal') player.stop();
  else $('#' + id).classList.add('hidden');
});

// Keyboard: Space / Enter to capture when not in a field or modal.
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' || e.code === 'Enter') {
    const tag = (document.activeElement?.tagName || '').toLowerCase();
    const anyModalOpen = ['playerModal', 'editorModal', 'exportModal']
      .some((m) => !$('#' + m).classList.contains('hidden'));
    // Skip when a button is focused — it fires its own click for Space/Enter.
    if (tag === 'input' || tag === 'select' || tag === 'textarea' || tag === 'button' || anyModalOpen) return;
    e.preventDefault();
    doCapture();
  }
});

// ---------- onion skin ----------
function applyOnion() {
  const s = getState();
  const last = s.frames[s.frames.length - 1];
  if (last && s.onionOn) {
    if (onion.src !== last.thumbUrl) onion.src = last.thumbUrl;
    onion.style.opacity = String(s.onionOpacity);
  } else {
    onion.style.opacity = '0';
  }
}

// ---------- reactive UI ----------
function syncUI() {
  const s = getState();
  filmstrip.render();
  $('#frameCount').textContent = String(s.frames.length);
  stage.style.setProperty('--ar', s.aspect.replace(':', '/'));
  $('#onionToggle').classList.toggle('active', s.onionOn);
  $('#playBtn').disabled = !s.frames.length;
  $('#exportBtn').disabled = !s.frames.length;
  applyOnion();
}

function primeControlsFromState() {
  const s = getState();
  $('#aspectSelect').value = s.aspect;
  $('#fps').value = s.fps;
  $('#fpsVal').textContent = s.fps + ' fps';
  $('#onionOpacity').value = Math.round(s.onionOpacity * 100);
  $('#onionVal').textContent = Math.round(s.onionOpacity * 100) + '%';
  $('#loopChk').checked = s.loop;
}

// ---------- boot ----------
onChange(syncUI);
(async () => {
  await init();
  primeControlsFromState();
  syncUI();
  await initCamera();
})();
