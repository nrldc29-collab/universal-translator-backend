const CACHE_VERSION = 'v21-split-tts';
const CACHE_NAME = `universal-translator-shell-${CACHE_VERSION}`;
const RUNTIME_CACHE = `universal-translator-runtime-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline.html';
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/install.html',
  '/offline.html',
  '/manifest.json',
  '/icon.svg',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/maskable-512.png',
];
const CACHEABLE_DESTINATIONS = new Set(['document', 'style', 'font', 'image', 'manifest']);
const NEVER_CACHE_PATHS = [
  '/health',
  '/ready',
  '/diagnostics',
  '/metrics',
  '/analytics',
  '/auth/',
  '/translate/',
  '/vad',
  '/ws/',
  '/version',
];

function shouldBypass(requestUrl) {
  return NEVER_CACHE_PATHS.some((path) => requestUrl.pathname === path || requestUrl.pathname.startsWith(path));
}

function isShellAsset(requestUrl) {
  return (
    requestUrl.pathname.startsWith('/icons/') ||
    PRECACHE_URLS.includes(requestUrl.pathname)
  );
}

async function cacheDiscoveredShellAssets(cache) {
  try {
    const response = await fetch('/', { cache: 'reload' });
    if (!response.ok) return;
    await cache.put('/', response.clone());
    const html = await response.text();
    const discoveredUrls = [...html.matchAll(/\b(?:href|src)="([^"]+)"/g)]
      .map((match) => new URL(match[1], self.location.origin))
      .filter((url) => url.origin === self.location.origin)
      .filter((url) => !shouldBypass(url))
      .filter((url) => isShellAsset(url) || /\.(?:css|woff2?|png|svg|webp|ico)$/.test(url.pathname))
      .map((url) => url.pathname + url.search);
    await Promise.all([...new Set(discoveredUrls)].map((url) => cache.add(url).catch(() => {})));
  } catch {
    // Static fallback still keeps the installable shell available.
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      await cache.addAll(PRECACHE_URLS);
      await cacheDiscoveredShellAssets(cache);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => ![CACHE_NAME, RUNTIME_CACHE].includes(key)).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const requestUrl = new URL(event.request.url);
  if (requestUrl.origin !== self.location.origin || shouldBypass(requestUrl)) return;

  // Always go to network for the HTML shell + JS bundle so iOS picks up new builds.
  if (event.request.mode === 'navigate' || event.request.destination === 'script') {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' })
        .then((response) => {
          if (response.ok && event.request.destination === 'script') {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request).then((cached) => cached || caches.match(OFFLINE_URL)))
    );
    return;
  }

  if (!CACHEABLE_DESTINATIONS.has(event.request.destination) && !isShellAsset(requestUrl)) return;

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networkFetch = fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(RUNTIME_CACHE).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => cached || caches.match(OFFLINE_URL));
      return cached || networkFetch;
    })
  );
});
