// Central app state: frames, project settings, persistence + change events.
import { db } from './db.js';
import { uid } from './util.js';

const listeners = new Set();

const state = {
  frames: [],          // [{ id, originalBlob, rotation, crop, renderBlob, thumbUrl }]
  aspect: '9:16',
  fps: 8,
  onionOpacity: 0.35,
  onionOn: true,
  loop: true,
  persistent: false,
};

function emit() {
  for (const fn of listeners) fn(state);
}

export function onChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function getState() { return state; }

// --- persistence -----------------------------------------------------------

function frameRecord(f) {
  return {
    id: f.id,
    originalBlob: f.originalBlob,
    rotation: f.rotation,
    crop: f.crop,
    renderBlob: f.renderBlob,
    order: state.frames.indexOf(f),
  };
}

async function persistFrame(f) {
  if (!state.persistent) return;
  try { await db.putFrame(frameRecord(f)); } catch { /* ignore */ }
}

async function persistMeta() {
  if (!state.persistent) return;
  try {
    await db.setMeta('settings', {
      aspect: state.aspect, fps: state.fps,
      onionOpacity: state.onionOpacity, onionOn: state.onionOn, loop: state.loop,
    });
  } catch { /* ignore */ }
}

// Re-save ordering for all frames (cheap: only the `order` field matters).
async function persistOrder() {
  if (!state.persistent) return;
  try {
    await Promise.all(state.frames.map((f) => db.putFrame(frameRecord(f))));
  } catch { /* ignore */ }
}

export async function init() {
  state.persistent = await db.available();
  if (state.persistent) {
    try {
      const settings = await db.getMeta('settings');
      if (settings) Object.assign(state, settings);
      const records = (await db.getAllFrames()) || [];
      records.sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
      state.frames = records.map((r) => ({
        id: r.id,
        originalBlob: r.originalBlob,
        rotation: r.rotation || 0,
        crop: r.crop || null,
        renderBlob: r.renderBlob,
        thumbUrl: URL.createObjectURL(r.renderBlob),
      }));
    } catch { /* start empty */ }
  }
  emit();
}

// --- mutations -------------------------------------------------------------

export function addFrame({ originalBlob, renderBlob }) {
  const f = {
    id: uid(),
    originalBlob,
    rotation: 0,
    crop: null,
    renderBlob,
    thumbUrl: URL.createObjectURL(renderBlob),
  };
  state.frames.push(f);
  persistFrame(f);
  emit();
  return f;
}

export function removeFrame(id) {
  const idx = state.frames.findIndex((f) => f.id === id);
  if (idx < 0) return;
  const [f] = state.frames.splice(idx, 1);
  URL.revokeObjectURL(f.thumbUrl);
  if (state.persistent) db.deleteFrame(id).catch(() => {});
  persistOrder();
  emit();
}

export function duplicateFrame(id) {
  const idx = state.frames.findIndex((f) => f.id === id);
  if (idx < 0) return;
  const src = state.frames[idx];
  const copy = {
    id: uid(),
    originalBlob: src.originalBlob,
    rotation: src.rotation,
    crop: src.crop ? { ...src.crop } : null,
    renderBlob: src.renderBlob,
    thumbUrl: URL.createObjectURL(src.renderBlob),
  };
  state.frames.splice(idx + 1, 0, copy);
  persistFrame(copy);
  persistOrder();
  emit();
}

export function moveFrame(fromIdx, toIdx) {
  if (fromIdx === toIdx) return;
  const [f] = state.frames.splice(fromIdx, 1);
  state.frames.splice(toIdx, 0, f);
  persistOrder();
  emit();
}

// Reorder the whole list to match an explicit array of frame ids.
export function reorderByIds(ids) {
  const map = new Map(state.frames.map((f) => [f.id, f]));
  const next = ids.map((id) => map.get(id)).filter(Boolean);
  if (next.length !== state.frames.length) return;
  state.frames = next;
  persistOrder();
  emit();
}

export function updateFrameEdit(id, { rotation, crop, renderBlob }) {
  const f = state.frames.find((x) => x.id === id);
  if (!f) return;
  URL.revokeObjectURL(f.thumbUrl);
  f.rotation = rotation;
  f.crop = crop;
  f.renderBlob = renderBlob;
  f.thumbUrl = URL.createObjectURL(renderBlob);
  persistFrame(f);
  emit();
}

export function clearFrames() {
  for (const f of state.frames) URL.revokeObjectURL(f.thumbUrl);
  state.frames = [];
  if (state.persistent) db.clearFrames().catch(() => {});
  emit();
}

export function setAspect(aspect) { state.aspect = aspect; persistMeta(); emit(); }
export function setFps(fps) { state.fps = fps; persistMeta(); }
export function setOnionOpacity(v) { state.onionOpacity = v; persistMeta(); }
export function setOnionOn(v) { state.onionOn = v; persistMeta(); emit(); }
export function setLoop(v) { state.loop = v; persistMeta(); }
