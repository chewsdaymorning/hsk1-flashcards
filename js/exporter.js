// Stitch frames into a downloadable video via canvas + MediaRecorder.
import { getState } from './state.js';
import { $, blobToImage, drawContain, projectSize, sleep, toast } from './util.js';

function pickMime() {
  if (!('MediaRecorder' in window)) return null;
  const types = [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4',
  ];
  for (const t of types) {
    try { if (MediaRecorder.isTypeSupported(t)) return t; } catch { /* ignore */ }
  }
  return '';
}

export function setupExporter() {
  const modal = $('#exportModal');
  const bar = $('#exportBar');
  const status = $('#exportStatus');
  const result = $('#exportResult');
  const video = $('#resultVideo');
  const link = $('#downloadLink');

  let lastUrl = null;

  async function run() {
    const { frames, aspect, fps } = getState();
    if (!frames.length) { toast('Add some frames first'); return; }
    if (!('MediaRecorder' in window)) { toast('Video export not supported here'); return; }

    modal.classList.remove('hidden');
    result.classList.add('hidden');
    bar.style.width = '0%';
    status.textContent = 'Decoding frames…';
    if (lastUrl) { URL.revokeObjectURL(lastUrl); lastUrl = null; }

    const [w, h] = projectSize(aspect);
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');

    const bitmaps = await Promise.all(frames.map((f) => blobToImage(f.renderBlob)));

    const mime = pickMime();
    let stream;
    try { stream = canvas.captureStream(0); }
    catch { stream = canvas.captureStream(); }
    const track = stream.getVideoTracks()[0];

    const options = mime ? { mimeType: mime, videoBitsPerSecond: 8_000_000 } : undefined;
    let rec;
    try { rec = new MediaRecorder(stream, options); }
    catch { rec = new MediaRecorder(stream); }

    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    const stopped = new Promise((res) => { rec.onstop = res; });
    rec.start();

    const dur = 1000 / fps;
    for (let i = 0; i < bitmaps.length; i++) {
      drawContain(ctx, bitmaps[i], w, h);
      if (track.requestFrame) track.requestFrame();
      else if (stream.requestFrame) stream.requestFrame();
      status.textContent = `Rendering frame ${i + 1} / ${bitmaps.length}`;
      bar.style.width = Math.round(((i + 1) / bitmaps.length) * 100) + '%';
      await sleep(dur);
    }
    await sleep(Math.max(dur, 150)); // hold the final frame
    rec.stop();
    await stopped;

    const type = (mime && mime.split(';')[0]) || 'video/webm';
    const blob = new Blob(chunks, { type });
    lastUrl = URL.createObjectURL(blob);
    const ext = type.includes('mp4') ? 'mp4' : 'webm';

    video.src = lastUrl;
    link.href = lastUrl;
    link.download = `stop-motion-${Date.now()}.${ext}`;
    status.textContent = `Done — ${bitmaps.length} frames at ${fps} fps`;
    bar.style.width = '100%';
    result.classList.remove('hidden');
  }

  return { run };
}
