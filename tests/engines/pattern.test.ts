import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { expandPattern, offStock, patternable, type PatternSpec } from "@/lib/domain/pattern";
import type { Feature, Stock } from "@/lib/domain/features";

/**
 * A BOLT CIRCLE IS ONE STATEMENT ON A DRAWING AND SIX FEATURES ON A PART.
 *
 * Every hole in a pattern had to be typed in by hand, one at a time, with its
 * coordinates worked out off the machine. Six holes on a 3.000" bolt circle is
 * twelve numbers to compute and twelve to mistype, on the most common thing
 * there is on a plate — and a hole entered at the wrong angle gets drilled in
 * the wrong place and measures perfectly on its own diameter.
 */

const near = (a: number, b: number, tol = 1e-6) => Math.abs(a - b) < tol;

/* ---------------- Bolt circle ---------------- */

const circle = (over: Partial<Extract<PatternSpec, { kind: "BOLT_CIRCLE" }>> = {}): PatternSpec => ({
  kind: "BOLT_CIRCLE", centerX: 0, centerY: 0, diameter: 3, count: 6, startAngle: 0, ...over,
});

test("a bolt circle puts every hole on the circle, evenly, from the stated angle", () => {
  const pts = expandPattern(circle());
  assert.ok(!("error" in pts));
  assert.equal(pts.length, 6);
  // The DIAMETER is the circle the centres sit on, which is what a drawing
  // states — not a radius, and not the holes.
  for (const p of pts) assert.ok(near(Math.hypot(p.x, p.y), 1.5), `${p.x},${p.y} is not on the ⌀3.000 circle`);
  // First at the stated angle, then every 60°.
  assert.ok(near(pts[0].x, 1.5) && near(pts[0].y, 0));
  assert.ok(near(pts[1].x, 0.75) && near(pts[1].y, 1.5 * Math.sin(Math.PI / 3)));
  assert.deepEqual(pts.map((p) => p.index), [1, 2, 3, 4, 5, 6]);
});

test("the start angle rotates the whole circle, and the centre moves it", () => {
  const rotated = expandPattern(circle({ startAngle: 30 }));
  assert.ok(!("error" in rotated));
  assert.ok(near(rotated[0].x, 1.5 * Math.cos(Math.PI / 6)));
  assert.ok(near(rotated[0].y, 1.5 * Math.sin(Math.PI / 6)));

  const moved = expandPattern(circle({ centerX: 1, centerY: -2 }));
  assert.ok(!("error" in moved));
  for (const p of moved) assert.ok(near(Math.hypot(p.x - 1, p.y + 2), 1.5));
});

test("a bolt circle of one is not a pattern, and neither is one with no diameter", () => {
  const one = expandPattern(circle({ count: 1 }));
  assert.ok("error" in one);
  assert.match(one.error.reason, /A bolt circle of 1 is not a pattern/);
  assert.ok(one.error.recommendations.some((r) => /just a hole/.test(r)));

  const flat = expandPattern(circle({ diameter: 0 }));
  assert.ok("error" in flat);
  assert.match(flat.error.reason, /needs a diameter/);
  // The message names which circle, because that is the number people confuse.
  assert.ok(flat.error.recommendations.some((r) => /the circle the hole CENTRES sit on/.test(r)));
});

/* ---------------- Grid ---------------- */

const grid = (over: Partial<Extract<PatternSpec, { kind: "GRID" }>> = {}): PatternSpec => ({
  kind: "GRID", originX: -1, originY: -1, columns: 3, rows: 2, pitchX: 1, pitchY: 0.5, ...over,
});

test("a grid runs row-major from its first instance", () => {
  const pts = expandPattern(grid());
  assert.ok(!("error" in pts));
  assert.equal(pts.length, 6);
  // The order a machinist reads a grid, and the order the holes come out of
  // the drill cycle.
  assert.deepEqual(
    pts.map((p) => [p.x, p.y]),
    [[-1, -1], [0, -1], [1, -1], [-1, -0.5], [0, -0.5], [1, -0.5]],
  );
});

test("a grid that repeats needs a pitch in the direction it repeats", () => {
  // Zero pitch puts two features in the same place, which is a hole drilled
  // twice and a coverage list with a duplicate in it.
  const noX = expandPattern(grid({ pitchX: 0 }));
  assert.ok("error" in noX);
  assert.match(noX.error.reason, /a pitch of zero puts two features in the same place/);
  // A single column does not need an X pitch, because it never repeats in X.
  assert.ok(!("error" in expandPattern(grid({ columns: 1, pitchX: 0 }))));
  assert.ok("error" in expandPattern(grid({ columns: 1, rows: 1 })));
});

/* ---------------- Line ---------------- */

