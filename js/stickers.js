// On-stage sticker layer: add, drag, resize, rotate and delete sticker overlays.
// Sticker geometry is stored as fractions of the stage (x/y centre, size = font
// height) so it maps straight onto the capture canvas regardless of screen size.
import { getState, addSticker, updateSticker, removeSticker } from './state.js';

const EMOJIS = [
  '😀', '😎', '😻', '🥳', '👻', '🤖', '👽', '💀',
  '🐶', '🐱', '🦄', '🦖', '🐠', '🐝', '🦋', '🌸',
  '🌟', '✨', '🔥', '🌈', '❤️', '💥', '⭐', '☁️',
  '🎈', '🎉', '👑', '⚽', '🚗', '🚀', '🍕', '🍩',
];

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function setupStickers(stage, layer, tray) {
  let selectedId = null;

  // --- sticker tray (emoji picker) ---
  EMOJIS.forEach((emoji) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sticker-pick';
    btn.textContent = emoji;
    btn.addEventListener('click', () => {
      const s = addSticker({ emoji });
      selectedId = s.id;
      tray.classList.add('hidden');
    });
    tray.appendChild(btn);
  });

  // Deselect when tapping empty stage (not a sticker).
  stage.addEventListener('pointerdown', (e) => {
    if (!e.target.closest('.sticker')) {
      if (selectedId !== null) { selectedId = null; render(); }
    }
  });

  function applyTransform(node, s, rect) {
    node.style.left = s.x * 100 + '%';
    node.style.top = s.y * 100 + '%';
    node.style.transform = `translate(-50%,-50%) rotate(${s.rotation || 0}deg)`;
    node.querySelector('.sticker-emoji').style.fontSize = (s.size || 0.2) * rect.height + 'px';
  }

  function makeNode(s) {
    const node = document.createElement('div');
    node.className = 'sticker';
    node.dataset.id = s.id;
    node.innerHTML =
      '<span class="sticker-emoji"></span>' +
      '<button type="button" class="sticker-del" title="Delete">✕</button>' +
      '<span class="sticker-handle rotate" title="Rotate">⟳</span>' +
      '<span class="sticker-handle resize" title="Resize">⤡</span>';
    node.querySelector('.sticker-emoji').textContent = s.emoji;

    node.querySelector('.sticker-del').addEventListener('pointerdown', (e) => {
      e.stopPropagation();
      e.preventDefault();
      if (selectedId === s.id) selectedId = null;
      removeSticker(s.id);
    });

    bindMove(node, s);
    bindHandle(node, node.querySelector('.resize'), s, 'resize');
    bindHandle(node, node.querySelector('.rotate'), s, 'rotate');
    return node;
  }

  // Drag the sticker body to move it.
  function bindMove(node, s) {
    const grip = node.querySelector('.sticker-emoji');
    grip.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      selectedId = s.id;
      render();
      const rect = stage.getBoundingClientRect();
      const startX = e.clientX, startY = e.clientY;
      const ox = s.x, oy = s.y;
      grip.setPointerCapture(e.pointerId);

      const move = (ev) => {
        s.x = clamp(ox + (ev.clientX - startX) / rect.width, 0, 1);
        s.y = clamp(oy + (ev.clientY - startY) / rect.height, 0, 1);
        node.style.left = s.x * 100 + '%';
        node.style.top = s.y * 100 + '%';
      };
      const up = () => {
        grip.removeEventListener('pointermove', move);
        grip.removeEventListener('pointerup', up);
        updateSticker(s.id, { x: s.x, y: s.y }, { silent: true });
      };
      grip.addEventListener('pointermove', move);
      grip.addEventListener('pointerup', up);
    });
  }

  // Corner handle: resize (distance from centre) or rotate (angle from centre).
  function bindHandle(node, handle, s, kind) {
    handle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      selectedId = s.id;
      render();
      const rect = stage.getBoundingClientRect();
      const cx = rect.left + s.x * rect.width;
      const cy = rect.top + s.y * rect.height;
      handle.setPointerCapture(e.pointerId);

      const move = (ev) => {
        const dx = ev.clientX - cx, dy = ev.clientY - cy;
        if (kind === 'resize') {
          // Handle sits at the box corner; corner dist ≈ (fontPx/2)*√2.
          s.size = clamp((Math.hypot(dx, dy) * Math.SQRT2) / rect.height, 0.05, 1.4);
          node.querySelector('.sticker-emoji').style.fontSize = s.size * rect.height + 'px';
        } else {
          s.rotation = (Math.atan2(dy, dx) * 180) / Math.PI + 90;
          node.style.transform = `translate(-50%,-50%) rotate(${s.rotation}deg)`;
        }
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
        updateSticker(s.id, kind === 'resize' ? { size: s.size } : { rotation: s.rotation }, { silent: true });
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });
  }

  function render() {
    const stickers = getState().stickers;
    const rect = stage.getBoundingClientRect();
    const byId = new Map([...layer.children].map((n) => [n.dataset.id, n]));

    // Drop nodes whose sticker is gone.
    for (const [id, node] of byId) {
      if (!stickers.some((s) => s.id === id)) { node.remove(); byId.delete(id); }
    }
    // Add / update remaining.
    for (const s of stickers) {
      let node = byId.get(s.id);
      if (!node) { node = makeNode(s); layer.appendChild(node); }
      applyTransform(node, s, rect);
      node.classList.toggle('selected', s.id === selectedId);
    }
  }

  window.addEventListener('resize', render);

  return { render };
}
