/* Street Banker service worker — conservative on purpose:
   static assets cache-first, pages always network (dashboards must
   never go stale), offline navigations get a friendly fallback.

   A navigation is only called offline after a second attempt fails:
   one rejected fetch is a blip, a cold start or a backgrounded tab, and
   answering it with "You're offline" states something about the reader's
   machine that we have not checked. The fallback page checks
   navigator.onLine itself and words itself accordingly.

   One exception, for the road: TOUR's Tour Home, My Day and Show Command
   pages are network-first with a cached fallback, so a schedule that was
   open an hour ago still opens in a venue basement with no signal. The
   copy is per-URL - query string included, because Show Command tabs and
   My Day dates live in the query - is whatever the server last sent that
   signed-in person, and is replaced on every successful load. */
var VERSION = "sb-v216";   /* Artist Pulse 500 on an unmeasured reading, and audio transports that started against a clock that had not started - both shipped a script the cached page would otherwise keep */
var PAGES = VERSION + "-tour";
var PRECACHE = ["/static/offline.html", "/static/img/streetbanker-logo.svg",
                "/static/img/icon-192.png", "/static/manifest.json"];
var TOUR_PAGE = /^\/tours\/[a-f0-9]{32}(\/my-day|\/shows\/[a-f0-9]{32})?$/;

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(VERSION).then(function (c) { return c.addAll(PRECACHE); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== VERSION && k !== PAGES; })
      .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

function retryThenFallback(request) {
  /* One more go before we tell somebody their connection is gone. A
     request that failed because the tab was backgrounded, or because the
     server was still waking, usually succeeds on the second ask. Only a
     second failure reaches the fallback page - which then decides for
     itself whether "offline" is a true word for what happened. */
  return fetch(request).catch(function () {
    return caches.match("/static/offline.html");
  });
}

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);
  if (e.request.mode === "navigate") {
    if (url.origin === location.origin && TOUR_PAGE.test(url.pathname)) {
      e.respondWith(fetch(e.request).then(function (resp) {
        if (resp.ok) {
          var copy = resp.clone();
          caches.open(PAGES).then(function (c) { c.put(e.request, copy); });
        }
        return resp;
      }).catch(function () {
        return caches.open(PAGES).then(function (c) { return c.match(e.request); })
          .then(function (hit) { return hit || retryThenFallback(e.request); });
      }));
      return;
    }
    e.respondWith(fetch(e.request).catch(function () {
      return retryThenFallback(e.request);
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
