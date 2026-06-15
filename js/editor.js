// Per-frame editor: rotate in 90° steps + draggable/resizable crop box.
import { getState, updateFrameEdit } from './state.js';
import { $, blobToImage, imgWidth, imgHeight, bakeFrame, toast } from './util.js';

export function setupEditor() {
  const modal = $('#editorModal');
  const stage = $('#editorStage');
  const canvas = $('#editorCanvas');
  const box = $('#cropBox');
  const ctx = canvas.getContext('2d');

  let current = null;     // frame being edited
  let rotation = 0;       // 0/90/180/270
  let crop = null;        // stage-px rect {left, top, width, height}
  const MIN = 28;

  function canvasRect() {
    const cr = canvas.getBoundingClientRect();
    const sr = stage.getBoundingClientRect();
    return { left: cr.left - sr.left, top: cr.top - sr.top, width: cr.width, height: cr.height };
  }

  function applyBox() {
    box.style.left = crop.left + 'px';
    box.style.top = crop.top + 'px';
    box.style.width = crop.width + 'px';
    box.style.height = crop.height + 'px';
  }

  function resetCropToFull() {
    const c = canvasRect();
    crop = { left: c.left, top: c.top, width: c.width, height: c.height };
    applyBox();
  }

  function cropFromSaved(saved) {
    const c = canvasRect();
    crop = {
      left: c.left + saved.x * c.width,
      top: c.top + saved.y * c.height,
      width: saved.w * c.width,
      height: saved.h * c.height,
    };
    applyBox();
  }

  async function renderCanvas() {
    const img = await blobToImage(current.originalBlob);
    const iw = imgWidth(img), ih = imgHeight(img);
    const rot = ((rotation % 360) + 360) % 360;
    const swap = rot === 90 || rot === 270;
    canvas.width = swap ? ih : iw;
    canvas.height = swap ? iw : ih;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((rot * Math.PI) / 180);
    ctx.drawImage(img, -iw / 2, -ih / 2);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }

  function clampCrop() {
    const c = canvasRect();
    crop.width = Math.max(MIN, Math.min(crop.width, c.width));
    crop.height = Math.max(MIN, Math.min(crop.height, c.height));
    crop.left = Math.max(c.left, Math.min(crop.left, c.left + c.width - crop.width));
    crop.top = Math.max(c.top, Math.min(crop.top, c.top + c.height - crop.height));
  }

  // --- crop box interactions ---
  let mode = null;        // 'move' | 'nw' | 'ne' | 'sw' | 'se'
  let startPt = null;
  let startCrop = null;

  function onDown(e) {
    const handle = e.target.closest('.handle');
    mode = handle ? handle.dataset.h : 'move';
    startPt = { x: e.clientX, y: e.clientY };
    startCrop = { ...crop };
    box.setPointerCapture?.(e.pointerId);
    e.preventDefault();
  }

  function onMove(e) {
    if (!mode) return;
    const dx = e.clientX - startPt.x;
    const dy = e.clientY - startPt.y;
    crop = { ...startCrop };
    if (mode === 'move') {
      crop.left = startCrop.left + dx;
      crop.top = startCrop.top + dy;
    } else {
      const right = startCrop.left + startCrop.width;
      const bottom = startCrop.top + startCrop.height;
      if (mode.includes('w')) { crop.left = startCrop.left + dx; crop.width = right - crop.left; }
      if (mode.includes('e')) { crop.width = startCrop.width + dx; }
      if (mode.includes('n')) { crop.top = startCrop.top + dy; crop.height = bottom - crop.top; }
      if (mode.includes('s')) { crop.height = startCrop.height + dy; }
    }
    clampCrop();
    applyBox();
  }

  function onUp() { mode = null; }

  box.addEventListener('pointerdown', onDown);
  box.addEventListener('pointermove', onMove);
  box.addEventListener('pointerup', onUp);
  box.addEventListener('pointercancel', onUp);

  // --- toolbar ---
  $('#rotLeft').addEventListener('click', () => rotate(-90));
  $('#rotRight').addEventListener('click', () => rotate(90));
  $('#cropReset').addEventListener('click', () => resetCropToFull());

  async function rotate(delta) {
    rotation = ((rotation + delta) % 360 + 360) % 360;
    await renderCanvas();
    requestAnimationFrame(resetCropToFull); // crop coords reset after relayout
  }

  $('#editorApply').addEventListener('click', async () => {
    const c = canvasRect();
    const x = (crop.left - c.left) / c.width;
    const y = (crop.top - c.top) / c.height;
    const w = crop.width / c.width;
    const h = crop.height / c.height;
    const isFull = x <= 0.005 && y <= 0.005 && w >= 0.995 && h >= 0.995;
    const savedCrop = isFull ? null : { x, y, w, h };
    try {
      const renderBlob = await bakeFrame(current.originalBlob, rotation, savedCrop);
      updateFrameEdit(current.id, { rotation, crop: savedCrop, renderBlob });
      close();
      toast('Frame updated');
    } catch (err) {
      toast('Could not apply edit');
      console.error(err);
    }
  });

  function close() {
    modal.classList.add('hidden');
    current = null;
  }

  async function open(id) {
    const f = getState().frames.find((x) => x.id === id);
    if (!f) return;
    current = f;
    rotation = f.rotation || 0;
    modal.classList.remove('hidden');
    await renderCanvas();
    requestAnimationFrame(() => {
      if (f.crop) cropFromSaved(f.crop);
      else resetCropToFull();
    });
  }

  return { open };
}
