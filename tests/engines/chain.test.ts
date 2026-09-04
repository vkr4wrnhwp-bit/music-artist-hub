import test from "node:test";
import assert from "node:assert/strict";
import { chainLength, chainMoves, offsetChain, rectangleChain, type Chain } from "@/lib/engines/cam/chain";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { isArc } from "@/lib/engines/cam/arc";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool } from "@/lib/domain/shop";

/**
 * CHAINED CONTOUR BOUNDARIES
 *
 * `contourToolpath` hard-coded `rectMoves(moves, 0, 0, w, l, cr, …)`. An
 * OUTSIDE_CONTOUR carried width, length and one corner radius, so every
 * profiled part in the system was a centred rectangle with four equal corners
 * — and a part that is an L, or a D, or a plate with a flat on one side, was
 * cut as a rectangle with nothing saying so.
 */

/* ---------------- The rectangle, as a chain ---------------- */

test("a rounded rectangle chain is tangent-continuous and closed", () => {
  const c = rectangleChain(5, 3, 0.375);
  // Eight segments: four sides and four corner arcs.
  assert.equal(c.segments.length, 8);
  assert.deepEqual(c.segments[c.segments.length - 1].to, c.start, "the chain does not close");
});

test("a rectangle's perimeter is measured round the corners, not across them", () => {
  // 2(w + l) describes the bounding box. The profile is shorter by the corners.
  const w = 5;
  const l = 3;
  const r = 0.375;
  const measured = chainLength(rectangleChain(w, l, r));
  const boxed = 2 * (w + l);
  const expected = boxed - 8 * r + 2 * Math.PI * r;
  assert.ok(Math.abs(measured - expected) < 1e-9, `${measured} against ${expected}`);
  assert.ok(measured < boxed, "the profile is not shorter than its bounding box");
});

test("a sharp-cornered rectangle is four lines", () => {
  const c = rectangleChain(4, 2, 0);
  assert.equal(c.segments.length, 4);
  assert.ok(c.segments.every((s) => s.kind === "LINE"));
});

/* ---------------- Offsetting ---------------- */

const offset = (c: Chain, r: number) => {
  const o = offsetChain(c, r);
  assert.ok(!("error" in o), "error" in o ? o.error.reason : "");
  if ("error" in o) throw new Error("unreachable");
  return o;
};

test("offsetting a tangent chain needs no joins", () => {
  // Most real profiles are tangent-continuous — that is what a fillet is for —
  // and their offsets meet by themselves.
  const c = rectangleChain(5, 3, 0.375);
  assert.equal(offset(c, 0.25).segments.length, c.segments.length);
});

test("the offset of a rounded rectangle is the rectangle grown by the tool radius", () => {
  const o = offset(rectangleChain(5, 3, 0.375), 0.25);
  const xs = [o.start.x, ...o.segments.map((s) => s.to.x)];
  assert.ok(Math.abs(Math.max(...xs) - (2.5 + 0.25)) < 1e-9, `reaches X${Math.max(...xs)}`);
  // And its corner arcs grew by the same amount, so the wall stays parallel.
  const arc = o.segments.find((s) => s.kind === "ARC")!;
  assert.equal(arc.kind, "ARC");
});

test("a sharp convex corner gains a pivot arc", () => {
  // The offsets leave a gap at a sharp outside corner and the tool pivots
  // across it. Four corners, four extra arcs.
  const o = offset(rectangleChain(4, 2, 0), 0.25);
  assert.equal(o.segments.length, 8, "the pivot arcs are missing");
  assert.equal(o.segments.filter((s) => s.kind === "ARC").length, 4);
});

