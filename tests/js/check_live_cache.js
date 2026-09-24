/* The Live performance page keeps its set in this browser.
 *
 * static/js/live-perform-cache.js is the wiring between the performance page
 * and the engine bundle's own cache store. Run here against the bundle's
 * MemoryCacheStore, which has the same put/get/delete/listPaths contract as
 * the IndexedDbCacheStore the page opens, with a network that can be switched
 * off. The question each check answers is the one a venue asks: with no
 * internet, does the set still open and does every stem still load?
 *
 *     node tests/js/check_live_cache.js
 */
"use strict";

const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "..", "static", "js");
const scope = {};
const SB = new Function(
  "globalThis", "window", "self", "navigator", "document",
  fs.readFileSync(path.join(root, "livelab.js"), "utf8") + "; return globalThis.SBLive;"
)(scope, scope, scope, {}, {});
const cacheScope = {};
new Function("window", "globalThis",
  fs.readFileSync(path.join(root, "live-perform-cache.js"), "utf8")
)(cacheScope, cacheScope);
const C = cacheScope.SBLivePerformCache;

let passed = 0;
let failed = 0;
const pending = [];

function check(label, fn) {
  pending.push(Promise.resolve().then(fn).then(() => {
    console.log("PASS  " + label);
    passed++;
  }, (err) => {
    console.log("FAIL  " + label + "  -> " + String(err && err.message).split("\n")[0]);
    failed++;
  }));
}

function assert(cond, message) { if (!cond) throw new Error(message); }

const MANIFEST = {project: {id: "set-1"}, assets: {a: "/live/stem/a", b: "/live/stem/b"}};
const BYTES = {"/live/stem/a": [1, 2, 3, 4], "/live/stem/b": [9, 8, 7]};

/* A network that answers until it is switched off, and counts what it served. */
function network() {
  const net = {online: true, served: 0};
  net.fetchJson = () => net.online
    ? Promise.resolve(JSON.parse(JSON.stringify(MANIFEST)))
    : Promise.reject(new Error("offline"));
  net.fetchBytes = (url) => {
    if (!net.online) return Promise.reject(new Error("offline"));
    net.served++;
    return Promise.resolve(new Uint8Array(BYTES[url]).buffer);
  };
  return net;
}

/* The engine's side: what it was handed, per asset. */
function engine() {
  const got = {};
  return {got, load: (id, buffer) => { got[id] = Array.from(new Uint8Array(buffer)); return Promise.resolve(); }};
}

function open(store, net, eng) {
  return C.loadManifest(store, net.fetchJson).then((res) => {
    const ids = Object.keys(res.manifest.assets);
    return C.loadStems({ids, urls: res.manifest.assets, store,
                        fetchBytes: net.fetchBytes, load: eng.load})
      .then((tally) => ({from: res.from, tally}));
  });
}

check("the bundle still carries the cache store the page opens", () => {
  assert(SB.cache && SB.cache.IndexedDbCacheStore && SB.cache.MemoryCacheStore,
         "SBLive.cache stores missing");
});

check("first open, online: everything is downloaded and kept", async () => {
  const store = new SB.cache.MemoryCacheStore();
  const net = network(); const eng = engine();
  const out = await open(store, net, eng);
  assert(out.from === "network", "manifest came from " + out.from);
  assert(out.tally.downloaded === 2 && out.tally.kept === 0, JSON.stringify(out.tally));
  assert(await store.exists(C.MANIFEST_KEY), "manifest not kept");
  assert(await store.exists(C.stemKey("a")) && await store.exists(C.stemKey("b")), "stems not kept");
  assert(JSON.stringify(eng.got.a) === "[1,2,3,4]", "engine got " + eng.got.a);
});

check("reload with no internet: the set opens and every stem loads from this computer", async () => {
  const store = new SB.cache.MemoryCacheStore();
  const net = network();
  await open(store, net, engine());
  net.online = false;
  const served = net.served;
  const eng = engine();
  const out = await open(store, net, eng);
  assert(out.from === "this computer", "manifest came from " + out.from);
  assert(out.tally.kept === 2 && out.tally.failed === 0, JSON.stringify(out.tally));
  assert(net.served === served, "the network was asked again");
  assert(JSON.stringify(eng.got.b) === "[9,8,7]", "engine got " + eng.got.b);
});

check("reload online: kept stems are not downloaded again", async () => {
  const store = new SB.cache.MemoryCacheStore();
  const net = network();
  await open(store, net, engine());
  const served = net.served;
  const out = await open(store, net, engine());
  assert(out.tally.kept === 2 && net.served === served, JSON.stringify(out.tally));
});

check("never opened online: with no internet it says so rather than playing silence", async () => {
  const store = new SB.cache.MemoryCacheStore();
  const net = network(); net.online = false;
  let refused = false;
  try { await open(store, net, engine()); } catch (e) { refused = true; }
  assert(refused, "an empty store with no network still claimed a set");
});

check("a browser that refuses the space still plays, and counts what was not kept", async () => {
  const store = new SB.cache.MemoryCacheStore();
  store.put = () => Promise.reject(new Error("QuotaExceededError"));
  const net = network(); const eng = engine();
  const out = await open(store, net, eng);
  assert(out.tally.downloaded === 2 && out.tally.notKept === 2, JSON.stringify(out.tally));
  assert(eng.got.a && eng.got.b, "stems were not handed to the engine");
});

check("no store at all (no IndexedDB): the network path still works", async () => {
  const net = network(); const eng = engine();
  const out = await open(null, net, eng);
  assert(out.tally.downloaded === 2 && out.from === "network", JSON.stringify(out));
});

check("a kept copy the engine cannot decode is fetched again", async () => {
  const store = new SB.cache.MemoryCacheStore();
  await store.put(C.stemKey("a"), new Uint8Array([0]));
  const net = network();
  let first = true;
  const eng = {got: {}, load: (id, buffer) => {
    const bytes = Array.from(new Uint8Array(buffer));
    if (id === "a" && first && bytes.length === 1) { first = false; return Promise.reject(new Error("decode")); }
    eng.got[id] = bytes; return Promise.resolve();
  }};
  const out = await open(store, net, eng);
  assert(JSON.stringify(eng.got.a) === "[1,2,3,4]", "engine got " + eng.got.a);
  assert(out.tally.failed === 0, JSON.stringify(out.tally));
});

check("stems that left the set are removed; the manifest stays", async () => {
  const store = new SB.cache.MemoryCacheStore();
  await open(store, network(), engine());
  await store.put(C.stemKey("gone"), new Uint8Array([5]));
  const removed = await C.prune(store, ["a", "b"]);
  const paths = (await store.listPaths()).sort();
  assert(removed === 1, "removed " + removed);
  assert(JSON.stringify(paths) === JSON.stringify([C.MANIFEST_KEY, "stems/a", "stems/b"].sort()),
         "left " + paths);
});

Promise.all(pending).then(() => {
  console.log("\n" + passed + " passed, " + failed + " failed");
  process.exit(failed ? 1 : 0);
});
