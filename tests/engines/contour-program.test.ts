import test from "node:test";
import assert from "node:assert/strict";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { getPost, type PostContext } from "@/lib/engines/cam/post";
import { offsetChain, rectangleChain } from "@/lib/engines/cam/chain";
import { recognizeGeometry } from "@/lib/geometry/recognize";
import type { RawSegment } from "@/lib/geometry/loop";
import type { MachineProfile, Tool } from "@/lib/domain/shop";
import type { Stock } from "@/lib/domain/features";

/**
 * WHAT THE PROGRAM ACTUALLY SAYS FOR A PROFILED PART
 *
 * A plain 4 x 3 rectangle — the path every profiled part in CANVAS has always
 * taken — posted three of its four sides, emitted the straight right-hand edge
 * as an R0.2500 arc spanning 3 inches, and finished with four G3 blocks whose
 * start and end were the same point.
 *
 * A G2/G3 whose endpoint is where the tool already is, is a COMPLETE CIRCLE.
 * The control cuts it, at depth, in the corner of the part.
 *
 * The cause: the offset chain inserts a pivot arc at each sharp convex corner,
 * so it carries more segments than the boundary. The zip walked both with one
 * index, so from the first corner onward every boundary point landed on the
 * wrong centre move, and once the index ran past the end it clamped to the
 * closing point and emitted circles there.
 *
 * Nothing caught it because nothing read a posted program back as geometry.
 * These do.
 */

const machine = {
  manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20,
  maxSpindleRPM: 8100, maxFeed: 500, maxRapid: 1000,
} as unknown as MachineProfile;

const tool = {
  id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: '1/2" 3FL', diameter: 0.5,
  cornerRadius: 0, flutes: 3, fluteLength: 1.25, overallLength: 3, stickout: 1.6, maxRPM: 8100,
  chiploadMin: 0.002, chiploadMax: 0.005, sfmMin: 600, sfmMax: 1000, coolant: "FLOOD",
  material: "CARBIDE", holder: "ER32", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  minutesUsed: 0, partsCut: 0, expectedLifeMinutes: 240, costPerTool: 40, recommendedMaterials: [],
} as unknown as Tool;

