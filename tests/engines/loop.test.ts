import test from "node:test";
import assert from "node:assert/strict";
import { assembleLoops, splitProfile, JOIN_TOLERANCE, type RawSegment } from "@/lib/geometry/loop";
import { offsetChain, chainLength } from "@/lib/engines/cam/chain";

/**
 * UNORDERED SEGMENTS INTO A CLOSED, CORRECTLY-WOUND LOOP
 *
 * `Feature.chain` was read by two engines, typed in the domain, and written by
 * nothing — so every profile CANVAS posted was a rounded rectangle from three
 * numbers. This is the shared middle a DXF and a drawn sketch both arrive at.
 */

const L = (ax: number, ay: number, bx: number, by: number): RawSegment => ({
  kind: "LINE",
  a: { x: ax, y: ay },
  b: { x: bx, y: by },
});

/** A 4 x 2 rectangle centred on the origin, given counter-clockwise. */
const RECT_CCW: RawSegment[] = [
  L(-2, -1, 2, -1),
  L(2, -1, 2, 1),
  L(2, 1, -2, 1),
  L(-2, 1, -2, -1),
];

const areaOf = (segs: RawSegment[]) => assembleLoops(segs).loops[0].area;

/* ---------------- Closing the loop ---------------- */

test("segments in any order become one closed loop", () => {
  // File order is whatever the CAD wrote; click order is whatever the hand did.
  const shuffled = [RECT_CCW[2], RECT_CCW[0], RECT_CCW[3], RECT_CCW[1]];
  const { loops, refusals } = assembleLoops(shuffled);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 1);
  assert.equal(loops[0].chain.segments.length, 4);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-9, `area ${loops[0].area}`);
});

test("an edge given backwards is turned round rather than refused", () => {
  // A CAD writes a line from whichever end it likes. Which end is not a fact
  // about the part.
  const flipped = [RECT_CCW[0], L(2, 1, 2, -1), RECT_CCW[2], RECT_CCW[3]];
  const { loops, refusals } = assembleLoops(flipped);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 1);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-9);
});

test("the chain the loop produces is actually closed", () => {
  const { chain } = assembleLoops(RECT_CCW).loops[0];
  const end = chain.segments[chain.segments.length - 1].to;
  assert.ok(Math.hypot(end.x - chain.start.x, end.y - chain.start.y) < 1e-9, "the last segment does not return to the start");
});

/* ---------------- Winding is not cosmetic ---------------- */

test("a clockwise drawing comes out counter-clockwise", () => {
  /*
   * `contourToolpath` compensates side RIGHT — G42 — and `rectangleChain` is
   * counter-clockwise. Cut CCW with the tool on the right and the tool is
   * OUTSIDE the boundary, which is what profiling a part means. Feed a
   * clockwise loop through unchanged and the same G42 puts the cutter inside:
   * it climbs into the part and takes the profile off undersize by a full tool
   * diameter, with a program that reads correctly on the screen.
   *
   * A DXF carries no intent about direction and CAD writes both.
   */
  const cw = RECT_CCW.slice().reverse().map((s) => L(s.b.x, s.b.y, s.a.x, s.a.y));
  const { loops } = assembleLoops(cw);
  assert.equal(loops.length, 1);

  // The proof is not the segment order — it is which way the offset goes. A
  // correctly wound outside profile offsets OUTWARD, so it gets longer.
  const off = offsetChain(loops[0].chain, 0.25);
  assert.ok(!("error" in off), "the assembled loop could not be offset");
  if ("error" in off) throw new Error("unreachable");
  assert.ok(
    chainLength(off) > chainLength(loops[0].chain),
    "the offset came out shorter, so the cutter is on the inside of the part",
  );
});

test("a counter-clockwise drawing is left alone", () => {
  const off = offsetChain(assembleLoops(RECT_CCW).loops[0].chain, 0.25);
  if ("error" in off) throw new Error("the CCW loop could not be offset");
  assert.ok(chainLength(off) > chainLength(assembleLoops(RECT_CCW).loops[0].chain));
});

