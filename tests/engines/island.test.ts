import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { annulusOf, footprintOf, islandsIn, overlaps, standing } from "@/lib/engines/cam/island";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { planApproach } from "@/lib/engines/machinist";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * A POCKET MACHINED AWAY ANYTHING STANDING IN IT.
 *
 * A pocket toolpath sweeps its whole area. On a 3.000 × 2.000 pocket with a
 * ⌀0.750 locating boss at its centre, 66 of the 188 moves were inside the boss
 * and the helical entry started at the boss's own centre. The boss was machined
 * away, the operation reported real motion, and nothing said a word.
 *
 * The coverage gate caught the wrong half of it: a BOSS with no operation reads
 * as "not cut", and a machinist looking at a feature they want LEFT STANDING
 * could reasonably record it as not made by this program — which clears the
 * gate and leaves the program still cutting it away.
 */

const tool = (d: number): Tool =>
  ({
    id: "em", toolNumber: 2, toolClass: "FLAT_END_MILL", description: `end mill ⌀${d}`, diameter: d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1.5, overallLength: 4, stickout: 2.5,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  }) as unknown as Tool;

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

const rectPocket = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "p1", kind: "RECT_POCKET", label: "Relief pocket", centerX: 0, centerY: 0, width: 3, length: 2,
    depth: 0.25, cornerRadius: 0.25, bottomRadius: 0, top: 0, functionalRole: "NONE", critical: false, ...over,
  }) as unknown as Feature;

const circPocket = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "p1", kind: "CIRC_POCKET", label: "Sealing land", centerX: 0, centerY: 0, diameter: 2.5,
    depth: 0.2, top: 0, bottomRadius: 0, through: false, functionalRole: "SEAL", critical: false, ...over,
  }) as unknown as Feature;

const boss = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "b1", kind: "BOSS", label: "Locating boss", centerX: 0, centerY: 0, diameter: 0.75, height: 0.25,
    functionalRole: "LOCATING", critical: true, ...over,
  }) as unknown as Feature;