const stock = { x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as unknown as Stock;

const ctx = {
  tool, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
};

const post = (moves: ReturnType<typeof generateToolpath>) => {
  if (!moves.ok) throw new Error(`refused: ${moves.error.reason}`);
  return getPost("haas-ngc-dev")!.emit([moves.toolpath], {
    programNumber: "1001", programName: "TEST", units: "IN", workOffset: "G54", machine,
    toolTable: [{ toolNumber: 2, description: '1/2" 3FL', lengthOffset: 2, diameterOffset: 2, diameter: 0.5 }],
    safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-09-04T00:00:00Z",
    origins: [{ setupId: "s1", name: "SETUP 1", workOffset: "G54", sentence: "x" }],
  } as PostContext);
};

const cut = (feature: Record<string, unknown>) =>
  post(
    generateToolpath(
      { id: "op", type: "CONTOUR_2D", label: "profile", featureId: "f", toolId: "t2", setupId: "s1",
        pass: "ROUGH", overrides: {}, topZ: 0, finalZ: -0.5, clearanceZ: 0.1, retractZ: 0.25 } as never,
      { id: "f", kind: "OUTSIDE_CONTOUR", label: "profile", critical: false, functionalRole: "NONE", ...feature } as never,
      ctx as never,
      stock,
    ),
  );

/** Every cutting block, with its coordinates parsed back out. */
function blocks(code: string) {
  return code
    .split("\n")
    .filter((l) => /^(G4[12] )?G[0123] X/.test(l))
    .map((l) => {
      const m = /X(-?[\d.]+) Y(-?[\d.]+)/.exec(l)!;
      const ij = /I(-?[\d.]+) J(-?[\d.]+)/.exec(l);
      return { line: l, x: Number(m[1]), y: Number(m[2]), arc: /\bG[23] /.test(l), i: ij ? Number(ij[1]) : null, j: ij ? Number(ij[2]) : null };
    });
}

/* ---------------- The circle in the corner ---------------- */

test("no arc in a posted profile is a full circle", () => {
  /*
   * The defect this file exists for. A G2/G3 whose endpoint is where the tool
   * already is sweeps a complete turn — the control cuts a circle of the pivot
   * radius into the corner of the part, at depth, and the program reads
   * plausibly.
   */
  for (const f of [
    { width: 4, length: 3, cornerRadius: 0, depth: 0.5 },
    { width: 4, length: 3, cornerRadius: 0.25, depth: 0.5 },
    { width: 2, length: 2, cornerRadius: 0, depth: 0.5 },
  ]) {
    const b = blocks(cut(f));
    for (let i = 1; i < b.length; i++) {
      if (!b[i].arc) continue;
      assert.ok(
        Math.hypot(b[i].x - b[i - 1].x, b[i].y - b[i - 1].y) > 1e-9,
        `full-circle arc at (${b[i].x}, ${b[i].y}) in a ${f.width} x ${f.length} profile: ${b[i].line}`,
      );
    }
  }
});

test("a posted profile carries no zero-length cutting block", () => {
  // Legal, and blocks a machinist single-blocking has to step past for nothing.
  const b = blocks(cut({ width: 4, length: 3, cornerRadius: 0, depth: 0.5 }));
  for (let i = 1; i < b.length; i++) {
    if (b[i].line.startsWith("G0") || b[i - 1].line.startsWith("G0")) continue;
    assert.ok(
      Math.hypot(b[i].x - b[i - 1].x, b[i].y - b[i - 1].y) > 1e-9,
      `zero-length block: ${b[i].line}`,
    );
  }
});

test("all four sides of a rectangle reach the program", () => {
  /*
   * Three did. The fourth was consumed by the misaligned zip, and what came out
   * in its place was an arc — so the part was profiled on three sides and had a
   * circle cut where the fourth should have been.
   */
  const b = blocks(cut({ width: 4, length: 3, cornerRadius: 0, depth: 0.5 })).filter((x) => !x.line.startsWith("G0"));
  // One depth pass is lead-in, four sides, lead-out.
  const corners = [
    [-2, -1.5], [2, -1.5], [2, 1.5], [-2, 1.5],
  ];
  for (const [x, y] of corners) {
    assert.ok(
      b.some((blk) => Math.abs(blk.x - x) < 1e-6 && Math.abs(blk.y - y) < 1e-6),
      `the program never reaches the corner (${x}, ${y})`,
    );
  }
});

test("a straight edge is never programmed as an arc", () => {
  /*
   * `G3 X2.0000 Y1.5000 I0.0000 J0.2500` from (2, -1.5) is a 3 inch move on a
   * quarter-inch radius — geometrically impossible, and the control alarms on
   * it or cuts something else. It was the right-hand side of the plate.
   */
  const b = blocks(cut({ width: 4, length: 3, cornerRadius: 0, depth: 0.5 }));
  for (let i = 1; i < b.length; i++) {
    if (!b[i].arc) continue;
    const chord = Math.hypot(b[i].x - b[i - 1].x, b[i].y - b[i - 1].y);
    const radius = Math.hypot(b[i].i!, b[i].j!);
    assert.ok(
      chord <= 2 * radius + 1e-6,
      `an arc of R${radius.toFixed(4)} spans a ${chord.toFixed(4)}" chord — no such arc exists: ${b[i].line}`,
    );
  }
});

/* ---------------- Why it works now ---------------- */

test("the offset says which segments it inserted", () => {
  // Inferring it was the bug. A sharp-cornered rectangle gains one pivot per
  // corner; a fully rounded one gains none, because the offsets already meet.
  const sharp = offsetChain(rectangleChain(4, 3, 0), 0.25);
  if ("error" in sharp) throw new Error("the rectangle could not be offset");
  assert.deepEqual(sharp.pivots, [1, 3, 5, 7], "the four corner pivots are not reported");
  assert.equal(sharp.segments.length, 8);

  const rounded = offsetChain(rectangleChain(4, 3, 0.5), 0.25);
  if ("error" in rounded) throw new Error("the rounded rectangle could not be offset");
  assert.deepEqual(rounded.pivots, [], "a tangent profile was given pivots it does not need");
});

test("a pivot is motion for the simulator and not a block for the program", () => {
  /*
   * With compensation active the control pivots the tool round the corner
   * itself. The move has to stay — the simulator and the collision checks need
   * to know where the cutter body goes — but it must not be emitted.
   */
  const r = generateToolpath(
    { id: "op", type: "CONTOUR_2D", label: "profile", featureId: "f", toolId: "t2", setupId: "s1",
      pass: "ROUGH", overrides: {}, topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 0.25 } as never,
    { id: "f", kind: "OUTSIDE_CONTOUR", label: "profile", critical: false, functionalRole: "NONE",
      width: 4, length: 3, cornerRadius: 0, depth: 0.25 } as never,
    ctx as never,
    stock,
  );
  assert.ok(r.ok);
  if (!r.ok) throw new Error("unreachable");
  const pivots = r.toolpath.moves.filter((m) => m.program?.pivot);
  assert.equal(pivots.length, 4, "the pivot moves are not in the toolpath for the simulator");
  // And none of them reaches the program.
  const code = post(r);
  const b = blocks(code);
  for (const p of pivots) {
    assert.equal(
      b.some((blk) => Math.abs(blk.x - p.x) < 1e-9 && Math.abs(blk.y - p.y) < 1e-9 && blk.arc),
      false,
      `a pivot arc at (${p.x}, ${p.y}) was emitted as a block`,
    );
  }
});

/* ---------------- A real imported part ---------------- */

test("an L-bracket imported from a DXF posts as an L", () => {
  /*
   * The end of the whole road: `Feature.chain` was written by nothing, so this
   * part would have been cut as a 4 x 3 rectangle — square across the notch,
   * through whatever was meant to sit in it.
   *
   * Inside corner radiused R0.375 so a 1/2" cutter can make it; a sharp one is
   * refused by the offset, which is correct and is its own test.
   */
  const L: RawSegment[] = [
    { kind: "LINE", a: { x: 0, y: 0 }, b: { x: 4, y: 0 } },
    { kind: "LINE", a: { x: 4, y: 0 }, b: { x: 4, y: 1.5 } },
    { kind: "LINE", a: { x: 4, y: 1.5 }, b: { x: 1.875, y: 1.5 } },
    { kind: "ARC", a: { x: 1.875, y: 1.5 }, b: { x: 1.5, y: 1.875 }, center: { x: 1.875, y: 1.875 }, cw: true },
    { kind: "LINE", a: { x: 1.5, y: 1.875 }, b: { x: 1.5, y: 3 } },
    { kind: "LINE", a: { x: 1.5, y: 3 }, b: { x: 0, y: 3 } },
    { kind: "LINE", a: { x: 0, y: 3 }, b: { x: 0, y: 0 } },
  ];
  const rec = recognizeGeometry(L, { depth: 0.5 });
  assert.deepEqual(rec.refusals, []);

  const code = cut({ ...rec.profile!.parameters, chain: rec.profile!.chain, chainStart: rec.profile!.chainStart });
  const b = blocks(code).filter((x) => !x.line.startsWith("G0"));

  // The notch is the point: the program has to go IN to x = 1.5, not straight
  // across the top at x = 4.
  for (const [x, y] of [[4, 0], [4, 1.5], [1.875, 1.5], [1.5, 1.875], [1.5, 3], [0, 3]]) {
    assert.ok(
      b.some((blk) => Math.abs(blk.x - x) < 1e-6 && Math.abs(blk.y - y) < 1e-6),
      `the L-bracket program never reaches (${x}, ${y}) — it was cut as a rectangle`,
    );
  }
  // The inside fillet goes out as a real arc, clockwise on a CCW outline.
  const fillet = b.find((blk) => blk.arc && Math.abs(blk.x - 1.5) < 1e-6 && Math.abs(blk.y - 1.875) < 1e-6);
  assert.ok(fillet, "the inside fillet is not an arc in the program");
  assert.ok(/^G2 /.test(fillet!.line), `the inside fillet turns the wrong way: ${fillet!.line}`);
  assert.ok(Math.abs(Math.hypot(fillet!.i!, fillet!.j!) - 0.375) < 1e-6, "the fillet radius is not R0.375");

  // And it is still a compensated program on the boundary, not the centre.
  assert.match(code, /G42 D2 /);
});
