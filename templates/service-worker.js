const CACHE_VERSION = '{{APP_VERSION}}';
const CACHE_NAME = `e621tagger-${CACHE_VERSION}`;
const STATIC_CACHE = `${CACHE_NAME}-static`;

const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/js/hammer.min.js',
  '/static/js/sw-init.js',
  '/static/manifest.json',
  '/static/icons/favicon.svg',
  '/static/icons/favicon.ico',
  '/static/icons/apple-touch-icon.png',
  '/static/icons/favicon-96x96.png',
  '/static/icons/favicon-32x32.png',
  '/static/icons/favicon-16x16.png',
  '/static/icons/maskable_icon.png',
  '/static/icons/maskable_icon_x512.png',
  '/static/icons/maskable_icon_x384.png',
  '/static/icons/maskable_icon_x192.png',
  '/static/icons/maskable_icon_x128.png',
  '/static/icons/maskable_icon_x96.png',
  '/static/icons/maskable_icon_x72.png',
  '/static/icons/maskable_icon_x48.png',
  '/static/icons/egg/egg_top.png',
  '/static/icons/egg/egg_bottom.png',
  '/static/icons/egg/f1.png',
  '/static/icons/egg/f2.png',
  '/static/icons/egg/f3.png',
  '/static/icons/egg/f4.png',
  '/static/icons/egg/f5.png',
  '/static/icons/egg/f6.png',
  '/static/icons/egg/f7.png',
  '/static/icons/egg/f8.png',
  '/static/icons/egg/f9.png'
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

  if (url.pathname === '/predict' || url.pathname === '/health') {
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
            const responseToCache = networkResponse.clone();
            caches.open(STATIC_CACHE).then(cache => {
              cache.put(event.request, responseToCache);
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
          const responseToCache = networkResponse.clone();
          caches.open(STATIC_CACHE).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      });
    })
  );
});