test("a sharp inside corner is refused, with the radius the tool would leave", () => {
  /*
   * Engineering rather than laziness: a round tool cannot produce a sharp
   * inside corner. It leaves a radius and the drawing has to say so.
   */
  const notch: Chain = {
    start: { x: -2, y: -1 },
    segments: [
      { kind: "LINE", to: { x: 2, y: -1 } },
      { kind: "LINE", to: { x: 2, y: 1 } },
      { kind: "LINE", to: { x: 0, y: 1 } },
      { kind: "LINE", to: { x: 0, y: 0 } }, // into the notch
      { kind: "LINE", to: { x: -2, y: 0 } }, // and along its floor: sharp inside corner
      { kind: "LINE", to: { x: -2, y: -1 } },
    ],
  };
  const o = offsetChain(notch, 0.25);
  assert.ok("error" in o, "a sharp inside corner was offset anyway");
  if (!("error" in o)) return;
  assert.match(o.error.reason, /sharp inside corner/);
  assert.match(o.error.reason, /R0\.2500 radius/);
  assert.ok(o.error.recommendations.some((r) => /corner radius of at least/i.test(r)));
});

test("an inside arc smaller than the tool is refused by name", () => {
  // The same rule that already refuses a pocket corner tighter than the
  // cutter, generalised to a chain.
  const dish: Chain = {
    start: { x: -0.1, y: 0 },
    segments: [
      // A clockwise arc is an inside radius when the profile runs
      // counter-clockwise: offsetting right shrinks it.
      { kind: "ARC", to: { x: 0.1, y: 0 }, center: { x: 0, y: 0 }, cw: true },
      { kind: "LINE", to: { x: -0.1, y: 0 } },
    ],
  };
  const o = offsetChain(dish, 0.25);
  assert.ok("error" in o, "a 0.100 inside radius accepted a 0.500 cutter");
  if (!("error" in o)) return;
  assert.match(o.error.reason, /smaller than the ⌀0\.5000" cutter/);
});

/* ---------------- Moves ---------------- */

test("chain moves emit arcs for arcs and lines for lines", () => {
  const moves = chainMoves(rectangleChain(5, 3, 0.375), -0.1, 20);
  assert.equal(moves.filter((m) => isArc(m)).length, 4);
  assert.equal(moves.filter((m) => !isArc(m)).length, 4);
});

/* ---------------- End to end through the toolpath engine ---------------- */

const stock: Stock = { form: "RECTANGULAR", x: 8, y: 6, z: 1, material: "Aluminum 6061" };
const endmill = {
  id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "1/2 3FL", diameter: 0.5,
  cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1, overallLength: 3, stickout: 1.5,
  holder: "CAT40 ER32", holderNoseDiameter: 1.5, maxRPM: 8100, recommendedMaterials: [],
  chiploadMin: 0.001, chiploadMax: 0.004, sfmMin: 400, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
  condition: "GOOD", regrindCount: 0,
} as unknown as Tool;
const ctx: MachiningContext = {
  tool: endmill, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
};
const req: OperationRequest = {
  id: "op", type: "CONTOUR_2D", label: "profile", featureId: "f1", toolId: "t2", setupId: "s",
  pass: "FINISH", topZ: 0, finalZ: -0.2, clearanceZ: 0.1, retractZ: 1,
};

const feature = (over: Record<string, unknown> = {}) =>
  ({
    id: "f1", kind: "OUTSIDE_CONTOUR", label: "Outside profile", functionalRole: "NONE", critical: false,
    width: 5, length: 3, cornerRadius: 0.375, depth: 0.2, ...over,
  }) as unknown as Feature;

test("a feature with no chain is still cut as the rectangle it describes", () => {
  // Absent means the profile IS that rectangle, which is what most plate work
  // is. Nothing about an existing part changes.
  const r = generateToolpath(req, feature(), ctx, stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const xs = r.toolpath.moves.filter((m) => m.program).map((m) => m.program!.x);
  assert.ok(Math.abs(Math.max(...xs) - 2.5) < 1e-9, "the programmed boundary is not the feature's own");
});

test("a chained profile is cut as given, not as its bounding rectangle", () => {
  /*
   * A plate with a flat cut across one corner. As a rectangle it would be cut
   * square, and the flat would still be there when the part came off.
   */
  const chamfered = feature({
    chainStart: { x: -2.5, y: -1.5 },
    chain: [
      { kind: "LINE", to: { x: 2.5, y: -1.5 } },
      { kind: "LINE", to: { x: 2.5, y: 0.9 } },
      { kind: "LINE", to: { x: 1.9, y: 1.5 } }, // the flat
      { kind: "LINE", to: { x: -2.5, y: 1.5 } },
      { kind: "LINE", to: { x: -2.5, y: -1.5 } },
    ],
  });
  const r = generateToolpath(req, chamfered, ctx, stock);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  if (!r.ok) return;

  const pts = r.toolpath.moves.filter((m) => m.program).map((m) => m.program!);
  // The flat's own endpoints are in the program.
  assert.ok(pts.some((p) => Math.abs(p.x - 1.9) < 1e-9 && Math.abs(p.y - 1.5) < 1e-9), "the flat is not cut");
  // And no programmed point sits in the corner the flat removes.
  assert.equal(
    pts.some((p) => p.x > 2.4 && p.y > 1.4),
    false,
    "the profile was cut square through the flat",
  );
});

test("material removed is measured round the profile, not round its bounding box", () => {
  /*
   * The caller a mutation slipped past: chainLength was tested and the engine
   * that uses it was not. Two profiles with identical width and length — one
   * a plain rectangle, one with a corner cut off — removed exactly the same
   * amount of material while `2 * (width + length)` stood in for the
   * perimeter. That figure feeds tool wear, cost and the cycle estimate.
   */
  const plain = generateToolpath(req, feature({ cornerRadius: 0 }), ctx, stock);
  const flat = generateToolpath(
    req,
    feature({
      cornerRadius: 0,
      chainStart: { x: -2.5, y: -1.5 },
      chain: [
        { kind: "LINE", to: { x: 2.5, y: -1.5 } },
        { kind: "LINE", to: { x: 2.5, y: 0.5 } },
        { kind: "LINE", to: { x: 1.5, y: 1.5 } },
        { kind: "LINE", to: { x: -2.5, y: 1.5 } },
        { kind: "LINE", to: { x: -2.5, y: -1.5 } },
      ],
    }),
    ctx,
    stock,
  );
  assert.ok(plain.ok && flat.ok);
  if (!plain.ok || !flat.ok) return;
  assert.ok(
    flat.toolpath.materialRemoved < plain.toolpath.materialRemoved,
    `the shorter profile removed ${flat.toolpath.materialRemoved} against the rectangle's ${plain.toolpath.materialRemoved}`,
  );
});

test("a profile with an inside corner too tight for the tool refuses by name", () => {
  const notched = feature({
    chainStart: { x: -2.5, y: -1.5 },
    chain: [
      { kind: "LINE", to: { x: 2.5, y: -1.5 } },
      { kind: "LINE", to: { x: 2.5, y: 1.5 } },
      { kind: "LINE", to: { x: 0.5, y: 1.5 } },
      { kind: "LINE", to: { x: 0.5, y: 0.5 } },
      { kind: "LINE", to: { x: -0.5, y: 0.5 } },
      { kind: "LINE", to: { x: -0.5, y: 1.5 } },
      { kind: "LINE", to: { x: -2.5, y: 1.5 } },
      { kind: "LINE", to: { x: -2.5, y: -1.5 } },
    ],
  });
  const r = generateToolpath(req, notched, ctx, stock);
  assert.equal(r.ok, false, "a sharp inside corner produced a toolpath");
  if (r.ok) return;
  assert.match(r.error.reason, /sharp inside corner/);
  assert.match(r.error.reason, /Outside profile/);
});

test("a profile that starts on an arc is refused rather than compensated badly", () => {
  // Compensation cannot be brought on over an arc: a control either faults or
  // ramps the offset through the cut.
  const roundStart = feature({
    chainStart: { x: 1, y: 0 },
    chain: [
      { kind: "ARC", to: { x: -1, y: 0 }, center: { x: 0, y: 0 }, cw: false },
      { kind: "ARC", to: { x: 1, y: 0 }, center: { x: 0, y: 0 }, cw: false },
    ],
  });
  const r = generateToolpath(req, roundStart, ctx, stock);
  assert.equal(r.ok, false);
  if (r.ok) return;
  assert.match(r.error.reason, /starts on an arc/);
});
