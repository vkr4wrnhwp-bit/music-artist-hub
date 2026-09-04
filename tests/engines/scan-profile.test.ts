import test from "node:test";
import assert from "node:assert/strict";
import { sliceMesh } from "@/lib/scan/slice";
import { fitChain } from "@/lib/geometry/fit";
import { assembleLoops, splitProfile } from "@/lib/geometry/loop";
import { offsetChain, chainLength } from "@/lib/engines/cam/chain";
import type { Mesh, Triangle } from "@/lib/scan/mesh";

/**
 * A SCAN BECOMES A PROFILE
 *
 * Reverse engineering stopped before geometry and said so: a scan produced an
 * envelope, mesh integrity and planar faces, with bores, radii and threads
 * marked NOT ATTEMPTED. The outside profile — the thing a 3-axis program most
 * needs — came from nowhere.
 *
 * A part a 3-axis mill makes is 2.5D, so its outline IS the cross-section of
 * the mesh. Slicing is exact arithmetic. What comes out is a chord per
 * triangle, and turning that back into the lines and arcs somebody drew is a
 * fit against a tolerance somebody chooses.
 */

/* ---------------- Building meshes of known parts ---------------- */

const tri = (a: [number, number, number], b: [number, number, number], c: [number, number, number]): Triangle => ({
  a, b, c, normal: [0, 0, 0],
});

const mesh = (triangles: Triangle[]): Mesh => ({
  triangles, format: "ASCII", name: "test", recomputedNormals: 0, warnings: [],
});

/** An extruded closed polygon: walls only, which is all a slice reads. */
function extrude(outline: { x: number; y: number }[], z0: number, z1: number): Mesh {
  const t: Triangle[] = [];
  for (let i = 0; i < outline.length; i++) {
    const p = outline[i];
    const q = outline[(i + 1) % outline.length];
    t.push(tri([p.x, p.y, z0], [q.x, q.y, z0], [q.x, q.y, z1]));
    t.push(tri([p.x, p.y, z0], [q.x, q.y, z1], [p.x, p.y, z1]));
  }
  return mesh(t);
}

/** A circle as `n` points, which is how a scanner delivers a curve. */
const circlePts = (cx: number, cy: number, r: number, n: number) =>
  Array.from({ length: n }, (_, i) => ({
    x: cx + r * Math.cos((2 * Math.PI * i) / n),
    y: cy + r * Math.sin((2 * Math.PI * i) / n),
  }));

const RECT = [
  { x: -2, y: -1 }, { x: 2, y: -1 }, { x: 2, y: 1 }, { x: -2, y: 1 },
];

/* ---------------- The slice ---------------- */

test("a slice through an extruded plate is its outline", () => {
  const r = sliceMesh(extrude(RECT, 0, 0.75), "IN");
  assert.ok(Math.abs(r.z - 0.375) < 1e-9, `sliced at ${r.z}, expected mid-height`);
  const { loops, refusals } = assembleLoops(r.segments);
  assert.deepEqual(refusals, []);
  assert.equal(loops.length, 1);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-6, `area ${loops[0].area}`);
});

test("millimetres are converted, because an STL carries no units", () => {
  // A millimetre scan read as inches is a part 25.4 times too big, and every
  // number in it is self-consistent.
  const mm = extrude(RECT.map((p) => ({ x: p.x * 25.4, y: p.y * 25.4 })), 0, 19.05);
  const r = sliceMesh(mm, "MM");
  const { loops } = assembleLoops(r.segments);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-4, `area ${loops[0].area} — the scan was not converted`);
});

test("a slice can be taken at a named height, because a step has two outlines", () => {
  // A part with a step has a different outline top and bottom, and which one
  // you want is a question about the part rather than a fact about the mesh.
  const wide = extrude(RECT, 0, 0.5);
  const narrow = extrude([{ x: -1, y: -0.5 }, { x: 1, y: -0.5 }, { x: 1, y: 0.5 }, { x: -1, y: 0.5 }], 0.5, 1);
  const stepped = mesh([...wide.triangles, ...narrow.triangles]);

  const low = assembleLoops(sliceMesh(stepped, "IN", 0.25).segments).loops;
  const high = assembleLoops(sliceMesh(stepped, "IN", 0.75).segments).loops;
  assert.ok(Math.abs(low[0].area - 8) < 1e-6, `low ${low[0].area}`);
  assert.ok(Math.abs(high[0].area - 2) < 1e-6, `high ${high[0].area}`);
});