test("a line runs along its stated angle at its stated pitch", () => {
  const pts = expandPattern({ kind: "LINEAR", originX: 0, originY: 0, count: 4, pitch: 0.5, angle: 90 });
  assert.ok(!("error" in pts));
  assert.deepEqual(pts.map((p) => [p.x, p.y]), [[0, 0], [0, 0.5], [0, 1], [0, 1.5]]);

  const diag = expandPattern({ kind: "LINEAR", originX: 0, originY: 0, count: 3, pitch: Math.SQRT2, angle: 45 });
  assert.ok(!("error" in diag));
  assert.ok(near(diag[1].x, 1) && near(diag[1].y, 1));
});

test("a line of one, or with no pitch, is refused", () => {
  assert.ok("error" in expandPattern({ kind: "LINEAR", originX: 0, originY: 0, count: 1, pitch: 1, angle: 0 }));
  const flat = expandPattern({ kind: "LINEAR", originX: 0, originY: 0, count: 4, pitch: 0, angle: 0 });
  assert.ok("error" in flat);
  assert.match(flat.error.reason, /every instance in the same place/);
});

/* ---------------- Against the stock ---------------- */

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

test("a pattern bigger than the plate is caught before the features exist", () => {
  /*
   * A bolt circle bigger than the stock is a transposed diameter or a pattern
   * measured from the wrong datum. Six features and one hole in the middle of
   * a rapid is a much more expensive way to find that out.
   */
  // ⌀6 on a 6 × 4 plate: the two on the X axis land on the edge, the other
  // four are past the ends of the short side.
  const pts = expandPattern(circle({ diameter: 6 }));
  assert.ok(!("error" in pts));
  const off = offStock(pts, STOCK);
  assert.equal(off.length, 4, `${off.length} of 6 off a 6 × 4 plate on a ⌀6 circle`);
  // Bigger than the plate in every direction is all of them.
  const wild = expandPattern(circle({ diameter: 8 }));
  assert.ok(!("error" in wild));
  assert.equal(offStock(wild, STOCK).length, 6);
  // And a pattern that fits reports nothing.
  const fits = expandPattern(circle());
  assert.ok(!("error" in fits));
  assert.equal(offStock(fits, STOCK).length, 0);
});

test("only a feature with a centre can be placed", () => {
  const hole = { id: "h", kind: "DRILLED_HOLE", label: "h", centerX: 0, centerY: 0, diameter: 0.2 } as unknown as Feature;
  const contour = { id: "c", kind: "OUTSIDE_CONTOUR", label: "c", width: 5, length: 3 } as unknown as Feature;
  assert.equal(patternable(hole), true);
  assert.equal(patternable(contour), false);
});

/* ---------------- What the action does with it ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const action = strip(readFileSync("src/app/(app)/parts/[id]/features/feature-actions.ts", "utf8"));

test("a pattern is expanded into real features, not held as a pattern", () => {
  /*
   * Everything downstream of the feature list is per feature: coverage asks
   * whether each one is cut, inspection assigns each one a method, measurement
   * records a reading against each one. A virtual pattern would have to be
   * unfolded at every one of those points, and the first place it was not
   * unfolded would be a hole nobody checked.
   */
  assert.ok(/for \(const pos of positions\.slice\(1\)\) \{[\s\S]{0,200}?tx\.feature\.create/.test(action));
  // The source BECOMES the first instance rather than being copied beside it.
  assert.ok(/tx\.feature\.update\(\{[\s\S]{0,400}?patternIndex: 1,/.test(action));
  assert.ok(/centerX: positions\[0\]\.x, centerY: positions\[0\]\.y/.test(action));
});

test("the pattern is placed in one transaction", () => {
  // Half a bolt circle is worse than none: the coverage gate would pass on
  // three holes and the drawing calls six.
  assert.ok(/await db\.\$transaction\(/.test(action), "a pattern can be left half-created");
});

test("the inspection method is not carried across the pattern", () => {
  /*
   * A method is a decision about how one feature gets verified, recorded
   * against a name and a time. Copying it would put a person's signature on
   * five decisions they did not make.
   */
  const create = /for \(const pos of positions\.slice\(1\)\)[\s\S]*?\n    \}/.exec(action)![0];
  assert.equal(/inspectionMethod/.test(create), false, "an inspection method is copied onto features nobody assessed");
  assert.equal(/inspectionMethodBy/.test(create), false);
  // The tolerance and the fit ARE carried: they are properties of the feature
  // the machinist described, not decisions about one instance.
  assert.ok(/tolerancePlus: source\.tolerancePlus/.test(create));
  assert.ok(/fitClass: source\.fitClass/.test(create));
});

test("a pattern off the stock is refused before anything is created", () => {
  assert.ok(/const off = offStock\(positions, revision\.stock\);/.test(action), "the stock check is gone");
  assert.ok(
    /if \(off\.length > 0\) \{[\s\S]{0,500}?return \{/.test(action),
    "the stock check does not refuse",
  );
  assert.ok(
    action.indexOf("offStock(positions") < action.indexOf("db.$transaction"),
    "features are created before the check runs",
  );
});

test("a feature already in a pattern is not patterned again", () => {
  // Otherwise the second placement silently orphans the first group.
  assert.ok(/if \(source\.patternId\) return \{ error:/.test(action));
});
