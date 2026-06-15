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

// Capture the current video frame, center-cropped to `aspect`, at project size.
export async function capture(video, aspect) {
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

  const [ow, oh] = projectSize(aspect);
  const canvas = document.createElement('canvas');
  canvas.width = ow; canvas.height = oh;
  canvas.getContext('2d').drawImage(video, sx, sy, sw, sh, 0, 0, ow, oh);
  return canvasToBlob(canvas, 'image/jpeg', 0.92);
}
