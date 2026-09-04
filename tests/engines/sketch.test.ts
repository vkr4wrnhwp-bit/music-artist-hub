import test from "node:test";
import assert from "node:assert/strict";
import { sketchToSegments, type SketchPoint } from "@/lib/geometry/sketch";
import { assembleLoops } from "@/lib/geometry/loop";
import { recognizeGeometry } from "@/lib/geometry/recognize";
import { offsetChain, chainLength } from "@/lib/engines/cam/chain";

/**
 * DRAWING THE PART
 *
 * A shop with a DXF imports it. A shop working from a napkin, a sample or a
 * phone photo has nothing to import, and typing a width and a length is how
 * every part in CANVAS ended up a rectangle.
 *
 * The fillet is the part worth testing: a corner radius is an arc tangent to
 * both edges, and getting it wrong is wrong geometry on the part rather than a
 * rendering bug.
 */

const P = (x: number, y: number, r = 0): SketchPoint => ({ x, y, r });

/** A 4 x 2 rectangle, counter-clockwise from the bottom-left. */
const RECT = [P(-2, -1), P(2, -1), P(2, 1), P(-2, 1)];

const ok = (r: ReturnType<typeof sketchToSegments>) => {
  assert.equal(r.error, null, r.error ?? "");
  return r.segments;
};

/* ---------------- Sharp corners ---------------- */

test("points with no radius become the polygon through them", () => {
  const segs = ok(sketchToSegments(RECT));
  assert.equal(segs.length, 4);
  assert.ok(segs.every((s) => s.kind === "LINE"));
  const { loops, refusals } = assembleLoops(segs);
  assert.deepEqual(refusals, []);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-9);
});

test("three points is the fewest an outline can have", () => {
  assert.match(sketchToSegments([P(0, 0), P(1, 0)]).error ?? "", /at least three points/);
  assert.equal(sketchToSegments([P(0, 0), P(1, 0), P(0, 1)]).error, null);
});

test("the outline closes from the last point back to the first", () => {
  // A drawing surface that needed the last point to be clicked on top of the
  // first would be a drawing surface nobody could close.
  const segs = ok(sketchToSegments([P(0, 0), P(1, 0), P(0, 1)]));
  assert.equal(segs.length, 3);
  assert.deepEqual(segs[2].b, { x: 0, y: 0 }, "the closing segment carries something other than a coordinate");
});

/* ---------------- The fillet ---------------- */

test("a corner radius becomes an arc tangent to both edges", () => {
  /*
   * A 90 degree corner with R0.5: the arc starts 0.5 back along each edge and
   * its centre sits 0.5 in on the bisector — for the corner at (2, -1) coming
   * from (-2, -1) and going to (2, 1), that is (1.5, -0.5).
   */
  const segs = ok(sketchToSegments([P(-2, -1), P(2, -1, 0.5), P(2, 1), P(-2, 1)]));
  const arc = segs.find((s) => s.kind === "ARC");
  assert.ok(arc, "the radius did not produce an arc");
  if (arc.kind !== "ARC") throw new Error("unreachable");
  assert.ok(Math.abs(arc.center.x - 1.5) < 1e-9 && Math.abs(arc.center.y + 0.5) < 1e-9, `centre ${JSON.stringify(arc.center)}`);
  // Tangent means the arc's ends are exactly a radius from the centre.
  for (const p of [arc.a, arc.b]) {
    assert.ok(Math.abs(Math.hypot(p.x - arc.center.x, p.y - arc.center.y) - 0.5) < 1e-9, "the arc is not tangent to its edges");
  }
  // Tolerance, not deep-equal: these are computed off a tangent and a bisector.
  assert.ok(Math.abs(arc.a.x - 1.5) < 1e-9 && Math.abs(arc.a.y + 1) < 1e-9, JSON.stringify(arc.a));
  assert.ok(Math.abs(arc.b.x - 2) < 1e-9 && Math.abs(arc.b.y + 0.5) < 1e-9, JSON.stringify(arc.b));
});

test("the setback is not the radius, except on a square corner", () => {
  /*
   * The arc starts `r / tan(theta/2)` back along the edge. At 90 degrees
   * tan(45) is 1 and the setback happens to equal the radius, which is why a
   * test suite made only of rectangles cannot tell the two apart — and why an
   * L-bracket with a 60 degree corner would come out wrong and pass.
   *
   * Equilateral triangle: the corner at the origin is 60 degrees, so R0.2 sets
   * back 0.2 / tan(30) = 0.34641.
   */
  const tri = [P(0, 0, 0.2), P(2, 0), P(1, Math.sqrt(3))];
  const segs = ok(sketchToSegments(tri));
  const arc = segs.find((sg) => sg.kind === "ARC");
  if (arc?.kind !== "ARC") throw new Error("expected an arc");
  const back = 0.2 / Math.tan(Math.PI / 6);
  assert.ok(Math.abs(back - 0.34641) < 1e-5, "the fixture is not a 60 degree corner");

  // One tangent point lies up the edge toward (1, sqrt3), the other along +X.
  const along = [arc.a, arc.b].find((pt) => Math.abs(pt.y) < 1e-9);
  assert.ok(along, "neither tangent point is on the edge running along X");
  assert.ok(
    Math.abs(along!.x - back) < 1e-9,
    `tangent at ${along!.x.toFixed(5)}, expected ${back.toFixed(5)} — the setback was taken as the radius`,
  );
  // And the arc really is tangent: its centre is one radius from both ends.
  for (const pt of [arc.a, arc.b]) {
    assert.ok(Math.abs(Math.hypot(pt.x - arc.center.x, pt.y - arc.center.y) - 0.2) < 1e-9);
  }
});

