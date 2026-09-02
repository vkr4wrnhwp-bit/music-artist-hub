import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * "Highlight the target feature in the uploaded image and the 3D
 * reconstruction."
 *
 * Half of that ask is buildable and half is not, and the difference is the
 * whole point. CANVAS holds the reconstructed geometry in part coordinates,
 * so it can point at a feature there. It records which face a photograph
 * shows and what scale reference was in frame — not an origin, an orientation
 * or a pixels-per-inch — so it cannot place a marker on the photo without
 * guessing, and an operator would measure whatever the guess landed on.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const guided = () => strip(readFileSync("src/components/reverse/guided-measurement.tsx", "utf8"));
const thumb = () => strip(readFileSync("src/components/part-thumb.tsx", "utf8"));

test("the reference panel no longer shows photos[0] regardless of anything", () => {
  // The defect: the first uploaded photo, always, with no way to see another.
  const src = guided();
  assert.ok(!/photos\[0\]\.url/.test(src), "the panel is back to hardcoding the first photo");
  assert.ok(/setViewId/.test(src), "there is no way to choose a view");
});

test("every uploaded view is reachable, and the absent ones are named", () => {
  const src = guided();
  assert.ok(/photos\.map\(/.test(src), "the views are not offered as choices");
  // Computed against the set photo-set.tsx asks for, and actually rendered.
  assert.ok(/REQUIRED_VIEWS\.filter\(/.test(src), "nothing compares the uploads against the required set");
  assert.ok(/\{missingViews\.join\(/.test(src), "the missing views are computed and never shown");
  assert.ok(/missingViews\.length > 0 &&/.test(src), "the missing-view line is not conditioned on there being any");
});

test("the highlight is drawn on the geometry, never on the photograph", () => {
  const src = guided();
  assert.ok(/highlightFeatureId=\{highlighted\?\.id/.test(src), "the linked feature is not highlighted in the geometry");
  // A marker positioned over the image would look like this. There is no
  // basis for one, so there must not be one.
  assert.ok(!/<img[\s\S]{0,400}?position:\s*absolute/.test(src), "something is being positioned over the photo");
  assert.ok(!/pixelsPerInch|imageOrigin|photoScale|markerX/.test(src), "a photo-space coordinate appeared");
});

test("the panel says why the photograph carries no marker", () => {
  // Principle 5: an unimplemented capability stays visibly labelled. Silence
  // would read as "there is nothing to point at here".
  const src = guided();
  assert.match(src, /No marker is drawn on the photograph/);
  assert.match(src, /cannot place one without guessing/);
});

test("the highlight cannot make an ordinary feature read as critical", () => {
  // BLUE means critical in this drawing. If the highlight changed a stroke
  // colour, emphasis and criticality would be the same signal — and a
  // machinist reads blue as "this one is critical", not "this one is selected".
  const src = thumb();
  const block = /highlight === null\) return shape;[\s\S]{0,400}/.exec(src);
  assert.ok(block, "the highlight branch moved — this test cannot check it any more");
  assert.ok(!/BLUE/.test(block![0]), "the highlight sets a colour rather than an opacity");
  assert.match(block![0], /opacity=/);
});

test("with nothing highlighted the drawing is untouched", () => {
  // The thumbnail is used across the library; passing no highlight must not
  // dim anything or change the markup.
  const src = thumb();
  assert.match(src, /shape === null \|\| highlight === null\) return shape;/);
  assert.match(src, /highlightFeatureId = null/, "the prop is not optional-with-no-highlight by default");
});


test("a highlight the plan view cannot draw is ignored, not honoured", () => {
  // Caught in the browser, not by a type: linking "Face top" dimmed all eight
  // drawable features to emphasise a feature that renders as nothing. A
  // highlight pointing at empty space is worse than no highlight, because it
  // hides the geometry the operator can actually see.
  const src = thumb();
  assert.match(src, /export function drawnInTopView/, "nothing decides whether a feature is drawable");
  assert.match(
    src,
    /const highlight = features\.some\(\(x\) => x\.id === highlightFeatureId && drawnInTopView\(x\)\)/,
    "the highlight is applied without checking the feature is drawn",
  );
  // The dimming must key off the checked value, not the raw prop.
  const branch = /if \(shape === null \|\| highlight[\s\S]{0,200}/.exec(src)![0];
  assert.ok(!/highlightFeatureId/.test(branch), "the render still reads the unchecked prop");
});

test("the panel says when a linked feature has no outline in plan", () => {
  const src = guided();
  assert.match(src, /drawnInTopView/, "the panel does not ask whether the feature is drawable");
  assert.match(src, /has no outline in plan/);
});

test("every kind the drawing renders is listed as drawable", () => {
  // If a new kind gains a shape and is not added to the list, its highlight
  // silently stops working. Both lists live in this file; compare them.
  const src = thumb();
  const listed = /const DRAWN_IN_TOP_VIEW = \[([\s\S]*?)\]/.exec(src)![1];
  const rendered = new Set([...src.matchAll(/f\.kind === "([A-Z_]+)"/g)].map((m) => m[1]));
  for (const kind of rendered) {
    assert.ok(listed.includes(`"${kind}"`), `${kind} is drawn but is not listed as drawable`);
  }
  assert.ok(rendered.size >= 7, `precondition: the drawing still renders several kinds (${rendered.size})`);
});
