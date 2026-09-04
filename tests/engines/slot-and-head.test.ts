import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { planApproach } from "@/lib/engines/machinist";
import { isArc } from "@/lib/engines/cam/arc";
import type { MachiningContext, Move, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * THE FEATURE KINDS THE PLANNER SKIPPED
 *
 * SLOT sat in the pocket bucket, so every slot on a part got a POCKET_2D
 * operation and the pocket engine then refused it — "is a SLOT and cannot be
 * machined with a 2D pocket operation". A plan that reads complete, produces an
 * operation, and cannot run. The machinist reads the plan; the refusal only
 * appears at export.
 *
 * COUNTERBORE and COUNTERSINK sat in no bucket at all. No operation, no
 * concern, total silence on a feature whose whole point is that a screw head
 * has to sit in it — caught only by the coverage gate, three pages away.
 */

const tool = (o: { id: string; n: number; cls: string; d: number; over?: Partial<Tool> }): Tool =>
  ({
    id: o.id, toolNumber: o.n, toolClass: o.cls, description: `${o.cls} ⌀${o.d}`, diameter: o.d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1.5, overallLength: 4, stickout: 2.5,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0, ...o.over,
  }) as unknown as Tool;

const EM375 = tool({ id: "em375", n: 3, cls: "FLAT_END_MILL", d: 0.375 });
const EM50 = tool({ id: "em50", n: 4, cls: "FLAT_END_MILL", d: 0.5 });
const D201 = tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201, over: { pointAngle: 118, tipDiameter: 0 } });
const D266 = tool({ id: "d266", n: 7, cls: "DRILL", d: 0.266, over: { pointAngle: 118, tipDiameter: 0 } });
const CS82 = tool({ id: "cs82", n: 8, cls: "COUNTERSINK", d: 0.5, over: { pointAngle: 82, tipDiameter: 0.02 } });

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

const ctx = (t: Tool, partFeatures: Feature[] = []): MachiningContext => ({
  tool: t, partFeatures, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const req = (over: Partial<OperationRequest> = {}): OperationRequest =>
  ({
    id: "op1", type: "SLOT_MILL", label: "op", featureId: "f1", toolId: "t", setupId: "s", pass: "ROUGH",
    overrides: {}, topZ: 0, finalZ: -0.2, clearanceZ: 0.1, retractZ: 1, ...over,
  }) as unknown as OperationRequest;

const slot = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "f1", kind: "SLOT", label: "Keyway slot", startX: -1, startY: 0, endX: 1, endY: 0,
    width: 0.5, depth: 0.2, top: 0, functionalRole: "NONE", critical: false, ...over,
  }) as unknown as Feature;

/* ---------------- The slot ---------------- */

