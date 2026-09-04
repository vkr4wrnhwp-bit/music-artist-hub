import test from "node:test";
import assert from "node:assert/strict";
import { recognizeGeometry } from "@/lib/geometry/recognize";
import { readDxf } from "@/lib/dxf/parse";
import { featureSuggestionSchema } from "@/lib/domain/features";
import type { RawSegment } from "@/lib/geometry/loop";

/**
 * CLOSED LOOPS INTO FEATURE PROPOSALS
 *
 * The last step a DXF import and a profile drawn in CANVAS share. A human
 * accepts every proposal before it becomes geometry — zero-click ingest, never
 * zero-click geometry.
 */

const L = (ax: number, ay: number, bx: number, by: number): RawSegment => ({
  kind: "LINE", a: { x: ax, y: ay }, b: { x: bx, y: by },
});

const RECT: RawSegment[] = [L(-2, -1, 2, -1), L(2, -1, 2, 1), L(2, 1, -2, 1), L(-2, 1, -2, -1)];

test("the outer loop becomes an outside contour carrying its own boundary", () => {
  const r = recognizeGeometry(RECT);
  assert.ok(r.profile);
  assert.equal(r.profile!.kind, "OUTSIDE_CONTOUR");
  assert.equal(r.profile!.chain?.length, 4);
  assert.deepEqual(r.profile!.chainStart, { x: -2, y: -1 });
  assert.equal(r.profileSize!.width, 4);
  assert.equal(r.profileSize!.length, 2);
});

test("the proposal passes the schema that guards what becomes geometry", () => {
  // `parameters` is scalars only, so the chain is its own validated field
  // rather than a loosened record that would admit anything else too.
  const parsed = featureSuggestionSchema.safeParse(recognizeGeometry(RECT).profile);
  assert.ok(parsed.success, JSON.stringify(parsed.error?.issues));
  assert.equal(parsed.data!.chain!.length, 4);
});

test("a chain of one segment is not a boundary", () => {
  // The schema floor. Two is the fewest a closed loop can have — a circle's
  // two half-arcs.
  const bad = featureSuggestionSchema.safeParse({
    kind: "OUTSIDE_CONTOUR", label: "x", parameters: {},
    chain: [{ kind: "LINE", to: { x: 1, y: 1 } }], chainStart: { x: 0, y: 0 },
  });
  assert.equal(bad.success, false);
});

test("a chain with a non-finite coordinate is refused at the boundary", () => {
  // A coordinate that is not a number is not a place on the part. Infinity is
  // the one `z.number()` lets through on its own, and it reaches the offset
  // arithmetic as a silent NaN rather than a refusal.
  for (const bad of [Number.NaN, Infinity, -Infinity]) {
    const parsed = featureSuggestionSchema.safeParse({
      kind: "OUTSIDE_CONTOUR", label: "x", parameters: {},
      chain: [{ kind: "LINE", to: { x: bad, y: 1 } }, { kind: "LINE", to: { x: 0, y: 0 } }],
      chainStart: { x: 0, y: 0 },
    });
    assert.equal(parsed.success, false, `${bad} reached the geometry`);
  }
});

/* ---------------- What a drawing does not say ---------------- */

test("depth is not invented from a 2D drawing", () => {
  /*
   * A drawing gives shape. Putting a Z on the part that nobody chose is how a
   * profile ends up cut to a depth out of thin air — so it is left absent and
   * the feature form refuses the feature until somebody supplies it.
   */
  const r = recognizeGeometry(RECT);
  assert.equal("depth" in r.profile!.parameters, false, "a depth was guessed from a flat drawing");
  assert.match(r.profile!.rationale!, /Depth is not in a 2D drawing and has not been guessed/);
});

test("a supplied depth is carried, because then somebody chose it", () => {
  const r = recognizeGeometry(RECT, { depth: 0.5 });
  assert.equal(r.profile!.parameters.depth, 0.5);
});

test("interior loops are described, not classified", () => {
  /*
   * A circle could be drilled, bored or milled — three operations, three
   * tools. That is a manufacturing decision a drawing does not answer, so the
   * interiors come back measured and named for a person to say.
   */
  const hole: RawSegment[] = [
    { kind: "ARC", a: { x: 0.25, y: 0 }, b: { x: -0.25, y: 0 }, center: { x: 0, y: 0 }, cw: false },
    { kind: "ARC", a: { x: -0.25, y: 0 }, b: { x: 0.25, y: 0 }, center: { x: 0, y: 0 }, cw: false },
  ];
  const r = recognizeGeometry([...RECT, ...hole]);
  assert.equal(r.interior.length, 1);
  assert.equal(r.interior[0].kind, "CIRCLE");
  assert.ok(Math.abs(r.interior[0].diameter! - 0.5) < 1e-9);
  assert.ok(Math.abs(r.interior[0].x) < 1e-9 && Math.abs(r.interior[0].y) < 1e-9);
  // And no hole feature was proposed off the back of it.
  assert.equal(r.profile!.kind, "OUTSIDE_CONTOUR");
});

