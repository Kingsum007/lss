const CACHE = 'lss-shell-v1';
const ASSETS = ['/', '/index.html', '/styles.css', '/app.js', '/manifest.webmanifest', '/icon.svg', '/lib/encoding.js', '/lib/crypto.js', '/lib/store.js', '/lib/policy.js', '/lib/engine.js'];
const ALLOWED = new Set(ASSETS);
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('lss-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.search || !ALLOWED.has(url.pathname)) return;
  // Only the fixed application shell is cached. API responses and records never enter Cache Storage.
  event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
});
