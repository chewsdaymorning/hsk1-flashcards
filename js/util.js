// Shared helpers: aspect ratios, image rendering, small DOM utilities.

export const ASPECTS = {
  '1:1':  [1, 1],
  '4:5':  [4, 5],
  '9:16': [9, 16],
  '16:9': [16, 9],
  '4:3':  [4, 3],
  '3:4':  [3, 4],
};

// Output canvas size for a given aspect, with the long edge at `base` px.
export function projectSize(aspect, base = 1080) {
  const [w, h] = ASPECTS[aspect] || ASPECTS['1:1'];
  if (w >= h) return [base, Math.round((base * h) / w)];
  return [Math.round((base * w) / h), base];
}

export function uid() {
  return 'f_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
}

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return [...root.querySelectorAll(sel)]; }

// Decode a Blob into an ImageBitmap (preferred) or HTMLImageElement fallback.
export async function blobToImage(blob) {
  if ('createImageBitmap' in window) {
    try { return await createImageBitmap(blob); } catch { /* fall through */ }
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = reject;
      el.src = url;
    });
    return img;
  } finally {
    // Revoke after the image element has loaded its pixels.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function imgWidth(img) { return img.width || img.naturalWidth; }
export function imgHeight(img) { return img.height || img.naturalHeight; }

// Draw an image into a ctx of size (cw, ch) using "contain" with a black bg.
export function drawContain(ctx, img, cw, ch) {
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, cw, ch);
  const iw = imgWidth(img), ih = imgHeight(img);
  const scale = Math.min(cw / iw, ch / ih);
  const dw = iw * scale, dh = ih * scale;
  ctx.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
}

export function canvasToBlob(canvas, type = 'image/jpeg', quality = 0.92) {
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), type, quality));
}

// Bake rotation (0/90/180/270) + normalized crop into a new JPEG blob.
// `crop` is {x,y,w,h} in 0..1 coords relative to the rotated image.
export async function bakeFrame(originalBlob, rotation = 0, crop = null) {
  const img = await blobToImage(originalBlob);
  const iw = imgWidth(img), ih = imgHeight(img);
  const rot = ((rotation % 360) + 360) % 360;
  const swap = rot === 90 || rot === 270;
  const rw = swap ? ih : iw;
  const rh = swap ? iw : ih;

  const rc = document.createElement('canvas');
  rc.width = rw; rc.height = rh;
  const rctx = rc.getContext('2d');
  rctx.translate(rw / 2, rh / 2);
  rctx.rotate((rot * Math.PI) / 180);
  rctx.drawImage(img, -iw / 2, -ih / 2);

  if (!crop) return canvasToBlob(rc);

  const cx = Math.round(crop.x * rw);
  const cy = Math.round(crop.y * rh);
  const cw = Math.max(1, Math.round(crop.w * rw));
  const ch = Math.max(1, Math.round(crop.h * rh));
  const cc = document.createElement('canvas');
  cc.width = cw; cc.height = ch;
  cc.getContext('2d').drawImage(rc, cx, cy, cw, ch, 0, 0, cw, ch);
  return canvasToBlob(cc);
}

let toastTimer = null;
export function toast(msg, ms = 2200) {
  const el = $('#toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), ms);
}
