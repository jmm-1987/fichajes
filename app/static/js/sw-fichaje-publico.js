const CACHE_VERSION = "fichaje-publico-v1";
const OFFLINE_URL = "/fichaje-publico/";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      return cache.addAll([
        "/fichaje-publico/",
        "/fichaje-publico/sesion",
        "/static/css/app.css",
        "/static/img/logo-jm.png",
      ]);
    }),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  const sameOrigin = url.origin === self.location.origin;

  if (!sameOrigin) return;

  const esDocumento = event.request.mode === "navigate";
  if (esDocumento) {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          const copia = resp.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, copia));
          return resp;
        })
        .catch(() => caches.match(event.request).then((r) => r || caches.match(OFFLINE_URL))),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((resp) => {
        const copia = resp.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, copia));
        return resp;
      });
    }),
  );
});
