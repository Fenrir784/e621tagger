# PWA Documentation

This document provides comprehensive documentation of the Progressive Web App (PWA) implementation for e621tagger. It covers the service worker, manifest, and offline functionality.

---

## PWA Components

| Component | File | Purpose |
|-----------|------|---------|
| Service Worker | `templates/service-worker.js` | Offline caching, network request interception |
| SW Registration | `static/js/sw-init.js` | Service worker registration |
| Web Manifest | `static/manifest.json` | App metadata, icons, display |
| Install Script | (in index.html) | Install prompt handling |

---

## Service Worker

### File Location

`templates/service-worker.js`

### Version-Based Caching

```javascript
const CACHE_VERSION = '{{APP_VERSION}}';
const CACHE_NAME = `e621tagger-${CACHE_VERSION}`;
const STATIC_CACHE = `${CACHE_NAME}-static`;
```

The cache includes the application version for easy invalidation.

### Cached Resources

```javascript
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
```

**Total**: 32 cached resources

---

## Service Worker Life Cycle

### Install Event

```javascript
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});
```

**Behavior**:
1. Open cache named with version
2. Add all URLs to cache
3. Call `skipWaiting()` to activate immediately

### Activate Event

```javascript
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
```

**Behavior**:
1. Delete all old caches
2. Claim existing clients
3. Send `reload` message to all open windows

### Fetch Event

```javascript
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
```

### Request Strategies

| Request Type | Strategy | Behavior |
|-------------|----------|----------|
| Non-GET | Network | Always fetch |
| `/predict`, `/health` | Network | Always fetch |
| Navigation | Network-first with offline fallback | Try network, fallback to cache |
| Static assets | Cache-first | Try cache, fetch and cache |
| Other | Cache-first | Try cache, fetch and cache |

---

## SW Registration

### File Location

`static/js/sw-init.js`

### Registration Code

```javascript
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js').then(reg => {
            console.log('Service Worker registered:', reg);
        }).catch(err => {
            console.error('Service Worker registration failed:', err);
        });
    });

    navigator.serviceWorker.addEventListener('message', event => {
        if (event.data && event.data.action === 'reload') {
            window.location.reload();
        }
    });
}
```

**Behavior**:
1. Register service worker on page load
2. Log registration status
3. Listen for `reload` message from SW

---

## Web Manifest

### File Location

`static/manifest.json`

### Manifest Content

```json
{
  "name": "e621tagger",
  "short_name": "e621tagger",
  "description": "Free web-based e621 tagging app created for furries by furries.",
  "id": "/",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "display_override": ["window-controls-overlay", "standalone"],
  "orientation": "portrait",
  "theme_color": "#8b4aff",
  "background_color": "#0a0c10",
  "categories": ["utilities", "productivity", "multimedia"],
  "icons": [...],
  "screenshots": [...],
  "related_applications": [],
  "prefer_related_applications": false
}
```

### Manifest Fields

| Field | Value | Description |
|-------|-------|-------------|
| `name` | e621tagger | Full app name |
| `short_name` | e621tagger | Short name for home screen |
| `description` | ... | App description |
| `id` | / | Unique app identifier |
| `start_url` | / | Launch URL |
| `scope` | / | Navigation scope |
| `display` | standalone | Display as standalone app |
| `orientation` | portrait | Lock to portrait |
| `theme_color` | #8b4aff | App theme color |
| `background_color` | #0a0c10 | Splash screen background |

### Icons

| Size | File | Purpose |
|------|------|---------|
| 48x48 | maskable_icon_x48.png | Small icon |
| 72x72 | maskable_icon_x72.png | |
| 96x96 | maskable_icon_x96.png | Favicon |
| 128x128 | maskable_icon_x128.png | |
| 192x192 | maskable_icon_x192.png | App icon |
| 384x384 | maskable_icon_x384.png | |
| 512x512 | maskable_icon_x512.png | Large icon |
| 1024x1024 | maskable_icon.png | Store listing |

### Icon Purposes

```json
{
  "purpose": "any",
  "sizes": "1024x1024",
  "src": "/static/icons/maskable_icon.png",
  "type": "image/png"
}
```

| Purpose | Description |
|---------|-------------|
| `any` | Used at any size |
| `maskable` | Designed for masking (adaptive icons) |

### Screenshots

```json
"screenshots": [
  {
    "src": "/static/screenshots/desktop1.webp",
    "sizes": "1920x1080",
    "type": "image/webp",
    "form_factor": "wide",
    "label": "Desktop view 1"
  },
  {
    "src": "/static/screenshots/mobile1.webp",
    "sizes": "1080x1920",
    "type": "image/webp",
    "label": "Mobile view 1"
  }
]
```

---

## Display Modes

### Standalone

```json
"display": "standalone"
```

| Mode | Description |
|------|-------------|
| `standalone` | Full screen, no browser chrome |
| `fullscreen` | Full screen |
| `minimal-ui` | Minimal browser UI |
| `browser` | Normal browser tab |

---

## Installation

### Browser Prompts

Browsers show "Install" button when PWA criteria are met.

