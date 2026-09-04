import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { planApproach } from "@/lib/engines/machinist";
import { minimumInternalRadius } from "@/lib/domain/features";
import { FEATURE_KINDS } from "@/lib/domain/features";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * THE LAST TWO KINDS NOTHING LOOKED AT.
 *
 * A sweep of all fifteen feature kinds through the planner found two still
 * silently dropped. A FILLET appeared nowhere in any engine: it did not
 * constrain tool selection, it was not cut, and it raised no concern — so a
 * drawing calling R0.0625 pocket corners got whatever radius the pocket's own
 * `cornerRadius` allowed, which is how a part comes back with corners four
 * times too big for whatever has to sit in them. A STEP had no toolpath and no
 * plan branch at all, though it is an ordinary facing cut over a strip.
 */

const tool = (d: number): Tool =>
  ({
    id: "em", toolNumber: 2, toolClass: "FLAT_END_MILL", description: `end mill ⌀${d}`, diameter: d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 2, overallLength: 4, stickout: 3,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  }) as unknown as Tool;

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

const step = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "s1", kind: "STEP", label: "Mounting step", side: "XMIN", width: 0.5, depth: 0.25, top: 0,
    functionalRole: "NONE", critical: false, ...over,
  }) as unknown as Feature;

const fillet = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "fi1", kind: "FILLET", label: "Corner fillets", radius: 0.0625, applyTo: "POCKET_CORNERS",
    functionalRole: "NONE", critical: false, ...over,
  }) as unknown as Feature;