test("a filleted outline measures the area it should", () => {
  // 4 x 2 less the corner a R0.5 fillet takes off: r² − πr²/4.
  const segs = ok(sketchToSegments([P(-2, -1), P(2, -1, 0.5), P(2, 1), P(-2, 1)]));
  const { loops, refusals } = assembleLoops(segs);
  assert.deepEqual(refusals, []);
  const expected = 8 - (0.25 - (Math.PI * 0.25) / 4);
  assert.ok(Math.abs(loops[0].area - expected) < 1e-9, `area ${loops[0].area} against ${expected}`);
});

test("the fillet turns the way the corner turns", () => {
  /*
   * The half that is easy to get backwards. On a counter-clockwise outline an
   * outside corner turns left, so its fillet is counter-clockwise; reverse the
   * outline and every fillet reverses with it. A fillet bulging the wrong way
   * is a corner that sticks out instead of being rounded off.
   */
  const ccw = ok(sketchToSegments([P(-2, -1), P(2, -1, 0.5), P(2, 1), P(-2, 1)]));
  const a = ccw.find((s) => s.kind === "ARC");
  if (a?.kind !== "ARC") throw new Error("expected an arc");
  assert.equal(a.cw, false);

  const cw = ok(sketchToSegments([P(-2, 1), P(2, 1), P(2, -1, 0.5), P(-2, -1)]));
  const b = cw.find((s) => s.kind === "ARC");
  if (b?.kind !== "ARC") throw new Error("expected an arc");
  assert.equal(b.cw, true, "the fillet did not follow the direction the outline was drawn in");

  // Either way round, the assembled loop is the same part.
  assert.ok(Math.abs(assembleLoops(ccw).loops[0].area - assembleLoops(cw).loops[0].area) < 1e-9);
});

test("an inside corner rounds inward", () => {
  // An L-bracket: the reflex corner is the one the cutter's own radius has to
  // fit, and its fillet must go the other way from the outside ones.
  const l = [P(0, 0), P(3, 0), P(3, 1), P(1, 1, 0.25), P(1, 3), P(0, 3)];
  const segs = ok(sketchToSegments(l));
  const { loops, refusals } = assembleLoops(segs);
  assert.deepEqual(refusals, []);
  // 3 x 1 plus 1 x 2, less what the inside fillet removes: πr²/4 − r² is
  // negative, so an inside round ADDS material back into the corner.
  const expected = 3 + 2 + (0.0625 - (Math.PI * 0.0625) / 4);
  assert.ok(Math.abs(loops[0].area - expected) < 1e-9, `area ${loops[0].area} against ${expected}`);
});

/* ---------------- What it refuses ---------------- */

test("a radius bigger than its edges is refused rather than clipped", () => {
  /*
   * A clipped fillet is a different shape from the one that was drawn, and it
   * would arrive looking deliberate. The message says how much edge the radius
   * needs and how much there is.
   */
  const r = sketchToSegments([P(-2, -1), P(2, -1, 5), P(2, 1), P(-2, 1)]);
  assert.equal(r.segments.length, 0);
  assert.match(r.error ?? "", /R5 at \(2, -1\)/);
  assert.match(r.error ?? "", /needs 5\.0000" of edge either side/);
  assert.match(r.error ?? "", /2\.0000/);
});

test("a radius on a straight-through point has nothing to round", () => {
  const r = sketchToSegments([P(-2, -1), P(0, -1, 0.25), P(2, -1), P(2, 1), P(-2, 1)]);
  assert.match(r.error ?? "", /is straight, so a radius has nothing to round/);
});

test("two points in the same place are named rather than divided by", () => {
  const r = sketchToSegments([P(0, 0), P(1, 0, 0.1), P(1, 0), P(0, 1)]);
  assert.match(r.error ?? "", /Two points at the same place/);
});

/* ---------------- End to end: what gets cut ---------------- */

test("a drawn outline reaches a proposal the contour engine will cut", () => {
  // The whole point. A drawn part and an imported part go through the same
  // assembly, the same winding rule and the same refusals.
  const segs = ok(sketchToSegments([P(-2, -1), P(2, -1, 0.5), P(2, 1, 0.5), P(-2, 1)]));
  const rec = recognizeGeometry(segs);
  assert.deepEqual(rec.refusals, []);
  assert.ok(rec.profile);
  assert.equal(rec.profile!.chain!.filter((s) => s.kind === "ARC").length, 2);
  assert.ok(Math.abs(rec.profileSize!.width - 4) < 1e-9);
  assert.ok(Math.abs(rec.profileSize!.length - 2) < 1e-9);

  const off = offsetChain({ start: rec.profile!.chainStart!, segments: rec.profile!.chain! }, 0.25);
  assert.ok(!("error" in off), `the contour engine refuses this drawing: ${JSON.stringify(off)}`);
  if ("error" in off) throw new Error("unreachable");
  assert.ok(chainLength(off) > chainLength({ start: rec.profile!.chainStart!, segments: rec.profile!.chain! }),
    "the cutter would run inside the part");
});

test("a drawing given clockwise still cuts the outside of the part", () => {
  // Nobody drawing a part thinks about winding. The assembler settles it, and
  // this is the proof it survives all the way to the offset.
  const segs = ok(sketchToSegments([P(-2, 1), P(2, 1), P(2, -1, 0.5), P(-2, -1)]));
  const rec = recognizeGeometry(segs);
  const chain = { start: rec.profile!.chainStart!, segments: rec.profile!.chain! };
  const off = offsetChain(chain, 0.25);
  if ("error" in off) throw new Error("the clockwise drawing could not be offset");
  assert.ok(chainLength(off) > chainLength(chain), "a clockwise drawing put the cutter inside the part");
});