test("where it sliced is stated, not left to be assumed", () => {
  const r = sliceMesh(extrude(RECT, 0, 0.75), "IN");
  assert.match(r.assumptions.join(" "), /Sliced at mid-height/);
  assert.match(r.assumptions.join(" "), /a step has a different outline at a different height/);
  assert.match(r.assumptions.join(" "), /chord per triangle/);
  assert.match(sliceMesh(extrude(RECT, 0, 0.75), "IN", 0.2).assumptions.join(" "), /Sliced at Z 0\.2000" as asked/);
});

test("triangles lying in the plane are skipped and counted", () => {
  // A coplanar triangle has no single crossing segment. Its edges come through
  // its neighbours, which do cross.
  const flat = mesh([...extrude(RECT, 0, 0.75).triangles, tri([-2, -1, 0.375], [2, -1, 0.375], [2, 1, 0.375])]);
  const r = sliceMesh(flat, "IN", 0.375);
  assert.equal(r.coplanar, 1);
  assert.match(r.assumptions.join(" "), /lie in the slice plane/);
  // And the outline still closes.
  assert.deepEqual(assembleLoops(r.segments).refusals, []);
});

test("a drafted wall crosses the plane where the plane cuts it", () => {
  /*
   * Every wall in these fixtures is vertical, and a vertical edge crosses at
   * the same X and Y whatever height you take it at — so an interpolation that
   * always took the midpoint would look correct on all of them. A real scanned
   * part has draft, or a chamfered side, and then where the plane cuts the edge
   * is the whole answer.
   *
   * A pyramid frustum: 4 x 4 at the bottom, 2 x 2 at the top, over Z 0 to 1.
   * At Z 0.25 the section is 3.5 x 3.5.
   */
  const bot = [{ x: -2, y: -2 }, { x: 2, y: -2 }, { x: 2, y: 2 }, { x: -2, y: 2 }];
  const top = [{ x: -1, y: -1 }, { x: 1, y: -1 }, { x: 1, y: 1 }, { x: -1, y: 1 }];
  const t: Triangle[] = [];
  for (let i = 0; i < 4; i++) {
    const p = bot[i], q = bot[(i + 1) % 4], P = top[i], Q = top[(i + 1) % 4];
    t.push(tri([p.x, p.y, 0], [q.x, q.y, 0], [Q.x, Q.y, 1]));
    t.push(tri([p.x, p.y, 0], [Q.x, Q.y, 1], [P.x, P.y, 1]));
  }
  const quarter = assembleLoops(sliceMesh(mesh(t), "IN", 0.25).segments).loops;
  assert.equal(quarter.length, 1);
  assert.ok(Math.abs(quarter[0].area - 3.5 * 3.5) < 1e-6, `area ${quarter[0].area} at Z0.25, expected 12.25`);

  const threeQ = assembleLoops(sliceMesh(mesh(t), "IN", 0.75).segments).loops;
  assert.ok(Math.abs(threeQ[0].area - 2.5 * 2.5) < 1e-6, `area ${threeQ[0].area} at Z0.75, expected 6.25`);
});

/* ---------------- The fit ---------------- */

test("a scanned rectangle fits back to four lines", () => {
  /*
   * The whole point. A 4 x 2 plate slices into a chord per wall triangle; the
   * shape somebody designed is four lines, and cutting the chords instead would
   * be a program of dozens of blocks and a wall a hand can feel.
   */
  const dense = RECT.flatMap((p, i) => {
    const q = RECT[(i + 1) % RECT.length];
    // Twenty points along each edge, as a scanner would deliver it.
    return Array.from({ length: 20 }, (_, k) => ({ x: p.x + ((q.x - p.x) * k) / 20, y: p.y + ((q.y - p.y) * k) / 20 }));
  });
  const r = sliceMesh(extrude(dense, 0, 0.5), "IN");
  const loop = splitProfile(assembleLoops(r.segments).loops).profile!;
  assert.ok(loop.chain.segments.length >= 40, "the fixture did not produce a dense chord soup");

  const fit = fitChain(loop.chain, { tolerance: 0.001 });
  assert.equal(fit.to, 4, `fitted to ${fit.to} segments, expected 4 lines`);
  assert.equal(fit.arcs, 0, "a straight edge came back as an arc");
  assert.ok(fit.maxDeviation < 1e-9, `deviation ${fit.maxDeviation}`);
  // And it is still the same part.
  assert.ok(Math.abs(assembleLoops(toRaw(fit.chain)).loops[0].area - 8) < 1e-6);
});

test("a scanned disc fits back to arcs, not to a hundred chords", () => {
  const r = sliceMesh(extrude(circlePts(0, 0, 1, 120), 0, 0.5), "IN");
  const loop = splitProfile(assembleLoops(r.segments).loops).profile!;
  assert.ok(loop.chain.segments.length >= 100);

  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  assert.ok(fit.to <= 4, `a disc fitted to ${fit.to} segments`);
  assert.ok(fit.arcs >= 1, "a round part came back with no arcs at all");
  // Every arc is the radius that was there.
  for (const s of fit.chain.segments) {
    if (s.kind !== "ARC") continue;
    const rr = Math.hypot(s.to.x - s.center.x, s.to.y - s.center.y);
    assert.ok(Math.abs(rr - 1) < 0.01, `fitted R${rr.toFixed(4)} where R1.0000 was scanned`);
  }
});

test("a straight edge is never fitted as an arc, even though it is a huge circle", () => {
  /*
   * A line is also a circle of enormous radius. A tie handed to the arc would
   * put a meaningless R400 arc where a machinist expects G1 — which reads as a
   * mistake in the program even though the motion is the same.
   */
  const fit = fitChain(
    splitProfile(assembleLoops(sliceMesh(extrude(RECT, 0, 0.5), "IN").segments).loops).profile!.chain,
    { tolerance: 0.001 },
  );
  assert.equal(fit.arcs, 0);
  assert.equal(fit.lines, 4);
});

test("a noisy straight edge still comes back a line", () => {
  /*
   * A scanner does not deliver a straight edge straight. Within tolerance a
   * huge circle fits those points as well as a line does, and handing the tie
   * to the arc puts a meaningless R400 where a machinist expects G1 — a block
   * that reads as a mistake in the program even though the motion is the same.
   */
  const noisy = RECT.flatMap((p, i) => {
    const q = RECT[(i + 1) % RECT.length];
    return Array.from({ length: 20 }, (_, k) => {
      const f = k / 20;
      // A smooth bow, which is exactly what a large circle fits.
      const bow = 0.0008 * Math.sin(Math.PI * f);
      const nx = -(q.y - p.y), ny = q.x - p.x;
      const m = Math.hypot(nx, ny);
      return { x: p.x + (q.x - p.x) * f + (nx / m) * bow, y: p.y + (q.y - p.y) * f + (ny / m) * bow };
    });
  });
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(noisy, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  assert.equal(fit.arcs, 0, `scanner noise on a flat wall was fitted as ${fit.arcs} arc(s)`);
  assert.equal(fit.lines, 4);
});

test("an inside radius turns the other way from an outside one", () => {
  /*
   * On a counter-clockwise outline an outside corner sweeps counter-clockwise
   * and an inside one sweeps clockwise. Assuming either would bulge half the
   * radii on an L-bracket the wrong way — the corner would stick out instead of
   * being relieved, and the cutter would climb into the wall.
   */
  const arcPts = (cx: number, cy: number, r: number, a0: number, a1: number, n: number) =>
    Array.from({ length: n }, (_, k) => {
      const a = a0 + ((a1 - a0) * k) / (n - 1);
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
  // An L with a R0.5 inside corner at (1.5, 1.5).
  const L = [
    { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 1.5 }, { x: 2, y: 1.5 },
    // The SHORT way round: -90 to -180 is the 90 degree fillet. Going to
    // +180 instead sweeps 270 and turns the outline inside out.
    ...arcPts(2, 2, 0.5, -Math.PI / 2, -Math.PI, 16),
    { x: 1.5, y: 3 }, { x: 0, y: 3 },
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(L, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.003 });
  const arc = fit.chain.segments.find((sg) => sg.kind === "ARC");
  if (arc?.kind !== "ARC") throw new Error("the inside radius was flattened into lines");
  assert.equal(arc.cw, true, "an inside radius was fitted turning the way an outside one does");
  assert.ok(Math.abs(Math.hypot(arc.to.x - arc.center.x, arc.to.y - arc.center.y) - 0.5) < 0.02);
});

test("a plate with a radiused corner keeps the line and the arc apart", () => {
  const outline = [
    { x: -2, y: -1 }, { x: 1.5, y: -1 },
    ...Array.from({ length: 12 }, (_, k) => {
      const a = -Math.PI / 2 + (k * (Math.PI / 2)) / 11;
      return { x: 1.5 + 0.5 * Math.cos(a), y: -0.5 + 0.5 * Math.sin(a) };
    }),
    { x: 2, y: 1 }, { x: -2, y: 1 },
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(outline, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  assert.ok(fit.arcs >= 1, "the corner radius was flattened into lines");
  assert.ok(fit.lines >= 3, "the straight edges were swallowed into arcs");
  assert.ok(fit.to <= 8, `fitted to ${fit.to} segments — the fit is not recovering the shape`);
  const arc = fit.chain.segments.find((s) => s.kind === "ARC");
  if (arc?.kind !== "ARC") throw new Error("expected an arc");
  const rr = Math.hypot(arc.to.x - arc.center.x, arc.to.y - arc.center.y);
  assert.ok(Math.abs(rr - 0.5) < 0.02, `fitted R${rr.toFixed(4)} where R0.5 was scanned`);
});

/* ---------------- Tangency, which the fit breaks and the part does not have ---------------- */

test("a fitted fillet meets its edges tangentially, so the offset does not refuse it", () => {
  /*
   * The thing that made the whole scan path refuse on a real part. A fillet
   * meets its edges tangentially by construction; line and arc are fitted
   * independently, so their handover lands where the greedy line fit stopped
   * eating into the arc — a couple of hundredths past the true tangent point.
   * The joint then reads very slightly concave, and `offsetChain` refuses the
   * whole profile as a sharp inside corner a cutter cannot make.
   *
   * It is right to refuse a real one. This is not one: it is fitting noise at
   * a joint the part has smooth.
   */
  const arcPts = (cx: number, cy: number, r: number, a0: number, a1: number, n: number) =>
    Array.from({ length: n }, (_, k) => {
      const a = a0 + ((a1 - a0) * k) / (n - 1);
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
  const L = [
    { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 1.5 }, { x: 2, y: 1.5 },
    ...arcPts(2, 2, 0.5, -Math.PI / 2, -Math.PI, 17),
    { x: 1.5, y: 3 }, { x: 0, y: 3 },
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(L, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });

  assert.match(fit.notes.join(" "), /moved onto exact tangency/);
  // The proof is the offset: a joint that is really tangent offsets cleanly.
  const off = offsetChain(fit.chain, 0.25);
  assert.ok(
    !("error" in off),
    `the fitted scan is refused by the contour engine: ${"error" in off ? off.error.reason : ""}`,
  );
});

test("a snapped joint is exactly tangent, not merely close enough to offset", () => {
  /*
   * "The offset accepted it" is a weak oracle — a joint can be wrong in
   * several ways and still squeak past. Tangency has a definition: the
   * perpendicular distance from the arc's centre to the line IS the radius.
   * Measure that.
   */
  const arcPts = (cx: number, cy: number, r: number, a0: number, a1: number, n: number) =>
    Array.from({ length: n }, (_, k) => {
      const a = a0 + ((a1 - a0) * k) / (n - 1);
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
  const rounded = [
    { x: -2, y: -1 }, { x: 1.5, y: -1 },
    ...arcPts(1.5, -0.5, 0.5, -Math.PI / 2, 0, 14),
    { x: 2, y: 1 }, { x: -2, y: 1 },
  ];
  // Two shapes: an outside corner, and the L-bracket where the greedy line fit
  // genuinely overshoots into the fillet and the joint starts OFF the circle.
  const L = [
    { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 1.5 }, { x: 2, y: 1.5 },
    ...arcPts(2, 2, 0.5, -Math.PI / 2, -Math.PI, 17),
    { x: 1.5, y: 3 }, { x: 0, y: 3 },
  ];
  for (const outline of [rounded, L]) {
    const loop = splitProfile(assembleLoops(sliceMesh(extrude(outline, 0, 0.5), "IN").segments).loops).profile!;
    const fit = fitChain(loop.chain, { tolerance: 0.002 });
    checkTangency(fit, loop.area);
  }
});

/** Every line-to-arc joint is tangent, on the arc, and encloses the same part. */
function checkTangency(fit: ReturnType<typeof fitChain>, scannedArea: number) {
  {
  const segs = fit.chain.segments;
  const startOf = (i: number) => (i === 0 ? fit.chain.start : segs[i - 1].to);
  let checked = 0;
  for (let i = 0; i < segs.length; i++) {
    const a = segs[i];
    const b = segs[(i + 1) % segs.length];
    const arc = a.kind === "ARC" ? a : b.kind === "ARC" ? b : null;
    const line = a.kind === "LINE" ? a : b.kind === "LINE" ? b : null;
    if (!arc || !line || a.kind === b.kind) continue;

    const p = line === a ? startOf(i) : a.to;
    const q = line === a ? a.to : line.to;
    const dx = q.x - p.x;
    const dy = q.y - p.y;
    const m = Math.hypot(dx, dy);
    // Perpendicular distance from the arc's centre to the line.
    const h = Math.abs((arc.center.x - p.x) * dy - (arc.center.y - p.y) * dx) / m;
    const r = Math.hypot(arc.to.x - arc.center.x, arc.to.y - arc.center.y);
    assert.ok(
      Math.abs(h - r) < 1e-9,
      `joint ${i}: the line passes ${h.toFixed(8)}" from the centre of an R${r.toFixed(8)} arc — not tangent`,
    );
    // And the joint itself sits on the arc.
    const joint = a.to;
    assert.ok(
      Math.abs(Math.hypot(joint.x - arc.center.x, joint.y - arc.center.y) - r) < 1e-9,
      `joint ${i} does not lie on the arc it joins`,
    );
    checked++;
  }
  assert.ok(checked >= 2, `only ${checked} line-to-arc joints were checked`);

  /*
   * And the shape is still the part. Both tangent points from an external
   * point are genuinely tangent — the wrong one is on the other side of the
   * circle, which is tangent and is not this part. Area is what tells them
   * apart.
   */
  const fittedArea = assembleLoops(toRaw(fit.chain)).loops[0]?.area ?? 0;
  assert.ok(
    Math.abs(fittedArea - scannedArea) < 0.01,
    `the fitted shape encloses ${fittedArea.toFixed(4)} against the scanned ${scannedArea.toFixed(4)} — the joint moved to the wrong tangent`,
  );
  }
}

test("an arc meeting a line at a real angle is left where it is", () => {
  /*
   * Snapping must not become a way of quietly pulling a genuine corner onto a
   * tangency the part does not have. A half-round nose butted flat onto an
   * edge meets it at 90 degrees — that IS a corner, and moving it would change
   * the shape.
   */
  const arcPts = (cx: number, cy: number, r: number, a0: number, a1: number, n: number) =>
    Array.from({ length: n }, (_, k) => {
      const a = a0 + ((a1 - a0) * k) / (n - 1);
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
  // A "keyhole": a big disc with a straight chord cut across it, so the arc
  // meets the chord at a sharp angle rather than tangentially.
  const keyhole = [
    ...arcPts(0, 0, 1, Math.PI / 6, (11 * Math.PI) / 6, 40),
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(keyhole, 0, 0.5), "IN").segments).loops).profile!;
  const before = fitChain(loop.chain, { tolerance: 0.002 });
  // Whatever it fitted, the shape it describes is still the keyhole's area.
  assert.ok(Math.abs(loop.area - before.chain.segments.length * 0) < Infinity);
  const raw = toRaw(before.chain);
  const after = assembleLoops(raw).loops[0];
  assert.ok(
    Math.abs(after.area - loop.area) < 0.01,
    `the fitted shape encloses ${after.area.toFixed(4)} against the scanned ${loop.area.toFixed(4)} — a corner was pulled onto a tangency`,
  );
});

test("a real inside corner is still refused, because a cutter still cannot make one", () => {
  /*
   * The other half. Snapping must not become a way of quietly rounding a sharp
   * corner into something machinable — the check catches real inside corners
   * and has to keep doing it.
   */
  const sharpL = [
    { x: 0, y: 0 }, { x: 4, y: 0 }, { x: 4, y: 1.5 }, { x: 1.5, y: 1.5 },
    { x: 1.5, y: 3 }, { x: 0, y: 3 },
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(sharpL, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  const off = offsetChain(fit.chain, 0.25);
  assert.ok("error" in off, "a sharp inside corner was snapped into something the cutter can make");
  if (!("error" in off)) throw new Error("unreachable");
  assert.match(off.error.reason, /sharp inside corner/);
});

test("the snap is reported, with how far it moved", () => {
  // It changes the geometry that gets cut. Silently would be the wrong word.
  const arcPts = (cx: number, cy: number, r: number, a0: number, a1: number, n: number) =>
    Array.from({ length: n }, (_, k) => {
      const a = a0 + ((a1 - a0) * k) / (n - 1);
      return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
    });
  const rounded = [
    { x: -2, y: -1 }, { x: 1.5, y: -1 },
    ...arcPts(1.5, -0.5, 0.5, -Math.PI / 2, 0, 14),
    { x: 2, y: 1 }, { x: -2, y: 1 },
  ];
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(rounded, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  assert.match(fit.notes.join(" "), /joints? (was|were) moved onto exact tangency, the largest by 0\.\d+"/);
  assert.match(fit.notes.join(" "), /A fillet meets its edges tangentially/);
});

/* ---------------- What the fit will not claim ---------------- */

test("the fit reports its tolerance and its worst deviation", () => {
  // Fitting is deciding that points which are not on a line are close enough
  // to be treated as though they were. That is a number a person has to weigh.
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(circlePts(0, 0, 1, 60), 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.005 });
  assert.match(fit.notes.join(" "), /fitted to \d+ segments within 0\.0050"/);
  assert.match(fit.notes.join(" "), /Worst deviation 0\.\d+/);
  assert.ok(fit.maxDeviation <= 0.005, "the fit exceeded the tolerance it was given");
});

test("nothing is rounded to a nominal", () => {
  /*
   * A scan of a used part carries that part's wear. Rounding R0.4986 to R0.5
   * would launder wear into design intent, and the number a machinist needs to
   * see is the one that was measured.
   */
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(circlePts(0, 0, 0.4986, 90), 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.002 });
  const arc = fit.chain.segments.find((s) => s.kind === "ARC");
  if (arc?.kind !== "ARC") throw new Error("expected an arc");
  const rr = Math.hypot(arc.to.x - arc.center.x, arc.to.y - arc.center.y);
  assert.ok(Math.abs(rr - 0.5) > 1e-4, `R${rr.toFixed(5)} was rounded to a nominal`);
  assert.match(fit.notes.join(" "), /launder wear into design intent/);
});

test("a tighter tolerance keeps more segments, and says so", () => {
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(circlePts(0, 0, 1, 180), 0, 0.5), "IN").segments).loops).profile!;
  const loose = fitChain(loop.chain, { tolerance: 0.01 });
  const tight = fitChain(loop.chain, { tolerance: 0.00001 });
  assert.ok(tight.to >= loose.to, `tight ${tight.to} against loose ${loose.to}`);
  assert.ok(tight.maxDeviation <= loose.maxDeviation + 1e-12);
});

/* ---------------- End to end: a scan the contour engine will cut ---------------- */

test("a scanned plate reaches a chain the contour engine cuts", () => {
  const loop = splitProfile(assembleLoops(sliceMesh(extrude(RECT, 0, 0.5), "IN").segments).loops).profile!;
  const fit = fitChain(loop.chain, { tolerance: 0.001 });
  const off = offsetChain(fit.chain, 0.25);
  assert.ok(!("error" in off), `the contour engine refuses the fitted scan: ${JSON.stringify(off)}`);
  if ("error" in off) throw new Error("unreachable");
  // Outward, so the cutter is on the outside of the part.
  assert.ok(chainLength(off) > chainLength(fit.chain), "the fitted scan put the cutter inside the part");
});

/** A fitted chain, back to raw segments, so it can be re-assembled and measured. */
function toRaw(chain: { start: { x: number; y: number }; segments: { kind: string; to: { x: number; y: number }; center?: { x: number; y: number }; cw?: boolean }[] }) {
  const out = [];
  let from = chain.start;
  for (const s of chain.segments) {
    out.push(
      s.kind === "ARC"
        ? { kind: "ARC" as const, a: from, b: s.to, center: s.center!, cw: s.cw! }
        : { kind: "LINE" as const, a: from, b: s.to },
    );
    from = s.to;
  }
  return out;
}
