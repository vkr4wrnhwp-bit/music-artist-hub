import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { sanitiseFilename, buildStorageKey, resolveWithinRoot } from "@/lib/storage-key";

/**
 * Two questions: what key does an uploaded file get, and is a key allowed to
 * be read. They were answered by two different rules that disagreed, so an
 * ordinary filename could produce a key the reader refused.
 */

const ROOT = "/var/canvas/.storage";
const CHECKSUM = "2d711642b726b04400ff0011aabbccddeeff00112233445566778899aabbccdd";
const key = (name: string) => buildStorageKey("org_abc", CHECKSUM, name);

/* ---------------- put and get agree ---------------- */

test("a file that uploads can be read back", () => {
  // "rev..2.step" is an ordinary revision filename. The sanitiser kept dots,
  // so the key contained ".." and get() rejected any key containing "..".
  // The upload reported success and the file was unreadable forever.
  for (const name of ["rev..2.step", "bracket.v1..old.pdf", "..hidden.step", "normal.step", "a...b...c.dxf"]) {
    const k = key(name);
    assert.ok(resolveWithinRoot(ROOT, k), `${name} produced a key its own reader refuses: ${k}`);
  }
});

test("every key a filename can produce is readable", () => {
  const nasty = [
    "../../etc/passwd",
    "..\\..\\windows\\system32",
    "....//....//etc/shadow",
    "a b c.step",
    "naive-part.STEP",
    "%2e%2e%2fpasswd",
    "part .step",
    ".",
    "..",
    "...",
    String.fromCharCode(10, 10) + ".step",
    "/absolute/path.step",
  ];
  for (const name of nasty) {
    const k = key(name);
    assert.ok(resolveWithinRoot(ROOT, k), `${JSON.stringify(name)} produced an unreadable key: ${k}`);
  }
});

test("a sanitised filename never contains a traversal sequence", () => {
  for (const name of ["../../etc/passwd", "a..b", "....", "..", "x/../../y"]) {
    assert.ok(!sanitiseFilename(name).includes(".."), `${name} -> ${sanitiseFilename(name)}`);
  }
});

test("a sanitised filename is never empty and never hidden", () => {
  for (const name of ["", ".", "..", "...", "///", " "]) {
    const s = sanitiseFilename(name);
    assert.ok(s.length > 0, `${JSON.stringify(name)} sanitised to nothing`);
    assert.ok(!s.startsWith("."), `${JSON.stringify(name)} -> ${s} is a hidden file`);
  }
});

test("the organisation is part of every key", () => {
  // A leaked key from one shop must not be guessable into another's namespace.
  assert.ok(key("part.step").startsWith("org_abc/"));
  assert.ok(buildStorageKey("other_org", CHECKSUM, "part.step").startsWith("other_org/"));
  assert.notEqual(key("part.step"), buildStorageKey("other_org", CHECKSUM, "part.step"));
});

test("the same bytes and name give the same key, different bytes do not", () => {
  assert.equal(key("part.step"), key("part.step"));
  assert.notEqual(key("part.step"), buildStorageKey("org_abc", "ffffffff" + CHECKSUM.slice(8), "part.step"));
});

/* ---------------- containment is resolved, not pattern-matched ---------------- */

test("a key that climbs out of the root is refused", () => {
  // The old check was `storageKey.includes("..")` — a blacklist standing
  // between the application and an arbitrary file read. path.join of the root
  // with "a/../../../etc/passwd" resolves outside it.
  for (const k of ["../etc/passwd", "a/../../../etc/passwd", "org/../../../../../../etc/shadow", "./../../secrets"]) {
    assert.equal(resolveWithinRoot(ROOT, k), null, `${k} escaped the root`);
  }
});

test("an absolute key is refused rather than joined", () => {
  // path.join swallows a leading slash and looks safe; path.resolve does not.
  assert.equal(resolveWithinRoot(ROOT, "/etc/passwd"), null);
  assert.equal(resolveWithinRoot(ROOT, "/"), null);
});

test("an empty key is refused", () => {
  assert.equal(resolveWithinRoot(ROOT, ""), null);
});

test("a key that stays inside resolves to a path under the root", () => {
  const target = resolveWithinRoot(ROOT, "org_abc/2d/2d711642-part.step");
  assert.ok(target);
  assert.ok(target.startsWith(path.resolve(ROOT) + path.sep));
  assert.match(target, /part\.step$/);
});

test("a key that merely looks like traversal but stays inside is allowed", () => {
  // The point of resolving rather than pattern-matching: the question is
  // where the path lands, not what characters it contains.
  const target = resolveWithinRoot(ROOT, "org_abc/sub/../part.step");
  assert.ok(target, "a key that normalises to inside the root is inside the root");
  assert.ok(target.startsWith(path.resolve(ROOT) + path.sep));
});

test("containment does not depend on the root having a trailing slash", () => {
  for (const root of [ROOT, ROOT + "/", "/var/canvas/.storage/./"]) {
    assert.ok(resolveWithinRoot(root, "org/part.step"), root);
    assert.equal(resolveWithinRoot(root, "../escape"), null, root);
  }
});

test("a sibling directory sharing the root's prefix is not inside it", () => {
  // "/var/canvas/.storage-backup" starts with "/var/canvas/.storage" as a
  // string. A startsWith test without the separator would let it through.
  assert.equal(resolveWithinRoot(ROOT, "../.storage-backup/secret"), null);
});