const ctx = (d: number, partFeatures: Feature[]): MachiningContext => ({
  tool: tool(d), partFeatures, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const req = (over: Partial<OperationRequest> = {}): OperationRequest =>
  ({
    id: "o1", type: "POCKET_2D", label: "pocket", featureId: "p1", toolId: "em", setupId: "s", pass: "ROUGH",
    overrides: {}, topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 1, ...over,
  }) as unknown as OperationRequest;

/* ---------------- Footprints ---------------- */

test("a boss is the thing that has to survive the cut", () => {
  const fs = [rectPocket(), boss(), circPocket({ id: "p2" })];
  assert.deepEqual(standing(fs).map((f) => f.id), ["b1"]);
});

test("a circle and a rectangle overlap when they share any area", () => {
  const rect = footprintOf(rectPocket())!;
  assert.equal(overlaps(rect, footprintOf(boss())!), true, "a boss at the pocket centre does not overlap it");
  // Clear of the pocket in X.
  assert.equal(overlaps(rect, footprintOf(boss({ centerX: 2 }))!), false);
  // Just touching the wall, from outside — the corner case that decides
  // whether a cut is refused.
  assert.equal(overlaps(rect, footprintOf(boss({ centerX: 1.5 + 0.375 + 0.001 }))!), false);
  assert.equal(overlaps(rect, footprintOf(boss({ centerX: 1.5 + 0.375 - 0.001 }))!), true);
  // Two circles, and two rectangles.
  assert.equal(overlaps(footprintOf(circPocket())!, footprintOf(boss())!), true);
  assert.equal(overlaps(rect, footprintOf(rectPocket({ centerX: 3.5 }))!), false);
  assert.equal(overlaps(rect, footprintOf(rectPocket({ centerX: 2.5 }))!), true);
});

test("a feature with no footprint is not an island and does not have one", () => {
  const chamfer = { id: "c", kind: "CHAMFER", label: "edge", width: 0.03, angle: 45, applyTo: "OUTSIDE_TOP" } as unknown as Feature;
  assert.equal(footprintOf(chamfer), null);
  assert.deepEqual(islandsIn(chamfer, [boss()]), []);
});

/* ---------------- The one case that needs no clipping ---------------- */

test("a round island concentric in a round pocket is an annulus", () => {
  const a = annulusOf(circPocket(), boss({ diameter: 1.2 }))!;
  assert.equal(a.outerDiameter, 2.5);
  assert.equal(a.innerDiameter, 1.2);
});

test("anything else is not an annulus and is not pretended to be one", () => {
  // Off centre by more than a machining thou.
  assert.equal(annulusOf(circPocket(), boss({ centerX: 0.002 })), null);
  // A round island in a rectangular pocket.
  assert.equal(annulusOf(rectPocket(), boss()), null);
  // An island no smaller than the pocket is not an island.
  assert.equal(annulusOf(circPocket(), boss({ diameter: 2.5 })), null);
  // Concentric to a thou still is one — that is a real setup, not a mistake.
  assert.ok(annulusOf(circPocket(), boss({ centerX: 0.0009 })));
});

/* ---------------- What the engine does ---------------- */

test("a pocket refuses rather than machining a boss away", () => {
  const fs = [rectPocket(), boss()];
  const r = generateToolpath(req(), fs[0], ctx(0.25, fs), STOCK);
  assert.equal(r.ok, false, "the pocket cut straight through the boss");
  assert.match(r.ok ? "" : r.error.reason, /Locating boss stands inside Relief pocket/);
  assert.match(r.ok ? "" : r.error.reason, /would machine it away/);
  assert.match(r.ok ? "" : r.error.reason, /island avoidance, which this engine does not have/);
  // And it says what a person could do about it.
  assert.ok((r.ok ? [] : r.error.recommendations).some((x) => /not made by this program/.test(x)));
});

test("more than one island is refused by name", () => {
  const fs = [rectPocket(), boss(), boss({ id: "b2", label: "Second boss", centerX: 1 })];
  const r = generateToolpath(req(), fs[0], ctx(0.25, fs), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /2 features standing in it — Locating boss, Second boss/);
});

test("a pocket with nothing standing in it is unchanged", () => {
  // The whole check has to be invisible on the overwhelming majority of
  // pockets, which have no islands at all.
  const withBoss = generateToolpath(req(), rectPocket(), ctx(0.25, [rectPocket(), boss({ centerX: 2.5 })]), STOCK);
  const without = generateToolpath(req(), rectPocket(), ctx(0.25, [rectPocket()]), STOCK);
  assert.ok(withBoss.ok && without.ok);
  assert.deepEqual(withBoss.toolpath.moves, without.toolpath.moves);
});

test("an annulus is cut in the band and nowhere near the island", () => {
  /*
   * The one arrangement that needs no clipping. A ⌀0.375 tool in a ⌀2.500
   * pocket round a ⌀1.200 spigot cuts between radius 0.7875 and 1.0625 — a
   * tool radius clear of each wall — and nothing enters the spigot.
   */
  const fs = [circPocket(), boss({ label: "Spigot", diameter: 1.2 })];
  const r = generateToolpath(req({ finalZ: -0.2 }), fs[0], ctx(0.375, fs), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const radii = r.toolpath.moves.filter((m) => m.z < -0.001).map((m) => Math.hypot(m.x, m.y));
  assert.ok(Math.min(...radii) >= 0.6 + 0.1875 - 1e-9, `cut in to r${Math.min(...radii)}, into the ⌀1.200 spigot`);
  assert.ok(Math.max(...radii) <= 1.25 - 0.1875 + 1e-9, `cut out to r${Math.max(...radii)}, past the pocket wall`);
  // The material removed is the annulus, not the whole circle.
  const annulusArea = Math.PI * (1.25 ** 2 - 0.6 ** 2) * 0.2;
  assert.ok(Math.abs(r.toolpath.materialRemoved - annulusArea) < 0.01, `${r.toolpath.materialRemoved} vs ${annulusArea}`);
});

test("the helix goes in the band, not into the island", () => {
  // With an island there is material on the axis, so a helix on centre would
  // plunge a non-centre-cutting tool straight into the boss.
  const fs = [circPocket(), boss({ label: "Spigot", diameter: 1.2 })];
  const r = generateToolpath(req({ finalZ: -0.2 }), fs[0], ctx(0.375, fs), STOCK);
  assert.ok(r.ok);
  const descending = r.toolpath.moves.filter((m, i) => i > 0 && m.z < r.toolpath.moves[i - 1].z - 1e-9);
  assert.ok(descending.length > 0);
  for (const m of descending) {
    assert.ok(Math.hypot(m.x, m.y) > 0.6, `descended at r${Math.hypot(m.x, m.y).toFixed(4)}, inside the spigot`);
  }
});

test("a band the tool cannot get into is refused", () => {
  const fs = [circPocket(), boss({ label: "Spigot", diameter: 1.2 })];
  const r = generateToolpath(req({ finalZ: -0.2 }), fs[0], ctx(0.75, fs), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /leaves a 0\.6400" band around Spigot and the tool is ⌀0\.7500/);
  assert.match(r.ok ? "" : r.error.reason, /no room to get in, let alone move/);
});

test("the island gets a finish pass of its own", () => {
  // It is a wall of the part, and the one the boss's own size is measured on.
  const fs = [circPocket(), boss({ label: "Spigot", diameter: 1.2 })];
  const r = generateToolpath(req({ finalZ: -0.2 }), fs[0], ctx(0.375, fs), STOCK);
  assert.ok(r.ok);
  const leads = r.toolpath.moves.filter((m) => m.type === "LEAD_IN");
  assert.ok(
    leads.some((m) => Math.abs(Math.hypot(m.x, m.y) - (0.6 + 0.1875)) < 1e-9),
    `finish leads at r${leads.map((m) => Math.hypot(m.x, m.y).toFixed(4)).join(", ")}`,
  );
});

/* ---------------- The plan ---------------- */

const plan = (features: Feature[], d = 0.25) =>
  planApproach("MINIMUM_SETUPS", {
    stock: STOCK, features, tools: [tool(d)], workholding: null, finishedHeight: 0.7,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
  });

test("a boss says how it is not made, rather than being silently dropped", () => {
  const p = plan([rectPocket(), boss()]);
  assert.ok(
    p.concerns.some((c) => /Locating boss stands inside Relief pocket/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
  // A boss on its own face is the same answer for the same reason.
  const alone = plan([boss({ centerX: 2 })]);
  assert.ok(alone.concerns.some((c) => /Nothing here will produce it/.test(c)), `got [${alone.concerns.join(" | ")}]`);
});

test("a pocket the engine will refuse is not planned", () => {
  // The same shape as the slot: a plan that reads complete and cannot run.
  const p = plan([rectPocket(), boss()]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "p1").length, 0);
});

test("the annulus IS planned, because the engine can cut it", () => {
  const p = plan([circPocket(), boss({ label: "Spigot", diameter: 1.2 })], 0.375);
  const ops = p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "p1");
  assert.ok(ops.length > 0, `the one island case that works was not planned: [${p.concerns.join(" | ")}]`);
});

/* ---------------- The shape that caused it ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the pocket engine asks what is standing in the pocket before it cuts", () => {
  const engine = strip(readFileSync("src/lib/engines/cam/engine.ts", "utf8"));
  const fn = /function pocketToolpath\([\s\S]*?\n\}/.exec(engine);
  assert.ok(fn, "pocketToolpath moved — this test cannot check it any more");
  assert.ok(/const area =/.test(fn[0]), "the window does not reach the end of the function");
  assert.ok(/islandsIn\(feature, ctx\.partFeatures\)/.test(fn[0]), "the pocket no longer looks for islands");
  // The check comes before any move is generated, not after.
  assert.ok(fn[0].indexOf("islandsIn(") < fn[0].indexOf("moves.push("), "moves are generated before the check runs");
});
