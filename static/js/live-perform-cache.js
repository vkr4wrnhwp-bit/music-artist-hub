/* Live: keep a set in this browser, so a reload at the venue does not need
 * the internet.
 *
 * The engine bundle (livelab.js) has carried a cache module all along -
 * SBLive.cache.IndexedDbCacheStore - and the performance page never used it:
 * every open fetched every stem again, so a reload in a venue with no signal
 * was the end of the show, whatever the Live page said (overclaims list,
 * 2026-09-11, item 14). This is the wiring, kept out of the page so Node can
 * run it against the bundle's MemoryCacheStore (tests/js/check_live_cache.js).
 *
 *   loadManifest   network first, because the set may have changed since it
 *                  was last opened; a good answer is kept, and with no
 *                  network the kept copy is used instead.
 *   loadStems      this computer first, because a stem's bytes never change
 *                  under its id (a stem points at one Vault file for life);
 *                  anything not kept yet is downloaded and then kept.
 *   prune          stems that left the set are removed from the store, so
 *                  it holds this set and nothing else.
 *
 * The page itself is kept by the service worker (static/js/sw.js,
 * LIVE_PERFORM). Stems are the artist's masters taken apart: they are kept
 * only in this browser's own storage for this site, and clearing the site's
 * data removes them.
 */
(function (root) {
  "use strict";

  var MANIFEST_KEY = "manifest.json";

  function stemKey(assetId) { return "stems/" + assetId; }

  function toArrayBuffer(bytes) {
    // The store hands back a Uint8Array that may be a view on a larger
    // buffer; the engine wants exactly these bytes as an ArrayBuffer.
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  }

  function encodeJson(value) {
    return new TextEncoder().encode(JSON.stringify(value));
  }

  function decodeJson(bytes) {
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  /* fetchJson() resolves to the manifest or rejects. Resolves to
     {manifest, from: "network" | "this computer"}; rejects only when there is
     neither a network answer nor a kept copy. */
  function loadManifest(store, fetchJson) {
    return fetchJson().then(function (manifest) {
      if (!store) { return {manifest: manifest, from: "network"}; }
      return store.put(MANIFEST_KEY, encodeJson(manifest))
        .catch(function () { /* not kept this time; still playable */ })
        .then(function () { return {manifest: manifest, from: "network"}; });
    }, function (err) {
      if (!store) { throw err; }
      return store.get(MANIFEST_KEY).then(function (bytes) {
        if (!bytes) { throw err; }
        return {manifest: decodeJson(bytes), from: "this computer"};
      }, function () { throw err; });
    });
  }

  /* opts:
       ids         asset ids to load
       urls        {assetId: url}
       store       a cache store, or null when this browser has none
       fetchBytes  function (url) -> Promise<ArrayBuffer>
       load        function (assetId, ArrayBuffer) -> Promise (the engine)
     Resolves to {kept, downloaded, failed, notKept}: kept = loaded from this
     computer, downloaded = fetched now, notKept = fetched but could not be
     stored (the browser refused the space), failed = not loaded at all. */
  function loadStems(opts) {
    var tally = {kept: 0, downloaded: 0, failed: 0, notKept: 0};
    var store = opts.store;

    function fromNetwork(assetId) {
      return opts.fetchBytes(opts.urls[assetId]).then(function (buffer) {
        var copy = new Uint8Array(buffer.slice(0));
        var keep = store
          ? store.put(stemKey(assetId), copy).then(
              function () { return true; }, function () { return false; })
          : Promise.resolve(false);
        return keep.then(function (ok) {
          if (!ok) { tally.notKept++; }
          return opts.load(assetId, buffer);
        }).then(function () { tally.downloaded++; });
      });
    }

    function one(assetId) {
      var cached = store
        ? store.get(stemKey(assetId)).catch(function () { return null; })
        : Promise.resolve(null);
      return cached.then(function (bytes) {
        if (!bytes || !bytes.length) { return fromNetwork(assetId); }
        return Promise.resolve(opts.load(assetId, toArrayBuffer(bytes)))
          .then(function () { tally.kept++; }, function () {
            // A kept copy that no longer decodes is thrown away and fetched
            // again, rather than leaving a silent pad for the rest of the show.
            var drop = store.delete(stemKey(assetId)).catch(function () {});
            return drop.then(function () { return fromNetwork(assetId); });
          });
      }).catch(function () { tally.failed++; });
    }

    return Promise.all((opts.ids || []).map(one)).then(function () { return tally; });
  }

  function prune(store, keepIds) {
    if (!store) { return Promise.resolve(0); }
    var keep = {};
    keep[MANIFEST_KEY] = true;
    (keepIds || []).forEach(function (id) { keep[stemKey(id)] = true; });
    return store.listPaths().then(function (paths) {
      var gone = paths.filter(function (p) { return !keep[p]; });
      return Promise.all(gone.map(function (p) { return store.delete(p); }))
        .then(function () { return gone.length; });
    }).catch(function () { return 0; });
  }

  root.SBLivePerformCache = {
    MANIFEST_KEY: MANIFEST_KEY,
    stemKey: stemKey,
    loadManifest: loadManifest,
    loadStems: loadStems,
    prune: prune
  };
})(typeof window !== "undefined" ? window : globalThis);
