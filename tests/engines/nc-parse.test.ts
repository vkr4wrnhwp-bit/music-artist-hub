import { test } from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { getPost } from "@/lib/engines/cam/post";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool, MachineProfile } from "@/lib/domain/shop";

/**
 * Phase 4A/4B of the NC optimizer. What is pinned: modal interpretation,
 * unit conversion, arc endpoints, honest refusals, the never-retime tapping
 * flag — and the self-consistency test: the parser must read the programs
 * CANVAS's own posts emit, with zero refusals.
 */

test("modal motion and absolute coordinates: sticky G1, G0 rapids", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG1 Z-0.1 F10\nX2\nY1\nG0 Z1");
  assert.equal(p.refusals.length, 0);
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.equal(cuts.length, 3); // plunge + two sticky-G1 moves
  assert.equal(cuts[1].x1, 2);
  assert.equal(cuts[2].y1, 1);
  assert.equal(p.segments.filter((s) => s.kind === "RAPID").length, 2);
});

test("G21 converts to inches; G91 incremental accumulates", () => {
  const p = parseNC("G21 G91\nG0 X0 Y0 Z0\nG1 X25.4 F254\nX25.4");
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.ok(Math.abs(cuts[0].x1 - 1) < 1e-9);
  assert.ok(Math.abs(cuts[1].x1 - 2) < 1e-9);
  assert.ok(Math.abs((cuts[0].feed ?? 0) - 10) < 1e-9);
});

test("arcs land exactly on their endpoint and stay on radius", () => {
  const p = parseNC("G20 G90\nG0 X1 Y0 Z0\nG3 X-1 Y0 I-1 J0 F20");
  const arcs = p.segments.filter((s) => s.kind === "ARC");
  assert.ok(arcs.length >= 2);
  const last = arcs[arcs.length - 1];
  assert.ok(Math.abs(last.x1 - -1) < 1e-9 && Math.abs(last.y1) < 1e-9);
  for (const a of arcs) assert.ok(Math.abs(Math.hypot(a.x1, a.y1) - 1) < 0.002);
});

test("macros refuse with the line number; nothing after is interpreted", () => {
  const p = parseNC("G20\nG1 X1 F10\n#100 = 5\nG1 X9 F10");
  assert.equal(p.refusals.length, 1);
  assert.equal(p.refusals[0].line, 3);
  assert.ok(!p.segments.some((s) => s.x1 === 9));
});

test("G84 tapping segments carry the never-retime flag", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG84 Z-0.5 R0.1 F40\nG80");
  assert.ok(p.segments.some((s) => s.tapping && s.feed === 40));
  assert.ok(p.warnings.some((w) => /never be retimed/.test(w)));
});

test("G83 expands pecks that reach depth", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG83 Z-0.6 R0.1 Q0.25 F8\nG80");
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.ok(cuts.length >= 3);
  assert.ok(Math.abs(Math.min(...cuts.map((s) => s.z1)) - -0.6) < 1e-9);
});

test("self-consistency: the parser reads CANVAS's own Haas output with zero refusals", () => {
  const stock: Stock = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "AL" };
  const tool = {
    id: "t", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "em", diameter: 0.5, cornerRadius: 0,
    flutes: 3, material: "CARBIDE", fluteLength: 1.25, overallLength: 3, stickout: 1.6, holder: "CAT40",
    holderNoseDiameter: 1.75, maxRPM: 8100, recommendedMaterials: [], chiploadMin: 0.002, chiploadMax: 0.005,
    sfmMin: 600, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  } as unknown as Tool;
  const ctx: MachiningContext = { tool, materialSfmMin: 600, materialSfmMax: 1000, materialName: "AL", rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500 };
  const feature = { id: "f", kind: "RECT_POCKET", label: "P", functionalRole: "NONE", critical: false, centerX: 0, centerY: 0, width: 3, length: 2, depth: 0.25, cornerRadius: 0.25, top: 0 } as unknown as Feature;
  const req: OperationRequest = { id: "op", type: "POCKET_2D", label: "P", featureId: "f", toolId: "t", setupId: "s", topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 1 };
  const r = generateToolpath(req, feature, ctx, stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const machine = { id: "m", manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20, maxSpindleRPM: 8100, spindleTaper: "CAT40", maxFeed: 500, rapidRate: 1000, toolCapacity: 20, hasToolChanger: true, accuracy: 0.0002 } as unknown as MachineProfile;
  const nc = getPost("haas-ngc-dev")!.emit([r.toolpath], {
    programNumber: "1", programName: "t", machine, workOffset: "G54", units: "IN",
    toolTable: [{ toolNumber: 2, description: "em", lengthOffset: 2, diameter: 0.5 }],
    safeZ: 1, partName: "t", revision: "A", generatedAtIso: "2026-08-10T00:00:00Z",
  });
  const p = parseNC(nc);
  assert.equal(p.refusals.length, 0, JSON.stringify(p.refusals));
  assert.ok(p.segments.length > 50);
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 2: 0.5 }, rapidRate: 1000 });
  // Same arithmetic as the engine's own cycle time, so the totals must agree
  // to within the parsing round-trip.
  assert.ok(Math.abs(a.cutMinutes - r.toolpath.cycleTimeMinutes) / r.toolpath.cycleTimeMinutes < 0.25,
    `parsed ${a.cutMinutes} vs engine ${r.toolpath.cycleTimeMinutes}`);
});

test("air cutting is replay-proven: a repeated pass over removed material is air", () => {
  const prog = "G20 G90\nG0 X-2 Y0 Z0.2\nG1 Z-0.1 F5\nG1 X2 F20\nG0 Z0.2\nG0 X-2\nG1 Z-0.1 F5\nG1 X2 F20";
  const p = parseNC(prog);
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 0: 0.5 }, rapidRate: 600 });
  // BOTH the repeated pass and its re-plunge are air — the first pass already
  // cut the plunge point to depth. The replay is more thorough than the test
  // first assumed, which is exactly what a replay is for.
  const air = a.findings.filter((f) => f.kind === "AIR_CUTTING");
  assert.equal(air.length, 2, JSON.stringify(a.findings));
  assert.ok(air.every((f) => f.verdict === "CONFIDENT"));
  assert.deepEqual(air.map((f) => f.line).sort(), [7, 8]);
});

test("without stock nothing rises above REVIEW; unknown tools say INSUFFICIENT_DATA", () => {
  const prog = "G20 G90\nG0 X0 Y0 Z0.2\nG1 X3 F10";
  const p = parseNC(prog);
  const noStock = analyzeNC(p, { stock: null, toolDiameters: {}, rapidRate: 600 });
  assert.ok(noStock.findings.every((f) => f.verdict !== "CONFIDENT"));
  const cut = parseNC("G20 G90\nT7 M6\nG0 X0 Y0 Z0.2\nG1 Z-0.2 F5\nG1 X2 F20");
  const noTool = analyzeNC(cut, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: {}, rapidRate: 600 });
  assert.ok(noTool.findings.some((f) => f.kind === "UNKNOWN_CONTEXT" && f.verdict === "INSUFFICIENT_DATA"));
});

test("slow linking moves above the stock are found with the rapid-delta saving", () => {
  const p = parseNC("G20 G90\nG0 X-3 Y0 Z0.5\nG1 X3 F10");
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 0: 0.5 }, rapidRate: 600 });
  const slow = a.findings.find((f) => f.kind === "SLOW_LINKING_MOVE");
  assert.ok(slow);
  assert.ok(slow!.seconds > 30); // 6" at F10 is 36s; a rapid is under a second
});
