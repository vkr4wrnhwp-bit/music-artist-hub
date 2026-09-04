import { test } from "node:test";
import assert from "node:assert/strict";
import { generateToolpath } from "@/lib/engines/cam/engine";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool } from "@/lib/domain/shop";

/**
 * ADAPTIVE_2D contract: bounded radial engagement (15% of diameter) at full
 * axial depth, chip-thinning feed compensation capped by the machine, helical
 * entry, and refusals — never adaptations — when the premise does not hold.
 */

const stock: Stock = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" };

const endmill = {
  id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "1/2 3FL end mill", diameter: 0.5,
  cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 0.75, overallLength: 3, stickout: 1.4,
  holder: "CAT40", holderNoseDiameter: 1.75, maxRPM: 8100, recommendedMaterials: [],
  chiploadMin: 0.001, chiploadMax: 0.004, sfmMin: 600, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
  condition: "GOOD", regrindCount: 0,
} as unknown as Tool;

const ctx = (tool: Tool): MachiningContext => ({
  tool, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const rectPocket = {
  id: "f1", kind: "RECT_POCKET", label: "main pocket", functionalRole: "CLEARANCE", critical: false,
  centerX: 0, centerY: 0, width: 2, length: 3, cornerRadius: 0.375, depth: 0.6, through: false, top: 0,
} as unknown as Feature;
const circPocket = {
  id: "f2", kind: "CIRC_POCKET", label: "round pocket", functionalRole: "CLEARANCE", critical: false,
  centerX: 1, centerY: -0.5, diameter: 1.5, depth: 0.6, through: false, top: 0,
} as unknown as Feature;

const req = (finalZ = -0.6): OperationRequest => ({
  id: "op", type: "ADAPTIVE_2D", label: "adaptive", featureId: "f1", toolId: "t2", setupId: "s",
  topZ: 0, finalZ, clearanceZ: 0.1, retractZ: 1,
});

const AE = 0.5 * 0.15; // 15% of the 1/2" tool

test("rect pocket: full depth in a single pass, chip-thinned feed within the machine cap", () => {
  const r = generateToolpath(req(), rectPocket, ctx(endmill), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.ok(!r.toolpath.isPlaceholder);
  const cuts = r.toolpath.moves.filter((m) => m.type === "CUT");
  // Every cutting move is at final depth — there is no stepdown ladder.
  for (const m of cuts) assert.equal(m.z, -0.6);
  // Chip thinning raises feed above the programmed base, never above the machine.
  const cutFeed = cuts[cuts.length - 1].feed!;
  assert.ok(cutFeed > r.toolpath.parameters.feed, "chip-thinning compensation missing");
  assert.ok(cutFeed <= 500, "machine feed cap breached");
  // The outermost loop reaches the wall (tool-radius compensated).
  const maxX = Math.max(...cuts.map((m) => Math.abs(m.x)));
  assert.ok(Math.abs(maxX - (2 - 0.5) / 2) < 1e-6, "final loop must reach the pocket wall");
  // Removal is the whole pocket, not a per-loop guess.
  assert.ok(Math.abs(r.toolpath.materialRemoved - 2 * 3 * 0.6) < 1e-6);
  assert.match(r.toolpath.warnings[0], /15% radial engagement/);
});

test("rect pocket: successive boundary loops are spaced no wider than ae", () => {
  const r = generateToolpath(req(), rectPocket, ctx(endmill), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const cuts = r.toolpath.moves.filter((m) => m.type === "CUT");
  // Loop extents along the long axis, deduplicated and sorted.
  const extents = [...new Set(cuts.map((m) => Math.abs(m.y).toFixed(6)))].map(Number).sort((a, b) => a - b);
  const half = [...new Set(cuts.map((m) => Math.abs(m.x).toFixed(6)))].map(Number).sort((a, b) => a - b);
  const loopHalves = half.filter((v) => v > 1e-9);
  for (let i = 1; i < loopHalves.length; i++) {
    assert.ok(loopHalves[i] - loopHalves[i - 1] <= AE + 1e-6, "radial step exceeds the engagement bound");
  }
  assert.ok(extents.length > 2, "expected multiple loops");
});

test("circular pocket: spiral stays inside the wall and closes with a full ring at it", () => {
  const r = generateToolpath(req(), circPocket, ctx(endmill), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const cuts = r.toolpath.moves.filter((m) => m.type === "CUT" || m.type === "ARC");
  const maxR = 1.5 / 2 - 0.25;
  let seen = 0;
  for (const m of cuts) {
    const rad = Math.hypot(m.x - 1, m.y - -0.5);
    assert.ok(rad <= maxR + 1e-6, "cut outside the pocket wall");
    if (Math.abs(rad - maxR) < 1e-6) seen++;
  }
  assert.ok(seen > 8, "closing ring at the wall missing");
  // The engine rounds removal figures to 4 decimals.
  assert.ok(Math.abs(r.toolpath.materialRemoved - Math.PI * 0.75 ** 2 * 0.6) < 1e-3);
});

test("helical entry descends monotonically to depth — no straight plunge", () => {
  const r = generateToolpath(req(), circPocket, ctx(endmill), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const plunges = r.toolpath.moves.filter((m) => m.type === "PLUNGE");
  assert.ok(plunges.length > 10, "helical entry missing");
  let last = Infinity;
  for (const m of plunges) {
    assert.ok(m.z <= last + 1e-9, "entry helix climbed");
    assert.ok(Math.hypot(m.x - 1, m.y - -0.5) > 1e-9, "straight plunge at centre");
    last = m.z;
  }
  assert.equal(plunges[plunges.length - 1].z, -0.6);
});

test("depth beyond the flute length is refused, not stepped down", () => {
  const r = generateToolpath(req(-0.9), rectPocket, ctx(endmill), stock);
  assert.ok(!r.ok);
  if (r.ok) return;
  assert.match(r.error.reason, /flute/);
});

test("wrong tool, wrong feature, undersized pocket and unfittable corner are refused", () => {
  const drill = { ...endmill, toolClass: "DRILL" } as Tool;
  assert.ok(!generateToolpath(req(), rectPocket, ctx(drill), stock).ok);

  const hole = { ...(rectPocket as object), kind: "TAPPED_HOLE" } as Feature;
  assert.ok(!generateToolpath(req(), hole, ctx(endmill), stock).ok);

  const tiny = { ...(rectPocket as object), width: 0.4, length: 0.4 } as Feature;
  assert.ok(!generateToolpath(req(), tiny, ctx(endmill), stock).ok);

  const sharp = { ...(rectPocket as object), cornerRadius: 0.2 } as Feature;
  assert.ok(!generateToolpath(req(), sharp, ctx(endmill), stock).ok);
});
