// Camera capture: live stream, front/back toggle, aspect-cropped capture.
import { ASPECTS, projectSize, canvasToBlob } from './util.js';

let stream = null;
let facing = 'environment';

export function isActive() { return !!stream; }

export async function startCamera(video) {
  stopCamera();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error('Camera API not supported in this browser.');
  }
  stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
    audio: false,
  });
  video.srcObject = stream;
  try { await video.play(); } catch { /* autoplay quirks */ }
  return true;
}

export function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
}

export async function flipCamera(video) {
  facing = facing === 'environment' ? 'user' : 'environment';
  return startCamera(video);
}

// Capture a frame at project size, center-cropped to `aspect`.
// opts: { aspect, background: 'camera'|'white'|'black', stickers: [] }
// With a 'white'/'black' background the camera feed is replaced by a solid
// backdrop — handy for cut-out / sticker animation that's easy to key out later.
export async function capture(video, opts = {}) {
  const { aspect = '1:1', background = 'camera', stickers = [] } = opts;
  const [ow, oh] = projectSize(aspect);
  const canvas = document.createElement('canvas');
  canvas.width = ow; canvas.height = oh;
  const ctx = canvas.getContext('2d');

  if (background === 'white' || background === 'black') {
    ctx.fillStyle = background === 'white' ? '#ffffff' : '#000000';
    ctx.fillRect(0, 0, ow, oh);
  } else {
    const vw = video.videoWidth, vh = video.videoHeight;
    if (!vw || !vh) throw new Error('Camera not ready yet.');

    const [aw, ah] = ASPECTS[aspect] || ASPECTS['1:1'];
    const targetRatio = aw / ah;
    const videoRatio = vw / vh;

    let sx, sy, sw, sh;
    if (videoRatio > targetRatio) {
      sh = vh; sw = vh * targetRatio; sx = (vw - sw) / 2; sy = 0;
    } else {
      sw = vw; sh = vw / targetRatio; sx = 0; sy = (vh - sh) / 2;
    }
    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, ow, oh);
  }

  drawStickers(ctx, stickers, ow, oh);
  return canvasToBlob(canvas, 'image/jpeg', 0.92);
}

// Bake stickers into the canvas. Sticker x/y/size are fractions of the stage,
// which maps 1:1 onto the output canvas, so they translate directly.
function drawStickers(ctx, stickers, w, h) {
  for (const s of stickers) {
    const fs = (s.size || 0.2) * h;
    ctx.save();
    ctx.translate(s.x * w, s.y * h);
    ctx.rotate(((s.rotation || 0) * Math.PI) / 180);
    ctx.font = `${fs}px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(s.emoji, 0, 0);
    ctx.restore();
  }
}
