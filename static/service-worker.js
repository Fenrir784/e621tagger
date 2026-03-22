const CACHE_VERSION = 'v2';
const CACHE_NAME = `e621tagger-${CACHE_VERSION}`;
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/apple-touch-icon.png',
  '/static/favicon-32x32.png',
  '/static/favicon-16x16.png',
  '/static/favicon.ico',
  '/static/manifest.json',
  '/static/f1.png',
  '/static/f2.png',
  '/static/f3.png',
  '/static/f4.png',
  '/static/f5.png',
  '/static/f6.png',
  '/static/f7.png',
  '/static/f8.png',
  '/static/f9.png',
  '/static/egg_top.png',
  '/static/egg_bottom.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => {
      return clients.claim();
    }).then(() => {
      clients.matchAll({ type: 'window' }).then(clients => {
        clients.forEach(client => {
          client.postMessage({ action: 'reload' });
        });
      });
    })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