test("a slot is cut along its centreline, not as a rectangle", () => {
  const r = generateToolpath(req(), slot(), ctx(EM375), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const cuts = r.toolpath.moves.filter((m) => m.type === "CUT" || m.type === "LEAD_IN");
  assert.ok(cuts.length > 0);
  // The cutter's edge makes the round end, so its centre stops a radius short
  // of each end point rather than running off the end of the slot.
  const xs = r.toolpath.moves.map((m) => m.x);
  assert.ok(Math.min(...xs) >= -1 + 0.375 / 2 - 1e-9, `the tool ran to X${Math.min(...xs)}, past the end of the slot`);
  assert.ok(Math.max(...xs) <= 1 - 0.375 / 2 + 1e-9);
  assert.equal(r.toolpath.isPlaceholder, false);
});

test("a slot is ramped into, never plunged", () => {
  /*
   * A slot cannot be helixed into — at full width there is no room to swing —
   * and a standard end mill has no cutting edge at its centre. Ramping along
   * the slot's own length is what a machinist does instead.
   */
  const r = generateToolpath(req({ finalZ: -0.4 }), slot(), ctx(EM375), STOCK);
  assert.ok(r.ok);
  const moves = r.toolpath.moves;
  // Every descent below the top face happens on a move that also travels in X.
  const descents = moves.filter((m, i) => i > 0 && m.z < moves[i - 1].z - 1e-9 && m.z < -1e-9);
  assert.ok(descents.length > 0, "nothing descends into the cut");
  for (const [i, m] of moves.entries()) {
    if (i === 0 || m.z >= moves[i - 1].z - 1e-9 || m.z >= -1e-9) continue;
    assert.ok(
      Math.abs(m.x - moves[i - 1].x) > 1e-6,
      `the tool descends to Z${m.z.toFixed(4)} without moving along the slot — that is a plunge`,
    );
  }
});

test("the ramp is limited by the slot's own length, and says so", () => {
  // A short slot cannot ramp a full stepdown, and forcing it would plunge the
  // last of it into a tool nobody recorded as centre-cutting.
  const shortSlot = slot({ startX: -0.3, endX: 0.3, depth: 0.3 });
  const r = generateToolpath(req({ finalZ: -0.3 }), shortSlot, ctx(EM375), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  assert.ok(
    r.toolpath.warnings.some((w) => /3° ramp only reaches/.test(w)),
    r.toolpath.warnings.join(" | "),
  );
  assert.ok(r.toolpath.warnings.some((w) => /0\.2250" of travel/.test(w)), r.toolpath.warnings.join(" | "));
  // And the ramp is actually that shallow. Saying the slot is short while
  // still descending a full stepdown over it is a steeper ramp than the
  // sentence claims, on the tool the sentence exists to protect.
  const moves = r.toolpath.moves;
  for (const [i, m] of moves.entries()) {
    if (i === 0) continue;
    const prev = moves[i - 1];
    const drop = prev.z - m.z;
    if (drop <= 1e-9 || m.type === "PLUNGE" || m.type === "RAPID") continue;
    const run = Math.hypot(m.x - prev.x, m.y - prev.y);
    const deg = (Math.atan2(drop, run) * 180) / Math.PI;
    assert.ok(deg <= 3 + 1e-6, `the tool is fed down at ${deg.toFixed(2)}°, past the 3° ramp`);
  }
});

test("a tool wider than the slot is refused", () => {
  const r = generateToolpath(req(), slot({ width: 0.3 }), ctx(EM375), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /is 0\.3000" wide and the tool is ⌀0\.3750\. It does not fit\./);
});

test("a slot no longer than the cutter is refused, not fed straight down", () => {
  /*
   * The cutter's edge makes the round end, so its centre stops a radius short
   * at each end. A slot no longer than the tool leaves the two ends on one
   * point and the ramp becomes a vertical feed at a single XY — the plunge
   * this whole approach exists to avoid.
   */
  const r = generateToolpath(req(), slot({ startX: -0.15, endX: 0.15 }), ctx(EM375), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /the cutter centre has nowhere to travel and nothing to ramp along/);
  assert.ok((r.ok ? [] : r.error.recommendations).some((x) => /round-ended pocket/.test(x)));
});

test("a slot with no length is not a slot", () => {
  const r = generateToolpath(req(), slot({ endX: -1, endY: 0 }), ctx(EM375), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /starts and ends at the same point/);
});

test("a narrower tool takes a finishing lap round the slot", () => {
  // ⌀0.375 in a 0.500 slot leaves 0.0625 a side. The lap is the stadium the
  // boundary offsets to: two lines and a half-round at each end.
  const r = generateToolpath(req(), slot(), ctx(EM375), STOCK);
  assert.ok(r.ok);
  assert.ok(r.toolpath.moves.some(isArc), "no round end was cut");
  const ys = r.toolpath.moves.map((m) => m.y);
  assert.ok(Math.abs(Math.max(...ys) - 0.0625) < 1e-9, `the lap ran to Y${Math.max(...ys)}`);
  assert.ok(Math.abs(Math.min(...ys) + 0.0625) < 1e-9);
});

test("a full-width cut says it is one", () => {
  // 180° of engagement is the heaviest cut there is, and a machinist reading
  // "slot" on a sheet cannot tell which of the two they are getting.
  const r = generateToolpath(req(), slot({ width: 0.375 }), ctx(EM375), STOCK);
  assert.ok(r.ok);
  assert.ok(r.toolpath.warnings.some((w) => /180° engaged/.test(w)), r.toolpath.warnings.join(" | "));
  // And nothing laps a slot it has already cut wall to wall.
  assert.equal(r.toolpath.moves.some(isArc), false);
});

test("a diagonal slot is cut along its own line", () => {
  const r = generateToolpath(req(), slot({ startX: -1, startY: -1, endX: 1, endY: 1 }), ctx(EM375), STOCK);
  assert.ok(r.ok);
  // Every cutting move sits on the centreline or within half the slot of it.
  for (const m of r.toolpath.moves.filter((m) => m.type === "CUT" || m.type === "LEAD_IN")) {
    const off = Math.abs(m.x - m.y) / Math.SQRT2;
    assert.ok(off <= 0.25 + 1e-9, `a cut ${off.toFixed(4)}" off the centreline of a 0.5" slot`);
  }
});

/* ---------------- The head on a hole ---------------- */

const cbore = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "cb1", kind: "COUNTERBORE", label: "1/4 SHCS counterbore", centerX: 0, centerY: 1,
    diameter: 0.266, depth: 0.75, through: true, headDiameter: 0.4, headDepth: 0.26, top: 0,
    functionalRole: "CLEARANCE", critical: false, ...over,
  }) as unknown as Feature;

const csink = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "cs1", kind: "COUNTERSINK", label: "82° countersink", centerX: 0, centerY: -1,
    diameter: 0.201, depth: 0.75, through: true, headDiameter: 0.42, countersinkAngle: 82, top: 0,
    functionalRole: "CLEARANCE", critical: false, ...over,
  }) as unknown as Feature;

test("a counterbore is cut to its own depth, not the pilot's", () => {
  /*
   * The pilot goes right through the part. A head cut to the operation's
   * `finalZ` would take the whole thickness out at the head diameter, which is
   * not a counterbore — it is the part in two pieces.
   */
  const r = generateToolpath(req({ type: "COUNTERBORE", finalZ: -0.75 }), cbore(), ctx(EM375), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const deepest = Math.min(...r.toolpath.moves.map((m) => m.z));
  assert.ok(Math.abs(deepest + 0.26) < 1e-9, `the counterbore went to Z${deepest}`);
});

test("a counterbore plunges down its pilot rather than helixing", () => {
  /*
   * Everywhere else an end mill helixes into solid material. A counterbore is
   * the case where that does not apply: the tool is concentric with a hole
   * that already exists, so its axis is over open air. A ⌀0.400 bore with a
   * ⌀0.375 mill leaves 0.0125" of radius to move in, which no helix fits and
   * which needs none.
   */
  const r = generateToolpath(req({ type: "COUNTERBORE" }), cbore(), ctx(EM375), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  assert.ok(r.toolpath.moves.some((m) => m.type === "PLUNGE"));
  // And it still interpolates the wall rather than leaving the tool's size.
  assert.ok(r.toolpath.moves.some(isArc), "the bore was not interpolated");
});

test("a head with no diameter recorded is refused by the engine too", () => {
  /*
   * The planner refuses one before it ever gets here, and the engine takes
   * whatever operation exists — one stored before the field was filled in, one
   * a person edited. The head diameter is the whole of what this cuts, so a
   * missing one is not a small head.
   */
  const cases = [
    { type: "COUNTERBORE" as const, feature: cbore({ headDiameter: undefined }), tool: EM375 },
    { type: "COUNTERSINK" as const, feature: csink({ headDiameter: undefined }), tool: CS82 },
  ];
  for (const c of cases) {
    const r = generateToolpath(req({ type: c.type }), c.feature, ctx(c.tool), STOCK);
    assert.equal(r.ok, false, `${c.type} was cut with no head diameter`);
    assert.match(r.ok ? "" : r.error.reason, /records no head diameter/);
  }
});

test("a counterbore no bigger than its own hole is refused", () => {
  const r = generateToolpath(req({ type: "COUNTERBORE" }), cbore({ headDiameter: 0.25 }), ctx(EM375), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /A head no larger than its own hole is not a head/);
});

test("a counterbore with no depth recorded is refused, not cut shallow", () => {
  const r = generateToolpath(req({ type: "COUNTERBORE" }), cbore({ headDepth: undefined }), ctx(EM375), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /A head that sits proud is the failure this feature exists to prevent/);
});

test("a cutter too big for the counterbore is refused", () => {
  const r = generateToolpath(req({ type: "COUNTERBORE" }), cbore(), ctx(EM50), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /⌀0\.4000 counterbore and the tool is ⌀0\.5000/);
});

test("a countersink is a cone, and its depth is where the cone reaches the head", () => {
  /*
   * 82° included is a 41° half-angle. A ⌀0.420 head off a 0.020 tip flat is
   * (0.210 − 0.010) / tan 41° = 0.2301" down. The diameter and the depth are
   * one number, not two.
   */
  const r = generateToolpath(req({ type: "COUNTERSINK" }), csink(), ctx(CS82), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const deepest = Math.min(...r.toolpath.moves.map((m) => m.z));
  const want = -(0.42 / 2 - 0.01) / Math.tan((41 * Math.PI) / 180);
  assert.ok(Math.abs(deepest - want) < 1e-9, `plunged to Z${deepest}, want Z${want}`);
  assert.ok(r.toolpath.materialRemoved > 0);
});

test("a countersink ground at the wrong angle is refused, not plunged deeper", () => {
  // Plunging a 90° tool further makes the diameter and the wrong cone. The
  // angle of a countersink is the angle of the cone that cuts it.
  const wrong = tool({ id: "cs90", n: 9, cls: "COUNTERSINK", d: 0.5, over: { pointAngle: 90, tipDiameter: 0.02 } });
  const r = generateToolpath(req({ type: "COUNTERSINK" }), csink(), ctx(wrong), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /is a 82° countersink and .* is ground at 90°/);
});

test("a countersink tool with no point angle is refused", () => {
  const blank = tool({ id: "csx", n: 9, cls: "COUNTERSINK", d: 0.5 });
  const r = generateToolpath(req({ type: "COUNTERSINK" }), csink(), ctx(blank), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /no point angle recorded/);
});

test("a countersink whose tip will not enter the hole is refused", () => {
  const fat = tool({ id: "csf", n: 9, cls: "COUNTERSINK", d: 0.5, over: { pointAngle: 82, tipDiameter: 0.3 } });
  const r = generateToolpath(req({ type: "COUNTERSINK" }), csink(), ctx(fat), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /The tip will not enter it/);
});

/* ---------------- The plan ---------------- */

const plan = (features: Feature[], tools: Tool[]) =>
  planApproach("MINIMUM_SETUPS", {
    stock: STOCK, features, tools, workholding: null, finishedHeight: 0.7,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
  });

const opsOf = (features: Feature[], tools: Tool[]) => plan(features, tools).setups.flatMap((s) => s.operations);

test("a slot is planned as a slot, and the engine can run what was planned", () => {
  const ops = opsOf([slot()], [EM375, EM50]);
  const op = ops.find((o) => o.featureId === "f1");
  assert.ok(op, "no operation was planned for the slot");
  assert.equal(op.type, "SLOT_MILL", `a slot was planned as ${op.type}`);
  // ⌀0.375 over ⌀0.500: the biggest that still leaves a wall to finish.
  assert.equal(op.toolId, "em375");
  assert.match(op.rationale, /leaves 0\.0625" a side/);

  const r = generateToolpath(
    req({ type: op.type, featureId: op.featureId, finalZ: op.finalZ }),
    slot(),
    ctx(EM375),
    STOCK,
  );
  assert.ok(r.ok, `the plan produced an operation the engine refuses: ${r.ok ? "" : r.error.reason}`);
});

test("the plan takes the biggest cutter that fits, not the biggest that clears a corner", () => {
  // A pocket wants the biggest cutter its corners allow; a slot wants the
  // biggest that is not wider than the slot. The two rules pull opposite ways.
  const ops = opsOf([slot({ width: 0.5 })], [EM50, EM375]);
  assert.equal(ops.find((o) => o.featureId === "f1")!.toolId, "em375");
  // Nothing narrower available: full width, and the plan says so.
  const only = opsOf([slot({ width: 0.5 })], [EM50]);
  assert.equal(only.find((o) => o.featureId === "f1")!.toolId, "em50");
  assert.match(only.find((o) => o.featureId === "f1")!.rationale, /180° engaged/);
});

test("a slot no cutter fits is a concern, not an operation", () => {
  const p = plan([slot({ width: 0.2 })], [EM375, EM50]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.featureId === "f1").length, 0);
  assert.ok(p.concerns.some((c) => /Keyway slot is 0\.2000" wide/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a counterbore is drilled and then bored, in that order", () => {
  const ops = opsOf([cbore()], [EM375, D266]);
  const drill = ops.find((o) => o.type === "DRILL" || o.type === "PECK_DRILL");
  const head = ops.find((o) => o.type === "COUNTERBORE");
  assert.ok(drill, "the pilot is not drilled");
  assert.ok(head, "the counterbore is not cut");
  assert.equal(head.featureId, "cb1");
  assert.ok(drill.sequence < head.sequence, "the head is cut before the hole exists");
  assert.equal(head.finalZ, -0.26);
});

test("a countersink is planned against a cone of the right angle", () => {
  const ops = opsOf([csink()], [D201, CS82]);
  const head = ops.find((o) => o.type === "COUNTERSINK");
  assert.ok(head, "the countersink is not cut");
  assert.equal(head.toolId, "cs82");
  // The plan carries the depth the engine derives, so the sheet and the
  // program agree rather than being two numbers for one thing.
  assert.ok(Math.abs(head.finalZ + (0.42 / 2 - 0.01) / Math.tan((41 * Math.PI) / 180)) < 1e-9);
});

test("a head on a hole nobody can drill is a concern rather than an operation", () => {
  // Counterboring over a hole that was never produced is a tool change spent
  // on nothing, and it reads as though the feature is handled.
  const p = plan([cbore()], [EM375]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "COUNTERBORE").length, 0);
  assert.ok(
    p.concerns.some((c) => /its own hole is not being drilled/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
});

test("a countersink with no cone of the right angle in the crib names the nearest", () => {
  const cs90 = tool({ id: "cs90", n: 9, cls: "COUNTERSINK", d: 0.5, over: { pointAngle: 90, tipDiameter: 0.02 } });
  const p = plan([csink()], [D201, cs90]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "COUNTERSINK").length, 0);
  assert.ok(p.concerns.some((c) => /nearest cone in the crib is .* at 90°/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a head with no head diameter is a concern, not a guess at a fastener standard", () => {
  const p = plan([cbore({ headDiameter: undefined })], [EM375, D266]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "COUNTERBORE").length, 0);
  assert.ok(p.concerns.some((c) => /no head diameter recorded/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a counterbore with no depth is a concern, not an operation cut to nothing", () => {
  // A head that sits proud is the failure this feature exists to prevent, and
  // planning it without a depth hands the engine an operation it refuses.
  const p = plan([cbore({ headDepth: undefined })], [EM375, D266]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "COUNTERBORE").length, 0);
  assert.ok(p.concerns.some((c) => /no counterbore depth recorded/.test(c)), `got [${p.concerns.join(" | ")}]`);
  // The pilot is still drilled: the hole is real even where the head is not
  // yet dimensioned.
  assert.ok(p.setups.flatMap((s) => s.operations).some((o) => o.type === "DRILL" && o.featureId === "cb1"));
});

/* ---------------- The shape that caused it ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("no feature kind falls into a bucket whose engine refuses it", () => {
  const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));
  const classify = /function classify\([\s\S]*?\n}/.exec(planner);
  assert.ok(classify, "classify moved — this test cannot check it any more");
  assert.equal(
    /pockets:.*"SLOT"/.test(classify[0]),
    false,
    "a slot is back in the pocket bucket, and the pocket engine refuses slots",
  );
  assert.ok(/slots: features\.filter/.test(classify[0]), "slots have no bucket of their own");
  assert.ok(/heads: features\.filter\(headed\)/.test(classify[0]), "counterbores and countersinks have no bucket");
  // A head is BOTH: the pilot is drilled with every other hole.
  assert.ok(/holes: features\.filter\(\(f\) =>[^\n]*headed\(f\)\)/.test(classify[0]), "a head's pilot is not drilled");
});

test("a stepover of zero is not printed as a stepover of zero", () => {
  /*
   * A drill, a chamfer and a slot all carry stepover 0 because the number does
   * not apply to them. Printed, "0% stepover" beside a slot the cutter is 100%
   * engaged in is not a blank field — it is a wrong number, on the line a
   * machinist reads to see how hard the plan is pushing.
   */
  const page = strip(readFileSync("src/app/(app)/parts/[id]/machinist/page.tsx", "utf8"));
  assert.ok(
    /\{o\.stepover > 0 \? ` · \$\{\(o\.stepover \* 100\)\.toFixed\(0\)\}% stepover` : ""\}/.test(page),
    "the plan prints a stepover for operations that have none",
  );
});

test("the head goes on after the hole and before the thread", () => {
  // A counterbore cut after tapping cuts the top of the thread off; a
  // countersink after it raises a burr into the finished form.
  const seq = strip(readFileSync("src/lib/engines/sequencing.ts", "utf8"));
  const table = /FEATURE_STAGE: Record<OperationType, number> = \{[\s\S]*?\n\};/.exec(seq);
  assert.ok(table, "the stage table moved — this test cannot check it any more");
  const stage = (t: string) => Number(new RegExp(`${t}: (-?\\d+)`).exec(table[0])![1]);
  assert.ok(stage("DRILL") < stage("COUNTERBORE"));
  assert.ok(stage("COUNTERBORE") < stage("TAP"));
  assert.ok(stage("COUNTERSINK") < stage("TAP"));
  assert.equal(stage("SLOT_MILL"), stage("POCKET_2D"));
});
