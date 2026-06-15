// Lightweight IndexedDB wrapper for persisting frames + project settings.
// Frames are stored as Blobs so a page refresh doesn't lose your work.

const DB_NAME = 'stop-motion-studio';
const DB_VERSION = 1;
const FRAMES = 'frames';
const META = 'meta';

let dbPromise = null;

function open() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    if (!('indexedDB' in window)) return reject(new Error('IndexedDB unavailable'));
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(FRAMES)) {
        db.createObjectStore(FRAMES, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(META)) {
        db.createObjectStore(META, { keyPath: 'key' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function tx(store, mode) {
  return open().then((db) => db.transaction(store, mode).objectStore(store));
}

function reqToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export const db = {
  async available() {
    try { await open(); return true; } catch { return false; }
  },

  async putFrame(record) {
    const store = await tx(FRAMES, 'readwrite');
    return reqToPromise(store.put(record));
  },

  async deleteFrame(id) {
    const store = await tx(FRAMES, 'readwrite');
    return reqToPromise(store.delete(id));
  },

  async getAllFrames() {
    const store = await tx(FRAMES, 'readonly');
    return reqToPromise(store.getAll());
  },

  async clearFrames() {
    const store = await tx(FRAMES, 'readwrite');
    return reqToPromise(store.clear());
  },

  async setMeta(key, value) {
    const store = await tx(META, 'readwrite');
    return reqToPromise(store.put({ key, value }));
  },

  async getMeta(key) {
    const store = await tx(META, 'readonly');
    const rec = await reqToPromise(store.get(key));
    return rec ? rec.value : undefined;
  },
};
