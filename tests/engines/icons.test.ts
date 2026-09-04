import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";

/**
 * THE ICON SET IS ONE SET.
 *
 * These marks lived inline in nav.tsx, so the navigation had a vocabulary and
 * nothing else could reach it. Lifting them out only helps if they stay
 * lifted — the failure this guards is a second bore drawn somewhere else,
 * three months from now, at a different weight, that nobody notices because
 * it looks approximately right.
 */

const src = readFileSync("src/components/icons.tsx", "utf8");
const files = readdirSync("src", { recursive: true, encoding: "utf8" }).filter((f) => /\.tsx$/.test(f));

test("one grid, one weight, one colour source", () => {
  assert.match(src, /viewBox="0 0 20 20"/, "the set is drawn on a 20x20 grid");
  assert.match(src, /strokeWidth=\{1\.25\}/, "one stroke weight");
  assert.match(src, /stroke="currentColor"/, "marks take the colour of the text beside them");
  // A hardcoded stroke or fill colour is a mark that cannot express state,
  // and it is how a red icon ends up beside grey text.
  const hex = src.match(/(?:stroke|fill)="#[0-9a-f]{3,8}"/gi);
  assert.equal(hex, null, `a mark hardcodes a colour: ${hex?.join(", ")}`);
});

test("the datum triangle is the only filled shape", () => {
  const filled = [...src.matchAll(/fill="currentColor"/g)];
  assert.equal(filled.length, 1, "exactly one filled shape — a datum triangle is filled on a drawing, nothing else is");
});

test("every path stays inside the safe area", () => {
  // A coordinate outside 1.8–18.2 clips against a 20px box at rail size, and
  // it clips silently: the mark simply loses a stroke and still looks like an
  // icon.
  /*
   * BOTH sources, and this is the whole test. The first version scanned only
   * `d="..."` attributes and so read the six shapes in EXTRA while skipping
   * all twenty-six paths in the P record, which are plain strings. It passed a
   * planted `M10 -2 V6` without noticing — a green safe-area check over
   * geometry it had never looked at.
   */
  const record = src.slice(src.indexOf("const P:"), src.indexOf("const EXTRA:"));
  const sources = [
    ...[...record.matchAll(/"((?:M|A)[^"]*)"/g)].flatMap((m) => m[1].split("|")),
    ...[...src.matchAll(/d="([^"]+)"/g)].map((m) => m[1]),
  ];
  // A count, so the scan cannot silently shrink to nothing and still pass —
  // which is exactly how the first version of this test went green over
  // geometry it was not reading.
  assert.ok(sources.length >= 80, `expected the whole set, scanned ${sources.length} subpaths`);
  const bad: string[] = [];
  for (const raw of sources) {
    const m = [raw, raw];
    for (const n of m[1].matchAll(/-?\d+(?:\.\d+)?/g)) {
      const v = Number(n[0]);
      // Arc flags and radii in `A r r 0 0 1 x y` are not coordinates; the
      // bound below is loose enough to admit them and tight enough to catch a
      // real overshoot.
      if (v < -0.1 || v > 20.1) bad.push(`${m[1]} -> ${v}`);
    }
  }
  assert.deepEqual(bad, [], `paths outside the 20x20 box: ${bad.join("; ")}`);
});

test("nav.tsx no longer carries its own glyphs", () => {
  const nav = readFileSync("src/components/nav.tsx", "utf8");
  assert.ok(!/function RailIcon/.test(nav), "RailIcon is back — the rail is drawing its own set again");
  assert.ok(nav.includes('from "./icons"'), "the rail must draw from the shared set");
});

test("no component outside icons.tsx draws a 20x20 stroked mark of its own", () => {
  /*
   * The scan is deliberately narrow: a 20x20 viewBox with a 1.25 stroke IS
   * this set's signature, so anything else matching it is a copy. Diagrams,
   * thumbnails and the workspace draw at other sizes and are untouched — they
   * are drawings of a part, not marks in the vocabulary.
   */
  const strays: string[] = [];
  for (const f of files) {
    if (f === "components/icons.tsx") continue;
    const body = readFileSync(`src/${f}`, "utf8");
    for (const m of body.matchAll(/<svg[^>]*viewBox="0 0 20 20"[^>]*>/g)) {
      if (/strokeWidth=\{?1\.25/.test(m[0]) || /stroke-width="1\.25"/.test(m[0])) strays.push(f);
    }
  }
  assert.deepEqual([...new Set(strays)], [], `a second copy of the icon set: ${strays.join(", ")}`);
});

test("every name in IconName actually draws something", () => {
  // A name in the union with no geometry renders an empty <svg>: a 20px hole
  // where a mark should be, with no error anywhere.
  const union = src.slice(src.indexOf("export type IconName"), src.indexOf("/**", src.indexOf("export type IconName")));
  const names = [...union.matchAll(/"([a-zA-Z]+)"/g)].map((m) => m[1]);
  assert.ok(names.length >= 26, `IconName lists ${names.length} marks`);
  const inP = new Set([...src.slice(src.indexOf("const P:"), src.indexOf("const EXTRA:")).matchAll(/^\s{2}([a-zA-Z]+):/gm)].map((m) => m[1]));
  const inExtra = new Set([...src.slice(src.indexOf("const EXTRA:"), src.indexOf("export type IconName")).matchAll(/^\s{2}([a-zA-Z]+):/gm)].map((m) => m[1]));
  const empty = names.filter((n) => !inP.has(n) && !inExtra.has(n));
  assert.deepEqual(empty, [], `these names render an empty svg: ${empty.join(", ")}`);
});