test("winding is decided by area, including the arc's own cap", () => {
  /*
   * A shoelace over the chord alone gets the sign wrong on a shape whose arcs
   * carry most of its area — a slot-shaped outline is mostly two half-discs,
   * and a chord-only sum can land the wrong side of zero.
   */
  const slot: RawSegment[] = [
    L(-1, -0.5, 1, -0.5),
    { kind: "ARC", a: { x: 1, y: -0.5 }, b: { x: 1, y: 0.5 }, center: { x: 1, y: 0 }, cw: false },
    L(1, 0.5, -1, 0.5),
    { kind: "ARC", a: { x: -1, y: 0.5 }, b: { x: -1, y: -0.5 }, center: { x: -1, y: 0 }, cw: false },
  ];
  // 2 x 1 rectangle plus a full circle of r = 0.5.
  const expected = 2 + Math.PI * 0.25;
  assert.ok(Math.abs(areaOf(slot) - expected) < 1e-9, `area ${areaOf(slot)} against ${expected}`);

  const reversed = slot.slice().reverse().map((s) =>
    s.kind === "LINE" ? L(s.b.x, s.b.y, s.a.x, s.a.y) : { ...s, a: s.b, b: s.a, cw: !s.cw },
  );
  assert.ok(Math.abs(areaOf(reversed) - expected) < 1e-9, "the reversed slot did not measure the same area");
  const off = offsetChain(assembleLoops(reversed).loops[0].chain, 0.1);
  if ("error" in off) throw new Error("the reversed slot could not be offset");
  assert.ok(chainLength(off) > chainLength(assembleLoops(reversed).loops[0].chain));
});

/* ---------------- What it refuses, by name ---------------- */

test("a boundary that does not close says where it stops and how far the gap is", () => {
  // A drawing that does not close is a drawing with a mistake in it, and the
  // mistake has coordinates.
  const open = [RECT_CCW[0], RECT_CCW[1], RECT_CCW[2]];
  const { loops, refusals } = assembleLoops(open);
  assert.equal(loops.length, 0, "an open boundary was cut as a closed one");
  assert.equal(refusals.length, 1);
  assert.match(refusals[0].reason, /stops at \(-2\.0000, 1\.0000\)/);
  assert.match(refusals[0].reason, /nothing continues/);
});

test("a branch is refused rather than guessed", () => {
  // Two edges meeting at one point is a duplicated edge or a centreline left
  // in the export, and which way the boundary goes is not something to guess.
  const branched = [...RECT_CCW, L(2, -1, 4, -1)];
  const { refusals } = assembleLoops(branched);
  assert.ok(refusals.length >= 1);
  assert.match(refusals[0].reason, /More than one edge meets at/);
  assert.match(refusals[0].recommendations.join(" "), /duplicated edge|construction lines/);
});

test("nothing is nudged shut silently", () => {
  /*
   * CAD noise is closed, because refusing a boundary over a nanometre would
   * make the feature unusable. What is closed is REPORTED, because a gap a CAD
   * wrote by accident is worth knowing about before the part is cut.
   */
  const noisy = [L(-2, -1, 2, -1), L(2, -1 + 5e-5, 2, 1), RECT_CCW[2], RECT_CCW[3]];
  const { loops, refusals } = assembleLoops(noisy);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 1);
  // Not an exact compare: the join distance is a hypot of the drawn gap.
  assert.ok(loops[0].largestGapClosed > 4e-5, "the gap that was closed is not reported");
  assert.ok(loops[0].largestGapClosed <= JOIN_TOLERANCE);
});

test("a gap wider than CAD noise is a mistake, not noise", () => {
  const drawn = [L(-2, -1, 2, -1), L(2, -0.99, 2, 1), RECT_CCW[2], RECT_CCW[3]];
  const { loops, refusals } = assembleLoops(drawn);
  assert.equal(loops.length, 0, `a 0.010" gap was closed silently`);
  assert.match(refusals[0].reason, /0\.0100" away/);
});

test("a zero-length edge is not geometry and not a complaint", () => {
  // Every CAD emits a duplicated point sooner or later.
  const { loops, refusals } = assembleLoops([...RECT_CCW, L(2, 1, 2, 1)]);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 1);
  assert.equal(loops[0].chain.segments.length, 4);
});

/* ---------------- A DXF is the profile and the holes ---------------- */

test("more than one loop is the normal case, not an error", () => {
  // A plate exported from CAD is its outline and its holes in one file.
  const hole: RawSegment[] = [
    { kind: "ARC", a: { x: 0.25, y: 0 }, b: { x: -0.25, y: 0 }, center: { x: 0, y: 0 }, cw: false },
    { kind: "ARC", a: { x: -0.25, y: 0 }, b: { x: 0.25, y: 0 }, center: { x: 0, y: 0 }, cw: false },
  ];
  const { loops, refusals } = assembleLoops([...RECT_CCW, ...hole]);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 2);

  const { profile, interior } = splitProfile(loops);
  assert.ok(profile);
  assert.ok(Math.abs(profile!.area - 8) < 1e-9, "the outside of the part is not the largest loop");
  assert.equal(interior.length, 1);
  assert.ok(Math.abs(interior[0].area - Math.PI * 0.0625) < 1e-9);
});

