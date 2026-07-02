// Filmstrip: thumbnails with per-frame actions + pointer drag-to-reorder.
import { getState, removeFrame, duplicateFrame, reorderByIds } from './state.js';
import { $, $$ } from './util.js';

export function setupFilmstrip(container, { onEdit }) {
  let dragEl = null;
  let startX = 0, startY = 0;
  let pointerId = null;
  let pressedFrame = null;

  function render() {
    const { frames, aspect } = getState();
    const empty = $('#emptyHint');
    // Remove existing frame nodes (keep the hint element).
    $$('.frame', container).forEach((n) => n.remove());

    if (!frames.length) {
      if (empty) empty.classList.remove('hidden');
      return;
    }
    if (empty) empty.classList.add('hidden');

    frames.forEach((f, i) => {
      const el = document.createElement('div');
      el.className = 'frame';
      el.dataset.id = f.id;
      el.style.setProperty('--ar', aspect.replace(':', '/'));
      el.innerHTML = `
        <span class="index">${i + 1}</span>
        <img src="${f.thumbUrl}" alt="Frame ${i + 1}" draggable="false" />
        <div class="frame-actions">
          <button data-act="edit" title="Edit (crop & rotate)">✏️</button>
          <button data-act="dup" title="Duplicate">⧉</button>
          <button data-act="del" title="Delete">🗑️</button>
        </div>`;
      container.appendChild(el);
    });
  }

  // --- actions (event delegation) ---
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-act]');
    if (!btn) return;
    const frame = btn.closest('.frame');
    const id = frame?.dataset.id;
    if (!id) return;
    const act = btn.dataset.act;
    if (act === 'del') removeFrame(id);
    else if (act === 'dup') duplicateFrame(id);
    else if (act === 'edit') onEdit(id);
  });

  // --- pointer drag reordering ---
  container.addEventListener('pointerdown', (e) => {
    if (e.target.closest('button')) return; // let action buttons work
    const frame = e.target.closest('.frame');
    if (!frame) return;
    pressedFrame = frame;
    pointerId = e.pointerId;
    startX = e.clientX;
    startY = e.clientY;
  });

  container.addEventListener('pointermove', (e) => {
    if (e.pointerId !== pointerId || !pressedFrame) return;

    if (!dragEl) {
      const dx = Math.abs(e.clientX - startX);
      const dy = Math.abs(e.clientY - startY);
      // Begin dragging once horizontal intent is clear.
      if (dx > 8 && dx > dy) {
        dragEl = pressedFrame;
        dragEl.classList.add('dragging');
        try { container.setPointerCapture(pointerId); } catch { /* ok */ }
      } else {
        return;
      }
    }

    dragEl.style.pointerEvents = 'none';
    const under = document.elementFromPoint(e.clientX, e.clientY)?.closest?.('.frame');
    dragEl.style.pointerEvents = '';
    if (under && under !== dragEl && under.parentElement === container) {
      const rect = under.getBoundingClientRect();
      const after = e.clientX > rect.left + rect.width / 2;
      container.insertBefore(dragEl, after ? under.nextSibling : under);
    }
  });

  function endDrag() {
    if (dragEl) {
      dragEl.classList.remove('dragging');
      dragEl = null;
      const ids = $$('.frame', container).map((n) => n.dataset.id);
      reorderByIds(ids); // re-renders with fresh indices
    }
    pressedFrame = null;
    pointerId = null;
  }

  container.addEventListener('pointerup', endDrag);
  container.addEventListener('pointercancel', endDrag);

  return { render };
}
