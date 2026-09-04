import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { TIP_CLEARANCE, chamferEdge, chamferGeometry, type ChamferTool } from "@/lib/engines/cam/chamfer";
import { isArc } from "@/lib/engines/cam/arc";
import { generateToolpath } from "@/lib/engines/cam/engine";
import type { MachiningContext, Move, OperationRequest } from "@/lib/engines/cam/types";
import type { ChamferFeature, Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";
import { planApproach } from "@/lib/engines/machinist";

/**
 * CHAMFER
 *
 * `chamferToolpath` ignored `feature.width` and `feature.angle` entirely. It
 * walked a rectangle around the STOCK outline — not the part — at a hard-coded
 * R0.1 corner, at whatever Z the plan happened to carry, with a tool whose
 * point angle nothing in the system recorded. A 0.030 × 45° chamfer and a
 * 0.005 × 60° chamfer produced the identical path. Where the feature applied to
 * HOLES it emitted a rapid, a plunge and a retract at X0 Y0 and nothing else:
 * three moves at the origin, `isPlaceholder: false`, no warning, and the
 * pre-flight counted it as an operation that had produced motion.
 *
 * Found by an independent audit, not by a test here. Locked principle 5.
 */

const CHAMFER_MILL: ChamferTool = {
  description: '1/2" 90° chamfer mill',
  diameter: 0.5,
  pointAngle: 90,
  tipDiameter: 0.02,
};

const cham = (over: Partial<ChamferFeature> = {}): ChamferFeature =>
  ({
    id: "ch1", kind: "CHAMFER", label: "Outside chamfer", width: 0.03, angle: 45,
    applyTo: "OUTSIDE_TOP", functionalRole: "NONE", critical: false, ...over,
  }) as ChamferFeature;

/* ---------------- The cone decides the angle ---------------- */

test("a 90° chamfer mill cuts a 45° chamfer and says so when asked for anything else", () => {
  /*
   * The flank of the cone IS the chamfer surface. No depth and no offset makes
   * a 90° tool cut a 30° chamfer, and a system that quietly cut 45° of the
   * right width would produce a part that measures correct on the width and is
   * the wrong shape.
   */
  assert.ok(!("error" in chamferGeometry(cham({ angle: 45 }), CHAMFER_MILL)));

  const wrong = chamferGeometry(cham({ angle: 30 }), CHAMFER_MILL);
  assert.ok("error" in wrong, "a 90° tool was allowed to cut a 30° chamfer");
  assert.match(wrong.error.reason, /45\.0° chamfer/);
  assert.match(wrong.error.reason, /no depth or offset changes it/);
  // 30° off the face needs a flank 30° off the face, which is 60° off the
  // axis, which is a 120° included tool.
  assert.ok(wrong.error.recommendations.some((r) => /120° included/.test(r)), wrong.error.recommendations.join(" | "));
});

test("a chamfer mill with no point angle recorded refuses rather than assuming 90", () => {
  // The overwhelming majority of chamfer mills are 90°, which is exactly why
  // assuming it is dangerous: the shop that owns the 82° one is the shop this
  // would cut a wrong part for.
  const e = chamferGeometry(cham(), { ...CHAMFER_MILL, pointAngle: undefined });
  assert.ok("error" in e);
  assert.match(e.error.reason, /no point angle recorded/);
  assert.match(e.error.reason, /a chamfer is cut by the tool's cone/);

  const f = chamferGeometry(cham(), { ...CHAMFER_MILL, tipDiameter: undefined });
  assert.ok("error" in f);
  assert.match(f.error.reason, /no tip diameter recorded/);

  const g = chamferGeometry(cham(), { ...CHAMFER_MILL, pointAngle: undefined, tipDiameter: undefined });
  assert.ok("error" in g);
  assert.match(g.error.reason, /no point angle or tip diameter recorded/);
});

test("a chamfer with no width is not a chamfer", () => {
  const e = chamferGeometry(cham({ width: 0 }), CHAMFER_MILL);
  assert.ok("error" in e);
  assert.match(e.error.reason, /records no chamfer width/);
  // A break-edge is still a number, and the message says so rather than
  // letting somebody read "no width" as "just break it".
  assert.ok(e.error.recommendations.some((r) => /0\.005 × 45° is a number/.test(r)));
});

/* ---------------- The arithmetic ---------------- */

test("depth and offset come out of the geometry, not out of a constant", () => {
  /*
   * 0.030 × 45° with a 90° tool: the chamfer drops 0.030 (tan 45 = 1), the tip
   * runs TIP_CLEARANCE below that, and the centre sits a tip radius plus
   * clearance/tan 45 outside the finished boundary.
   */
  const g = chamferGeometry(cham({ width: 0.03, angle: 45 }), CHAMFER_MILL);
  assert.ok(!("error" in g));
  assert.equal(Number(g.drop.toFixed(6)), 0.03);
  assert.equal(Number(g.z.toFixed(6)), -(0.03 + TIP_CLEARANCE));
  assert.equal(Number(g.offset.toFixed(6)), Number((0.01 + TIP_CLEARANCE).toFixed(6)));

  // A different width is a different depth. The old code cut both at −0.030.
  const wide = chamferGeometry(cham({ width: 0.06, angle: 45 }), CHAMFER_MILL);
  assert.ok(!("error" in wide));
  assert.equal(Number(wide.z.toFixed(6)), Number((-(0.06 + TIP_CLEARANCE)).toFixed(6)));
  assert.notEqual(wide.z, g.z);
});

test("the flank lands on the chamfer, checked against the cone rather than the formula", () => {
  /*
   * The independent check: walk the cone the tool actually is, from the
   * position this says to put it in, and confirm its surface passes through
   * both ends of the chamfer the drawing asks for.
   *
   * Boundary at R, top face Z0, chamfer from (R − W, 0) to (R, −drop). The
   * cutter centre sits at R + offset; the flank facing the part is at
   * centre − radiusAt(height above the tip).
   */
  for (const [w, a] of [[0.03, 45], [0.01, 45], [0.05, 45]] as const) {
    const tool: ChamferTool = { ...CHAMFER_MILL, pointAngle: 2 * (90 - a) };
    const g = chamferGeometry(cham({ width: w, angle: a }), tool);
    assert.ok(!("error" in g), `${w} × ${a}`);
    const R = 2.75;
    const centre = R + g.offset;
    const flankAt = (z: number) => centre - g.radiusAt(z - g.z);
    assert.ok(Math.abs(flankAt(0) - (R - w)) < 1e-9, `${w} × ${a}: top of the chamfer is ${flankAt(0)}, want ${R - w}`);
    assert.ok(Math.abs(flankAt(-g.drop) - R) < 1e-9, `${w} × ${a}: bottom of the chamfer is ${flankAt(-g.drop)}, want ${R}`);
    // And below the chamfer the tool is clear of the wall rather than in it.
    assert.ok(flankAt(g.z) > R, `${w} × ${a}: the tool gouges the wall below the chamfer`);
  }
});

test("a shallower chamfer is a wider tool and the numbers follow it", () => {
  // 30° off the face needs a 120° included tool. Its flank is flatter, so the
  // same width drops less and the tool sits further out.
  const t30: ChamferTool = { ...CHAMFER_MILL, pointAngle: 120 };
  const g = chamferGeometry(cham({ width: 0.03, angle: 30 }), t30);
  assert.ok(!("error" in g));
  assert.equal(Number(g.drop.toFixed(6)), Number((0.03 * Math.tan(Math.PI / 6)).toFixed(6)));
  const R = 1;
  const flankAt = (z: number) => R + g.offset - g.radiusAt(z - g.z);
  assert.ok(Math.abs(flankAt(0) - (R - 0.03)) < 1e-9);
  assert.ok(Math.abs(flankAt(-g.drop) - R) < 1e-9);
});

/* ---------------- The edge it runs along ---------------- */

const contour = {
  id: "c1", kind: "OUTSIDE_CONTOUR", label: "Outside profile", width: 5.5, length: 3.5,
  cornerRadius: 0.25, depth: 0.625, functionalRole: "NONE", critical: false,
} as unknown as Feature;

const hole = (id: string, x: number, y: number): Feature =>
  ({ id, kind: "DRILLED_HOLE", label: `hole ${id}`, diameter: 0.25, depth: 0.5, centerX: x, centerY: y,
     functionalRole: "CLEARANCE", critical: false }) as unknown as Feature;

test("the outside chamfer follows the part, not the stock", () => {
  /*
   * The old path rang the STOCK outline. On the seeded bearing support the
   * stock is 6 × 4 and the finished profile is 5.5 × 3.5, so the pass cut air
   * a quarter of an inch outside the part for its entire length — and reported
   * material removed while doing it.
   */
  const e = chamferEdge(cham(), [contour]);
  assert.ok(!("error" in e) && e.kind === "BOUNDARY");
  assert.equal(e.label, "Outside profile");
  const xs = e.chain.segments.map((s) => s.to.x);
  assert.equal(Number(Math.max(...xs).toFixed(4)), 2.75, "the chamfer boundary is not the finished profile");
});

test("no outside profile on the part is a refusal, not a fallback to the stock", () => {
  const e = chamferEdge(cham(), [hole("h1", 0, 0)]);
  assert.ok("error" in e);
  assert.match(e.error.reason, /the only boundary available is the stock, which is not the part/);
});

test("a hole chamfer visits every hole", () => {
  const e = chamferEdge(cham({ applyTo: "HOLES" }), [contour, hole("h1", 1, 0), hole("h2", -1, 0), hole("h3", 0, 1)]);
  assert.ok(!("error" in e) && e.kind === "HOLES");
  assert.deepEqual(e.holes.map((h) => h.label).sort(), ["hole h1", "hole h2", "hole h3"]);
});

test("a hole chamfer with no holes says so rather than cutting at the origin", () => {
  const e = chamferEdge(cham({ applyTo: "HOLES" }), [contour]);
  assert.ok("error" in e);
  assert.match(e.error.reason, /no holes with a recorded diameter/);
});

test("a chamfer aimed at one feature cuts that one", () => {
  const e = chamferEdge(cham({ applyTo: "HOLES", targetFeatureId: "h2" }), [contour, hole("h1", 1, 0), hole("h2", -1, 0)]);
  assert.ok(!("error" in e) && e.kind === "HOLES");
  assert.deepEqual(e.holes.map((h) => h.label), ["hole h2"]);
});

/* ---------------- The toolpath ---------------- */

const tool = (over: Partial<Tool> = {}): Tool =>
  ({
    id: "t7", toolNumber: 7, toolClass: "CHAMFER_MILL", description: '1/2" 90° chamfer mill',
    diameter: 0.5, cornerRadius: 0, flutes: 4, material: "CARBIDE", fluteLength: 0.5,
    overallLength: 2.5, stickout: 1.1, holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8100,
    recommendedMaterials: [], chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 500, sfmMax: 900,
    coolant: "FLOOD", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
    pointAngle: 90, tipDiameter: 0.02, ...over,
  }) as unknown as Tool;

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

const ctx = (partFeatures: Feature[], t: Tool = tool()): MachiningContext => ({
  tool: t, partFeatures, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

// The default is the old hard-coded plan depth, so a test that does not name a
// depth still tells the engine's derived Z apart from the operation's.
const req = (finalZ = -0.03): OperationRequest =>
  ({
    id: "op1", type: "CHAMFER", label: "Chamfer Outside chamfer", featureId: "ch1", toolId: "t7",
    topZ: 0, finalZ, clearanceZ: 0.1, retractZ: 1, stepover: 0, stockToLeave: 0,
  }) as unknown as OperationRequest;

const cut = (moves: Move[]) => moves.filter((m) => m.type === "CUT");

test("the chamfer pass runs round the part at the derived depth", () => {
  const feature = cham();
  const r = generateToolpath(req(), feature, ctx([contour, feature]), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const cuts = cut(r.toolpath.moves);
  assert.ok(cuts.length >= 8, `only ${cuts.length} cutting moves`);
  // Every cut at one Z, and that Z is the geometry's.
  const zs = [...new Set(cuts.map((m) => Number(m.z.toFixed(6))))];
  assert.deepEqual(zs, [-(0.03 + TIP_CLEARANCE)]);
  // Round the finished profile plus the offset, not round the 6 × 4 stock.
  const maxX = Math.max(...cuts.map((m) => m.x));
  assert.ok(Math.abs(maxX - (2.75 + 0.01 + TIP_CLEARANCE)) < 1e-6, `pass runs to X${maxX}`);
  assert.ok(maxX < 3, "the pass is still out at the stock edge");
  assert.ok(r.toolpath.materialRemoved > 0);
});

test("the operation says when its planned depth was not the depth it cut", () => {
  // A depth typed into a plan cannot produce a chamfer of a stated width
  // except by coincidence, and a machinist reading Z−0.030 on the sheet and
  // Z−0.040 in the program needs to know which is the truth.
  const feature = cham();
  const r = generateToolpath(req(), feature, ctx([contour, feature]), STOCK);
  assert.ok(r.ok);
  assert.ok(
    r.toolpath.warnings.some((w) => /depth of a chamfer is set by its width and the tool's angle/.test(w)),
    r.toolpath.warnings.join(" | "),
  );
  // And at the derived depth it does not nag.
  const q = generateToolpath(req(-(0.03 + TIP_CLEARANCE)), feature, ctx([contour, feature]), STOCK);
  assert.ok(q.ok);
  assert.equal(q.toolpath.warnings.some((w) => /depth of a chamfer/.test(w)), false);
});

test("a hole chamfer cuts at every hole, not three moves at the origin", () => {
  /*
   * The shape this replaces: RAPID 0 0 0.1, PLUNGE 0 0 −0.03, RETRACT 0 0 1.
   * `isPlaceholder` false, no warning, and the pre-flight counted it as an
   * operation that had produced motion.
   */
  const feature = cham({ applyTo: "HOLES" });
  const holes = [hole("h1", 1, 0), hole("h2", -1, 0), hole("h3", 0, 1)];
  const r = generateToolpath(req(), feature, ctx([contour, feature, ...holes]), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const visited = new Set(r.toolpath.moves.filter((m) => m.type === "PLUNGE").map((m) => `${m.x},${m.y}`));
  assert.deepEqual([...visited].sort(), ["-1,0", "0,1", "1,0"]);
  assert.ok(r.toolpath.moves.some(isArc), "a hole big enough to interpolate was plunged");
  assert.equal(r.toolpath.isPlaceholder, false);
});

test("a hole too small to circle is plunged, and one the tip will not enter is refused", () => {
  const feature = cham({ applyTo: "HOLES" });
  // ⌀0.05: half of it is 0.025, and the centre offset is 0.02 — under the arc
  // floor, so the cone forms the whole chamfer on the way down.
  const tiny = { ...hole("h1", 0.5, 0), diameter: 0.05 } as unknown as Feature;
  const r = generateToolpath(req(), feature, ctx([contour, feature, tiny]), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  assert.equal(r.toolpath.moves.some(isArc), false, "a ⌀0.05 hole was interpolated");
  assert.ok(r.toolpath.moves.some((m) => m.type === "PLUNGE"));

  // ⌀0.015 against a 0.020 tip flat: the tool will not go in at all.
  const smaller = { ...hole("h1", 0.5, 0), diameter: 0.015 } as unknown as Feature;
  const q = generateToolpath(req(), feature, ctx([contour, feature, smaller]), STOCK);
  assert.equal(q.ok, false);
  assert.match(q.ok ? "" : q.error.reason, /will not enter the hole/);
});

test("an operation the chamfer engine refuses is an error, not a path", () => {
  // The whole point: no motion at all beats motion that is not the chamfer.
  const feature = cham({ angle: 30 });
  const r = generateToolpath(req(), feature, ctx([contour, feature]), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /45\.0° chamfer/);

  const noAngle = cham();
  const q = generateToolpath(req(), noAngle, ctx([contour, noAngle], tool({ pointAngle: undefined })), STOCK);
  assert.equal(q.ok, false);
  assert.match(q.ok ? "" : q.error.reason, /no point angle recorded/);
});

/* ---------------- The plan carries the same number ---------------- */

const CRIB = [tool(), tool({ id: "em", toolNumber: 2, toolClass: "FLAT_END_MILL", description: '1/2" end mill', pointAngle: undefined, tipDiameter: undefined })];

const planWith = (features: Feature[], crib: Tool[] = CRIB) =>
  planApproach("MINIMUM_SETUPS", {
    stock: STOCK,
    features,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
    tools: crib,
    workholding: null,
    finishedHeight: 0.7,
  });

test("the planned chamfer depth is the depth the engine will cut", () => {
  /*
   * `finalZ: -0.03` was hard-coded regardless of the chamfer's width or the
   * tool's angle. A machinist reads the plan and the setup sheet before the
   * control ever sees the program, and a depth on the sheet that the engine
   * then overrides is two numbers for one thing.
   */
  const feature = cham({ width: 0.05 });
  const ops = planWith([contour, feature]).setups.flatMap((s) => s.operations);
  const op = ops.find((o) => o.type === "CHAMFER");
  assert.ok(op, "no chamfer was planned");
  const geo = chamferGeometry(feature, tool());
  assert.ok(!("error" in geo));
  assert.equal(op.finalZ, geo.z);
  assert.notEqual(op.finalZ, -0.03, "the plan is back to the hard-coded depth");
});

test("a chamfer the crib cannot cut is a concern, not an operation", () => {
  // Planning an operation the engine is going to refuse produces a plan that
  // looks complete and a package that will not generate.
  const feature = cham({ angle: 30 });
  const p = planWith([contour, feature]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "CHAMFER").length, 0);
  assert.ok(p.concerns.some((c) => /Outside chamfer:.*45\.0° chamfer/.test(c)), `got [${p.concerns.join(" | ")}]`);

  // And a tool with no angle recorded is the same shape of answer.
  const plain = cham();
  const q = planWith([contour, plain], [tool({ pointAngle: undefined })]);
  assert.equal(q.setups.flatMap((s) => s.operations).filter((o) => o.type === "CHAMFER").length, 0);
  assert.ok(q.concerns.some((c) => /no point angle recorded/.test(c)), `got [${q.concerns.join(" | ")}]`);
});

test("no chamfer mill in the crib is said out loud", () => {
  const feature = cham();
  const p = planWith([contour, feature], [CRIB[1]]);
  assert.ok(p.concerns.some((c) => /no chamfer mill in the crib/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

/* ---------------- What the old code was ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the chamfer path is never derived from the stock outline", () => {
  const engine = strip(readFileSync("src/lib/engines/cam/engine.ts", "utf8"));
  const fn = /function chamferToolpath\([\s\S]*?\n\}/.exec(engine);
  assert.ok(fn, "chamferToolpath moved — this test cannot check it any more");
  // The window has to be the whole function or the guards below are vacuous.
  assert.ok(/chainLength\(path\)/.test(fn[0]), "the window does not reach the end of the function");
  assert.equal(/stock\./.test(fn[0]), false, "the chamfer is back to ringing the stock");
  assert.equal(/0\.1,/.test(fn[0]), false, "a hard-coded corner radius is back in the chamfer");
});

test("the planner and the engine ask one function for the depth", () => {
  // Two places computing a chamfer's Z is two places to drift, and the plan is
  // what a machinist reads before the program is what the machine runs.
  const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));
  assert.ok(/chamferGeometry\(f, chamfer\)/.test(planner), "the planner does not derive the chamfer depth");
  assert.equal(/finalZ: -0\.03,/.test(planner), false, "the planner is back to a hard-coded chamfer depth");
  assert.ok(/concerns\.push\(`\$\{f\.label\}: \$\{geo\.error\.reason\}`\)/.test(planner), "a refused chamfer is planned anyway");
});
