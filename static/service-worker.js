const CACHE_NAME = 'mant-v1';
const CORE_ASSETS = [
  '/offline.html',
  '/manifest.webmanifest',
  '/static/css/app.css',
  '/static/js/offline.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)))).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') {
    return;
  }

  const requestUrl = new URL(event.request.url);
  const isStatic = requestUrl.origin === self.location.origin && !requestUrl.pathname.startsWith('/api/') && !requestUrl.pathname.startsWith('/admin/') && !requestUrl.pathname.startsWith('/cuentas/recuperar') && !requestUrl.pathname.startsWith('/reportes/') && !requestUrl.pathname.includes('/download') && !requestUrl.pathname.includes('/pdf');

  if (!isStatic) {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) {
        return cached;
      }
      return fetch(event.request).then(response => {
        if (response && response.status === 200) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, copy));
        }
        return response;
      }).catch(() => caches.match('/offline.html') || Response.redirect('/offline.html'));
    })
  );
});