### HTML Integration

```html
<link rel="manifest" href="/static/manifest.json">
```

---

## Offline Functionality

### What's Cached

| Type | Available Offline |
|------|-----------------|
| App UI | Yes (returns cached `/`) |
| Static assets | Yes |
| /predict | No (network only) |
| /health | No (network only) |

### Offline Handling

1. **Navigation**: Return cached `/` if available
2. **Static**: Return cached or fetch-and-cache
3. **API**: Network only

### Notification

When offline navigation is served:

```javascript
client.postMessage({ action: 'offline' });
```

Frontend listens:

```javascript
navigator.serviceWorker.addEventListener('message', event => {
  if (event.data.action === 'offline') {
    // Show offline notification
  }
});
```

---

## Update Flow

```
1. New version deployed
         │
         ▼
2. Service worker updated
         │
         ▼
3. skipWaiting() called
         │
         ▼
4. New SW activates immediately
         │
         ▼
5. Old caches deleted
         │
         ▼
6. clients.claim() called
         │
         ▼
7. 'reload' message sent to windows
         │
         ▼
8. Page reloads
```

---

## Cache Invalidation

The cache is version-based:

- Cache name: `e621tagger-{VERSION}-static`
- Version changes on each deployment
- Old cache deleted on activation

---

## Browser Support

| Feature support | Chrome | Firefox | Safari | Edge |
|----------------|-------|---------|--------|-------|
| Service Worker | 40+ | 44+ | 15.2+ | 79+ |
| Web Manifest | 50+ | 75+ | 15.2+ | 79+ |
| Install Prompt | 60+ | - | 15.2+ | 79+ |

---

## Debugging

### Chrome DevTools

1. Open DevTools (F12)
2. Go to Application → Service Workers
3. Check status, update, unregister

### Check Cache

```
Application → Cache Storage → e621tagger-{version}-static
```

### Network Logs

```
Network → check /service-worker.js
```

---

## Testing

### Test Offline

1. Open app in Chrome
2. DevTools → Network → Offline
3. Reload page
4. Should show cached UI

### Test Update

1. Deploy new version
2. Visit app (old SW catches fetch)
3. New SW activates in background
4. Refresh page loads new version

---

## Lighthouse Audit

```bash
# Run PWA audit
lighthouse https://tagger.fenrir784.ru \
  --only-categories=pwa \
  --output=json \
  --output-path=pwa-report.json
```

### PWA Score Metrics

| Audit | Required |
|-------|----------|
| Registers SW | Yes |
| Has manifest | Yes |
| manifest.* properties | Yes |
| icons.* properties | Yes |
| Service Worker responds | Yes |
| start_url matches | Yes |

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  PWA Architecture                    │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Browser                               │  │
│  │                                                   │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │       sw-init.js                           │  │  │
│  │  │  - Register /service-worker.js            │  │  │
│  │  │  - Listen for 'reload' message            │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  │                      │                           │  │
│  │                      ▼                           │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │       Service Worker                        │  │  │
│  │  │                                          │  │  │
│  │  │  ┌───────────────────────────────────────┐  │  │  │
│  │  │  │  Install: Cache 32 resources        │  │  │  │
│  │  │  │  activate: Clean old caches         │  │  │  │
│  │  │  │  fetch: Cache-first + network      │  │  │  │
│  │  │  │  fetch: Network-first /predict   │  │  │  │
│  │  │  └───────────────────────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                              │
│                          ▼                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Cache Storage                         │  │
│  │  e621tagger-{version}-static                   │  │
│  │    ├── / (cached)                            │  │
│  │    ├── /static/css/style.css                 │  │
│  │    ├── /static/js/script.js                 │  │
│  │    └── ... (32 resources)                   │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## HTTP Caching Headers

### Service Worker Script

```python
# app.py
@app.route('/service-worker.js')
def service_worker():
    response = make_response(render_template('service-worker.js', ...))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
```

| Header | Value |
|--------|-------|
| Cache-Control | no-cache, no-store, must-revalidate |
| Pragma | no-cache |
| Expires | 0 |

**Purpose**: Prevent browser from caching SW, ensure SW cache is used.

### Static Assets

```python
@app.route('/static/<path:filename>')
def static_files(filename):
    response = make_response(send_from_directory('static', filename))
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response
```

| Header | Value |
|--------|-------|
| Cache-Control | public, max-age=86400 |

**Purpose**: Cache static assets for 24 hours (HTTP cache, not SW cache).

---

## Chrome Display Override

```json
"display_override": ["window-controls-overlay", "standalone"]
```

Enables Windows window controls on desktop.

---

## Integration Checklist

- [x] `/service-worker.js` endpoint in Flask
- [x] Cache version based on `APP_VERSION`
- [x] 32 resources cached
- [x] Network-first for navigation
- [x] Cache-first for static assets
- [x] Clean old caches on update
- [x] Reload message on update
- [x] Offline fallback for navigation
- [x] `/static/manifest.json` for PWA
- [x] Icons in multiple sizes
- [x] Screenshots for store listing
- [x] Proper theme colors
- [x] Standalone display mode