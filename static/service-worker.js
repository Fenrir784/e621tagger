const CACHE_VERSION = 'v13';
const CACHE_NAME = `e621tagger-${CACHE_VERSION}`;
const STATIC_CACHE = `${CACHE_NAME}-static`;

const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/js/hammer.min.js',
  '/static/manifest.json',
  '/static/android-chrome-192x192.png',
  '/static/android-chrome-512x512.png',
  '/static/favicon.ico',
  '/static/apple-touch-icon.png',
  '/static/favicon-32x32.png',
  '/static/favicon-16x16.png',
  '/static/egg_top.png',
  '/static/egg_bottom.png',
  '/static/f1.png',
  '/static/f2.png',
  '/static/f3.png',
  '/static/f4.png',
  '/static/f5.png',
  '/static/f6.png',
  '/static/f7.png',
  '/static/f8.png',
  '/static/f9.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== STATIC_CACHE) {
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
  const url = new URL(event.request.url);
  const isStatic = url.pathname.startsWith('/static/') ||
                   url.pathname === '/favicon.ico' ||
                   url.pathname === '/manifest.json';

  if (event.request.method !== 'GET') {
    event.respondWith(fetch(event.request));
    return;
  }

  if (url.pathname === '/predict') {
    event.respondWith(fetch(event.request));
    return;
  }

  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(async () => {
        const cache = await caches.open(STATIC_CACHE);
        const cachedResponse = await cache.match('/');
        if (cachedResponse) {
          const clientsList = await clients.matchAll({ type: 'window' });
          clientsList.forEach(client => {
            client.postMessage({ action: 'offline' });
          });
          return cachedResponse;
        }
        return new Response('Offline: unable to load page', { status: 503 });
      })
    );
    return;
  }

  if (isStatic) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(STATIC_CACHE).then(cache => {
              cache.put(event.request, networkResponse.clone());
            });
          }
          return networkResponse;
        }).catch(() => null);
        return cached || fetchPromise;
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(networkResponse => {
        if (networkResponse && networkResponse.status === 200) {
          caches.open(STATIC_CACHE).then(cache => {
            cache.put(event.request, networkResponse.clone());
          });
        }
        return networkResponse;
      });
    })
  );
});