test("two arcs that retrace each other are not a circle", () => {
  /*
   * Same centre, same radius, closed — and enclosing nothing, because the
   * second arc walks back over the first. Calling it a circle would put a
   * diameter on a loop with no area, and somebody would drill it.
   */
  const lens: RawSegment[] = [
    { kind: "ARC", a: { x: 1, y: 0 }, b: { x: -1, y: 0 }, center: { x: 0, y: 0 }, cw: false },
    { kind: "ARC", a: { x: -1, y: 0 }, b: { x: 1, y: 0 }, center: { x: 0, y: 0 }, cw: true },
  ];
  const r = recognizeGeometry([...RECT, ...lens]);
  const degenerate = r.interior.find((i) => i.area < 1e-6);
  assert.ok(degenerate, "the retracing pair did not come through as an interior loop");
  assert.equal(degenerate!.kind, "SHAPE", "a loop enclosing nothing was reported as a circle with a diameter");
  assert.equal(degenerate!.diameter, null);
});

test("an interior loop that is not a circle says so rather than being called one", () => {
  const r = recognizeGeometry([
    ...RECT,
    L(-1, -0.5, -0.5, -0.5), L(-0.5, -0.5, -0.5, 0.5), L(-0.5, 0.5, -1, 0.5), L(-1, 0.5, -1, -0.5),
  ]);
  assert.equal(r.interior.length, 1);
  assert.equal(r.interior[0].kind, "SHAPE");
  assert.equal(r.interior[0].diameter, null);
});

/* ---------------- Size has to cover the part ---------------- */

test("an arc that bulges past its endpoints is inside the measured size", () => {
  /*
   * A quarter-round corner whose ends are both inside the bounding box still
   * reaches out to the radius. A size taken from endpoints alone reports a
   * part smaller than it is — which is a stock size that does not cover it.
   *
   * A disc of r = 1 has both arc endpoints on the x axis and reaches y = ±1.
   */
  const disc: RawSegment[] = [
    { kind: "ARC", a: { x: 1, y: 0 }, b: { x: -1, y: 0 }, center: { x: 0, y: 0 }, cw: false },
    { kind: "ARC", a: { x: -1, y: 0 }, b: { x: 1, y: 0 }, center: { x: 0, y: 0 }, cw: false },
  ];
  const r = recognizeGeometry(disc);
  assert.ok(Math.abs(r.profileSize!.width - 2) < 1e-9, `width ${r.profileSize!.width}`);
  assert.ok(Math.abs(r.profileSize!.length - 2) < 1e-9, `length ${r.profileSize!.length} — the arc's bulge was not measured`);
});

test("an arc that does not reach a cardinal direction does not stretch the size", () => {
  // The other half of the same rule: only the extremes the arc actually sweeps
  // through count, or every rounded corner would inflate the part.
  const nub: RawSegment[] = [
    L(0, 0, 1, 0),
    { kind: "ARC", a: { x: 1, y: 0 }, b: { x: 0, y: 1 }, center: { x: 0, y: 0 }, cw: false },
    L(0, 1, 0, 0),
  ];
  const r = recognizeGeometry(nub);
  assert.ok(Math.abs(r.profileSize!.width - 1) < 1e-9, `width ${r.profileSize!.width}`);
  assert.ok(Math.abs(r.profileSize!.length - 1) < 1e-9, `length ${r.profileSize!.length}`);
});

/* ---------------- Nothing hidden ---------------- */

test("a gap that was closed is reported on the proposal", () => {
  const noisy = [L(-2, -1, 2, -1), L(2, -1 + 6e-5, 2, 1), RECT[2], RECT[3]];
  const r = recognizeGeometry(noisy);
  assert.match(r.warnings.join(" "), /closed across a gap of 0\.0000[56]/);
  assert.match(r.warnings.join(" "), /stated rather than hidden/);
});

test("an outline that does not close proposes nothing and says why", () => {
  const r = recognizeGeometry([RECT[0], RECT[1], RECT[2]]);
  assert.equal(r.profile, null, "an open outline was proposed as a boundary");
  assert.equal(r.profileSize, null);
  assert.equal(r.refusals.length, 1);
  assert.match(r.refusals[0].reason, /stops at/);
});

/* ---------------- A DXF, end to end ---------------- */

test("a DXF plate reaches a schema-valid proposal carrying its real outline", () => {
  const b = Math.tan(Math.PI / 8);
  const file = [
    "0", "SECTION", "2", "ENTITIES",
    "0", "LWPOLYLINE", "90", "5", "70", "1",
    "10", "-2", "20", "-1", "42", "0",
    "10", "2", "20", "-1", "42", "0",
    "10", "2", "20", "0.5", "42", String(b),
    "10", "1.5", "20", "1", "42", "0",
    "10", "-2", "20", "1", "42", "0",
    "0", "CIRCLE", "10", "0", "20", "0", "40", "0.1875",
    "0", "ENDSEC", "0", "EOF",
  ].join("\n");

  const r = recognizeGeometry(readDxf(file).segments);
  assert.deepEqual(r.refusals, []);
  assert.ok(r.profile);
  const parsed = featureSuggestionSchema.safeParse(r.profile);
  assert.ok(parsed.success, JSON.stringify(parsed.error?.issues));
  // Five segments: four straights and the fillet arc.
  assert.equal(r.profile!.chain!.length, 5);
  assert.equal(r.profile!.chain!.filter((s) => s.kind === "ARC").length, 1, "the fillet did not survive as an arc");
  assert.equal(r.interior.length, 1);
  assert.ok(Math.abs(r.interior[0].diameter! - 0.375) < 1e-9);
  assert.ok(Math.abs(r.profileSize!.width - 4) < 1e-9);
});
