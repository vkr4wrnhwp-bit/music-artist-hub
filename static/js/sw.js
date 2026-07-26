/* Street Banker service worker — conservative on purpose:
   static assets cache-first, pages always network (dashboards must
   never go stale), offline navigations get a friendly fallback. */
var VERSION = "sb-v10";
var PRECACHE = ["/static/offline.html", "/static/img/streetbanker-logo.svg",
                "/static/img/icon-192.png", "/static/manifest.json"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(PRECACHE); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(function () {
      return caches.match("/static/offline.html");
    }));
    return;
  }
  if (url.origin === location.origin && url.pathname.indexOf("/static/") === 0) {
    e.respondWith(caches.open(VERSION).then(function (c) {
      return c.match(e.request).then(function (hit) {
        return hit || fetch(e.request).then(function (resp) {
          if (resp.ok) c.put(e.request, resp.clone());
          return resp;
        });
      });
    }));
  }
});
