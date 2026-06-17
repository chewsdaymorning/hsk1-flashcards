# 🎬 Stop Motion Studio

A no-install, browser-based stop motion camera. Shoot frames with your phone or
laptop camera, line up each shot against the previous one with onion skinning,
edit and reorder frames, then stitch everything into a video at the speed you
choose.

## Features

- **Capture** frames directly from your device camera (front/back toggle).
- **Aspect ratio** picker — 1:1, 4:5, 9:16, 16:9, 4:3, 3:4. Frames are
  center-cropped to match.
- **Background** picker — shoot against the live **Camera**, or swap to a plain
  **White** or **Black** backdrop. Perfect for cut-out / sticker animation and
  for keying the subject out cleanly afterwards.
- **Stickers** — tap 🌟 Stickers to drop emoji onto the scene, then drag to
  move, use the corner handles to resize and rotate, and ✕ to delete. Stickers
  are baked into every captured frame, so you can reposition them between shots
  for cut-out style animation.
- **Onion skin** — the previous frame is overlaid on the live camera at an
  adjustable opacity so you can align your next shot.
- **Filmstrip** of every frame with:
  - **Reorder** by dragging frames left/right.
  - **Duplicate** a frame (hold a pose longer).
  - **Delete** unwanted frames.
  - **Edit** each frame individually — **crop & rotate**.
- **Custom speed** — set playback from 1 to 30 fps.
- **Preview** the animation in-app, with optional looping.
- **Export** the finished animation as a downloadable video (WebM, or MP4 where
  the browser supports it). Frames are auto-stitched together.
- **Auto-save** — frames and settings are stored in the browser (IndexedDB), so
  a refresh won't lose your work.

## Run it

It's a static site — no build step, no dependencies. Serve the folder over HTTP
(camera access requires a secure context: `https://` or `localhost`):

```bash
# from the project root
python3 -m http.server 8000
# then open http://localhost:8000 on your computer,
# or use your machine's LAN IP over https to test on a phone.
```

Then grant camera permission when prompted.

> Note: browsers only allow camera access on `localhost` or over HTTPS. On a
> phone you'll need to serve over HTTPS (e.g. via a tunnel) for the camera to
> work.

## How it's built

Vanilla JavaScript ES modules, no framework:

| File | Responsibility |
|------|----------------|
| `index.html` / `styles.css` | Layout and styling |
| `js/app.js` | Wires everything together, controls, keyboard shortcuts |
| `js/camera.js` | `getUserMedia`, camera flip, aspect-cropped capture |
| `js/state.js` | App state, mutations, change events |
| `js/db.js` | IndexedDB persistence of frames + settings |
| `js/filmstrip.js` | Thumbnails, per-frame actions, drag-to-reorder |
| `js/editor.js` | Per-frame crop & rotate editor |
| `js/playback.js` | In-app preview player |
| `js/exporter.js` | Canvas + `MediaRecorder` video export |
| `js/util.js` | Aspect math, image baking, shared helpers |

## Tips

- Press **Space** (or **Enter**) to capture a frame on desktop.
- Lower the **onion skin** opacity if it's hard to see your subject; raise it to
  line up fine movements.
- **Duplicate** a frame to make a moment linger without re-shooting it.