const ctx = (d: number, partFeatures: Feature[] = []): MachiningContext => ({
  tool: tool(d), partFeatures, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const req = (over: Partial<OperationRequest> = {}): OperationRequest =>
  ({
    id: "o1", type: "STEP_MILL", label: "step", featureId: "s1", toolId: "em", setupId: "s", pass: "ROUGH",
    overrides: {}, topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 1, ...over,
  }) as unknown as OperationRequest;

/* ---------------- The step ---------------- */

test("a step is cut from its edge to its wall and no further", () => {
  /*
   * ⌀0.500 tool, 0.500" step off the −X edge of a 6.000 plate. The wall is at
   * X−2.500; the cutter centre runs from X−3.250 — a radius past the edge —
   * to X−2.750, a radius short of the wall. The cut lands exactly on both.
   */
  const r = generateToolpath(req(), step(), ctx(0.5), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const cutting = r.toolpath.moves.filter((m) => m.z < -0.001);
  const xs = cutting.map((m) => m.x);
  assert.ok(Math.abs(Math.min(...xs) + 3.25) < 1e-9, `cut in from X${Math.min(...xs)}`);
  assert.ok(Math.abs(Math.max(...xs) + 2.75) < 1e-9, `cut to X${Math.max(...xs)}, past the wall at X-2.500`);
  // Across the part and off both ends, because a step is open on its own side.
  const ys = cutting.map((m) => m.y);
  assert.ok(Math.min(...ys) < -2, "the cutter does not roll off the end of the part");
  assert.ok(Math.max(...ys) > 2);
});

test("every side is cut on its own side", () => {
  const sides = [
    { side: "XMIN", axis: "x" as const, from: -3.25, to: -2.75 },
    { side: "XMAX", axis: "x" as const, from: 2.75, to: 3.25 },
    { side: "YMIN", axis: "y" as const, from: -2.25, to: -1.75 },
    { side: "YMAX", axis: "y" as const, from: 1.75, to: 2.25 },
  ];
  for (const s of sides) {
    const r = generateToolpath(req(), step({ side: s.side }), ctx(0.5), STOCK);
    assert.ok(r.ok, `${s.side}: ${r.ok ? "" : r.error.reason}`);
    const v = r.toolpath.moves.filter((m) => m.z < -0.001).map((m) => m[s.axis]);
    assert.ok(Math.abs(Math.min(...v) - s.from) < 1e-9, `${s.side} cut from ${Math.min(...v)}, want ${s.from}`);
    assert.ok(Math.abs(Math.max(...v) - s.to) < 1e-9, `${s.side} cut to ${Math.max(...v)}, want ${s.to}`);
  }
});

test("the material removed is the strip, not the plate", () => {
  // 0.500 wide × 4.000 across × 0.250 deep off the X edge; 6.000 across off Y.
  const x = generateToolpath(req(), step(), ctx(0.5), STOCK);
  const y = generateToolpath(req(), step({ side: "YMIN" }), ctx(0.5), STOCK);
  assert.ok(x.ok && y.ok);
  assert.equal(x.toolpath.materialRemoved, 0.5);
  assert.equal(y.toolpath.materialRemoved, 0.75);
});

test("a step is entered off the end of the part, never plunged into a corner", () => {
  /*
   * The cut is open on the side it runs along, which is what makes a step a
   * facing cut rather than a pocket. Every descent happens clear of the
   * material at one end.
   */
  const r = generateToolpath(req(), step(), ctx(0.5), STOCK);
  assert.ok(r.ok);
  for (const m of r.toolpath.moves.filter((m) => m.type === "PLUNGE")) {
    assert.ok(Math.abs(m.y) > 2, `plunged at Y${m.y}, inside the 4.000 plate`);
  }
});

test("a step of no width is refused", () => {
  const r = generateToolpath(req(), step({ width: 0 }), ctx(0.5), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /takes nothing off the edge/);
});

test("a step operation on anything else is refused", () => {
  const notStep = { ...step(), kind: "RECT_POCKET" } as unknown as Feature;
  const r = generateToolpath(req(), notStep, ctx(0.5), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /is a RECT_POCKET and is not a step/);
});

test("a step narrower than half the cutter says the tool is hanging off it", () => {
  const r = generateToolpath(req(), step({ width: 0.2 }), ctx(0.5), STOCK);
  assert.ok(r.ok);
  assert.ok(
    r.toolpath.warnings.some((w) => /the far side of the tool is doing nothing/.test(w)),
    r.toolpath.warnings.join(" | "),
  );
});

/* ---------------- The fillet ---------------- */

test("a fillet is an internal radius and constrains the cutter", () => {
  /*
   * It was invisible here. A part with R0.0625 fillets called out separately
   * from a pocket whose own corner reads R0.2500 was cut with a ⌀0.500 mill and
   * came back with corners four times too big for whatever had to sit in them.
   */
  const pocket = {
    id: "p1", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1,
    depth: 0.25, cornerRadius: 0.25, bottomRadius: 0, top: 0,
  } as unknown as Feature;
  assert.equal(minimumInternalRadius([pocket]), 0.25);
  assert.equal(minimumInternalRadius([pocket, fillet()]), 0.0625, "a fillet does not constrain the corner");
});

test("an outside fillet constrains nothing, because a cutter of any size goes round it", () => {
  assert.equal(minimumInternalRadius([fillet({ applyTo: "OUTSIDE_VERTICAL", radius: 0.01 })]), null);
});

/* ---------------- The plan ---------------- */

const plan = (features: Feature[], tools: Tool[] = [tool(0.5), tool(0.25)]) =>
  planApproach("MINIMUM_SETUPS", {
    stock: STOCK, features, tools, workholding: null, finishedHeight: 0.7,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
  });

test("a step is planned, and the engine can run what was planned", () => {
  const p = plan([step()]);
  const op = p.setups.flatMap((s) => s.operations).find((o) => o.featureId === "s1");
  assert.ok(op, `no operation for the step: [${p.concerns.join(" | ")}]`);
  assert.equal(op.type, "STEP_MILL");
  assert.match(op.rationale, /off the XMIN edge/);
  const r = generateToolpath(req({ type: op.type, finalZ: op.finalZ }), step(), ctx(0.5), STOCK);
  assert.ok(r.ok, `the plan produced an operation the engine refuses: ${r.ok ? "" : r.error.reason}`);
});

test("a step with no depth is a concern, not an operation", () => {
  const p = plan([step({ depth: undefined })]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "s1").length, 0);
  assert.ok(p.concerns.some((c) => /A step of unknown depth is a missing dimension/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a fillet says what makes it, rather than being silently dropped", () => {
  const p = plan([fillet()]);
  assert.ok(
    p.concerns.some((c) => /comes off the tool that cuts the corner/.test(c) && /R0\.0625 is now the smallest cutter radius/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
  const outside = plan([fillet({ applyTo: "OUTSIDE_VERTICAL" })]);
  assert.ok(outside.concerns.some((c) => /comes off the profile pass/.test(c)), `got [${outside.concerns.join(" | ")}]`);
});

/* ---------------- Nothing is dropped in silence ---------------- */

test("every feature kind either gets an operation or says why not", () => {
  /*
   * The sweep that found these two. SLOT was mis-routed, COUNTERBORE,
   * COUNTERSINK, BOSS, FILLET and STEP were dropped without a word, and a
   * tapped hole was drilled and never threaded — every one of them found by
   * asking this question of the whole vocabulary rather than of one kind.
   */
  const base = { functionalRole: "NONE", critical: false, top: 0 };
  const sample: Record<string, Record<string, unknown>> = {
    FACE: { depth: 0.0625 },
    RECT_POCKET: { centerX: 0, centerY: 0, width: 1.5, length: 1, depth: 0.25, cornerRadius: 0.25, bottomRadius: 0 },
    CIRC_POCKET: { centerX: 0, centerY: 0, diameter: 1.2, depth: 0.25, bottomRadius: 0, through: false },
    BORE: { centerX: 0, centerY: 0, diameter: 1.5, depth: 0.5, bottomRadius: 0, through: false },
    SLOT: { startX: -1, startY: 0, endX: 1, endY: 0, width: 0.5, depth: 0.2 },
    DRILLED_HOLE: { centerX: 0, centerY: 0, diameter: 0.201, depth: 0.5, through: false },
    TAPPED_HOLE: { centerX: 0, centerY: 0, diameter: 0.201, depth: 0.5, through: true, thread: "1/4-20 UNC" },
    COUNTERBORE: { centerX: 0, centerY: 0, diameter: 0.201, depth: 0.75, through: true, headDiameter: 0.4, headDepth: 0.26 },
    COUNTERSINK: { centerX: 0, centerY: 0, diameter: 0.201, depth: 0.75, through: true, headDiameter: 0.42, countersinkAngle: 90 },
    CHAMFER: { width: 0.03, angle: 45, applyTo: "OUTSIDE_TOP" },
    FILLET: { radius: 0.125, applyTo: "POCKET_CORNERS" },
    OUTSIDE_CONTOUR: { width: 5.5, length: 3.5, cornerRadius: 0.25, depth: 0.625 },
    ENGRAVING: { text: "CNV-001", centerX: 0, centerY: 1.5, height: 0.15, depth: 0.01 },
    BOSS: { centerX: 0, centerY: 0, diameter: 0.75, height: 0.25 },
    STEP: { side: "XMIN", width: 0.5, depth: 0.25 },
  };
  // A crib that can actually make every one of them, so what is under test is
  // whether the KIND is routed at all rather than whether a tool exists.
  const cls = (id: string, n: number, c: string, d: number, over: Partial<Tool> = {}): Tool =>
    ({ ...tool(d), id, toolNumber: n, toolClass: c, description: `${c} ⌀${d}`, ...over }) as unknown as Tool;
  const crib = [
    cls("fm", 1, "FACE_MILL", 2),
    cls("em50", 2, "FLAT_END_MILL", 0.5),
    cls("em25", 3, "FLAT_END_MILL", 0.25),
    cls("spot", 5, "SPOT_DRILL", 0.5, { pointAngle: 90, tipDiameter: 0 }),
    cls("d201", 6, "DRILL", 0.201, { pointAngle: 118, tipDiameter: 0 }),
    cls("cham", 8, "CHAMFER_MILL", 0.5, { pointAngle: 90, tipDiameter: 0.02 }),
    cls("csk", 9, "COUNTERSINK", 0.5, { pointAngle: 90, tipDiameter: 0.02 }),
    cls("bore", 10, "BORING_TOOL", 1.4),
    cls("tap", 11, "TAP", 0.25, { threadDesignation: "1/4-20 UNC", tapLeadThreads: 4 }),
    cls("eng", 12, "ENGRAVER", 0.125),
  ];
  const silent: string[] = [];
  for (const kind of FEATURE_KINDS) {
    const f = { id: "f1", kind, label: `test ${kind}`, ...base, ...sample[kind] } as unknown as Feature;
    const p = plan([f], crib);
    const ops = p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "f1").length;
    if (ops === 0 && !p.concerns.some((c) => c.includes(`test ${kind}`))) silent.push(kind);
  }
  assert.deepEqual(silent, [], `dropped without a word: ${silent.join(", ")}`);
});

test("a face with no face mill in the crib says so", () => {
  // The silence that survived longest, because a shop nearly always owns one.
  // Datum A is the surface everything else on the part is measured from.
  const p = plan([{ id: "f1", kind: "FACE", label: "Face top", depth: 0.0625, top: 0, functionalRole: "NONE", critical: false } as unknown as Feature], [tool(0.5)]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "f1").length, 0);
  assert.ok(
    p.concerns.some((c) => /nothing here establishes Datum A/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
});

test("the stage table has a rank for every operation type", () => {
  // Typed by OperationType, so the compiler asks for a stage the day a type is
  // added — this is the belt to that brace, and it is what caught SOFT_JAW.
  const seq = readFileSync("src/lib/engines/sequencing.ts", "utf8");
  const table = /FEATURE_STAGE: Record<OperationType, number> = \{[\s\S]*?\n\};/.exec(seq)!;
  assert.ok(/STEP_MILL: 1,/.test(table[0]), "a step has no stage");
});
