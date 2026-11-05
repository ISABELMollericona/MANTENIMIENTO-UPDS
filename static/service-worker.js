// v2: las páginas HTML van primero a la red. La versión anterior (cache-first)
// servía páginas viejas con tokens CSRF caducados (403 al iniciar sesión o guardar
// formularios), datos desactualizados e incluso páginas de otro usuario.
const STATIC_CACHE = 'mant-static-v2';
const PAGES_CACHE = 'mant-pages-v2';
const OFFLINE_URL = '/offline.html';
const CORE_ASSETS = [
  OFFLINE_URL,
  '/manifest.webmanifest',
  '/static/css/app.css',
  '/static/js/offline.js',
];

// Nunca se guardan en caché: autenticación, API, admin, reportes y descargas.
const NO_CACHE_PREFIXES = ['/api/', '/admin/', '/cuentas/', '/reportes/', '/service-worker.js'];
// Al entrar o salir de la sesión se borra la caché de páginas del usuario anterior.
const SESSION_RESET_PREFIXES = ['/cuentas/ingresar', '/cuentas/salir'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(CORE_ASSETS))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  const keep = [STATIC_CACHE, PAGES_CACHE];
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => !keep.includes(key)).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

function startsWithAny(pathname, prefixes) {
  return prefixes.some(prefix => pathname.startsWith(prefix));
}

function offlineFallback() {
  return caches.match(OFFLINE_URL).then(cached => cached || new Response(
    '<h1>Sin conexión</h1><p>Vuelve a intentarlo cuando tengas conexión.</p>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  ));
}

// Páginas: red primero; la copia guardada solo se usa sin conexión.
function networkFirstPage(request) {
  return fetch(request)
    .then(response => {
      if (response && response.status === 200 && !response.redirected && response.type === 'basic') {
        const copy = response.clone();
        caches.open(PAGES_CACHE).then(cache => cache.put(request, copy));
      }
      return response;
    })
    .catch(() => caches.match(request, { cacheName: PAGES_CACHE }).then(cached => cached || offlineFallback()));
}

// Archivos estáticos: responde con la caché y la actualiza en segundo plano.
function staleWhileRevalidate(request) {
  return caches.open(STATIC_CACHE).then(cache => cache.match(request).then(cached => {
    const network = fetch(request)
      .then(response => {
        if (response && response.status === 200) {
          cache.put(request, response.clone());
        }
        return response;
      })
      .catch(() => cached);
    return cached || network;
  }));
}

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (startsWithAny(url.pathname, SESSION_RESET_PREFIXES)) {
    event.waitUntil(caches.delete(PAGES_CACHE));
  }
  if (startsWithAny(url.pathname, NO_CACHE_PREFIXES) || url.pathname.includes('/download') || url.pathname.includes('/pdf')) {
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest' || url.pathname === OFFLINE_URL) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  const acceptsHtml = request.mode === 'navigate' || (request.headers.get('accept') || '').includes('text/html');
  if (acceptsHtml) {
    event.respondWith(networkFirstPage(request));
  }
});