test("interior loops are handed back rather than dropped", () => {
  // Nothing here decides what an interior loop IS — a circle could be drilled,
  // bored or milled, and a drawing does not answer that. Dropping it silently
  // is the one thing that must not happen.
  const { loops } = assembleLoops([
    ...RECT_CCW,
    L(-1, -0.5, -0.5, -0.5),
    L(-0.5, -0.5, -0.5, 0.5),
    L(-0.5, 0.5, -1, 0.5),
    L(-1, 0.5, -1, -0.5),
  ]);
  const { interior } = splitProfile(loops);
  assert.equal(interior.length, 1);
  assert.ok(Math.abs(interior[0].area - 0.5) < 1e-9);
});

test("the outside of the part is the largest loop, whatever order it arrives in", () => {
  // A CAD writes the holes before the outline as often as after. Taking the
  // first loop found would profile the part around one of its own holes.
  const hole = [
    L(-0.5, -0.5, 0.5, -0.5),
    L(0.5, -0.5, 0.5, 0.5),
    L(0.5, 0.5, -0.5, 0.5),
    L(-0.5, 0.5, -0.5, -0.5),
  ];
  const { profile, interior } = splitProfile(assembleLoops([...hole, ...RECT_CCW]).loops);
  assert.ok(Math.abs(profile!.area - 8) < 1e-9, "an interior loop was taken as the part outline");
  assert.equal(interior.length, 1);
  assert.ok(Math.abs(interior[0].area - 1) < 1e-9);
});

test("reversing an arc reverses which way it goes round", () => {
  /*
   * The half of the flip that is easy to miss: turning the loop round reverses
   * the order and the endpoints, and an arc walked the other way also sweeps
   * the other way. Leave `cw` alone and the arc bulges out of the part instead
   * of into it — a D-shaped plate profiled as though the flat were the curve.
   */
  const cwSlot: RawSegment[] = [
    L(-1, 0.5, 1, 0.5),
    { kind: "ARC", a: { x: 1, y: 0.5 }, b: { x: 1, y: -0.5 }, center: { x: 1, y: 0 }, cw: true },
    L(1, -0.5, -1, -0.5),
    { kind: "ARC", a: { x: -1, y: -0.5 }, b: { x: -1, y: 0.5 }, center: { x: -1, y: 0 }, cw: true },
  ];
  const { loops } = assembleLoops(cwSlot);
  assert.equal(loops.length, 1);
  // Wound clockwise on the way in, so every arc must have been turned round.
  const arcs = loops[0].chain.segments.filter((sg) => sg.kind === "ARC");
  assert.equal(arcs.length, 2);
  for (const a of arcs) assert.equal(a.kind === "ARC" && a.cw, false, "a reversed arc kept its original direction");
  // And the area is still the slot's, not a bow-tie's.
  assert.ok(Math.abs(loops[0].area - (2 + Math.PI * 0.25)) < 1e-9, `area ${loops[0].area}`);
});

test("no geometry at all is no profile, not an empty one", () => {
  const { profile, interior } = splitProfile(assembleLoops([]).loops);
  assert.equal(profile, null);
  assert.deepEqual(interior, []);
});

/* ---------------- The engine has to accept what comes out ---------------- */

test("an assembled profile survives the offset the toolpath needs", () => {
  // The whole point. A chain that cannot be offset is a chain the contour
  // engine refuses, and the import would have produced a feature nothing cuts.
  const rounded: RawSegment[] = [
    L(-2, -1, 1.75, -1),
    { kind: "ARC", a: { x: 1.75, y: -1 }, b: { x: 2, y: -0.75 }, center: { x: 1.75, y: -0.75 }, cw: false },
    L(2, -0.75, 2, 1),
    L(2, 1, -2, 1),
    L(-2, 1, -2, -1),
  ];
  const { loops, refusals } = assembleLoops(rounded);
  assert.deepEqual(refusals, []);
  const off = offsetChain(loops[0].chain, 0.25);
  assert.ok(!("error" in off), `the contour engine would refuse this profile: ${JSON.stringify(off)}`);
});
