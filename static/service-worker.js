const CACHE_NAME = 'e621tagger-v1';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/script.js',
  '/static/manifest.json',
  '/static/android-chrome-192x192.png',
  '/static/android-chrome-512x512.png',
  '/static/favicon.ico',
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
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});