import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { planTurning, FINISH_ALLOWANCE, type PlannerTool, type TurnPlanInput } from "@/lib/manufacturing/turn/planner";
import type { RotationalProfile, ProfileSegment } from "@/lib/manufacturing/turn/geometry";

/**
 * `RotationalPart.planJson` was written by the seed and by nothing else, so
 * every part created through the reverse-engineering flow had an empty plan:
 * no toolpaths, no cycle time, no cost, and a Tooling gate that could never
 * pass.
 *
 * What these pin is that the planner refuses rather than guessing. A plan that
 * quietly skipped the bore it could not reach would be worse than no plan,
 * because the cycle time and the cost would both look complete.
 */

const tool = (toolClass: string, station: string, over: Partial<PlannerTool> = {}): PlannerTool => ({
  station,
  toolClass,
  description: `${toolClass} tool`,
  surfaceSpeedMin: 400,
  surfaceSpeedMax: 900,
  feedPerRevMin: 0.004,
  feedPerRevMax: 0.015,
  maxDepthOfCut: 0.1,
  grooveWidth: null,
  minBoreDiameter: null,
  noseRadius: 0.031,
  ...over,
});

const CRIB: PlannerTool[] = [
  tool("FACING", "0303"),
  tool("OD_ROUGHING", "0101", { maxDepthOfCut: 0.15 }),
  tool("OD_FINISHING", "0202"),
  tool("BORING_BAR", "0404", { minBoreDiameter: 0.8 }),
  tool("GROOVING", "0505", { grooveWidth: 0.118 }),
  tool("THREADING", "0606"),
  tool("PARTING", "0707", { grooveWidth: 0.125 }),
];

const seg = (over: Partial<ProfileSegment> & { id: string }): ProfileSegment =>
  ({
    kind: "CYLINDER",
    label: over.id,
    zStart: 0,
    zEnd: 1,
    diameterStart: 1.5,
    diameterEnd: 1.5,
    internal: false,
    functionalRole: "NONE",
    critical: false,
    source: "USER",
    confirmedByUser: true,
    ...over,
  }) as ProfileSegment;

const profile = (segments: ProfileSegment[], over: Partial<RotationalProfile> = {}): RotationalProfile => ({
  units: "IN",
  zZeroReference: "front face",
  stockDiameter: 2,
  stockLength: 6,
  barStock: true,
  segments,
  ...over,
});

const input = (over: Partial<TurnPlanInput> = {}): TurnPlanInput => ({
  profile: profile([seg({ id: "s1", zEnd: 2 })]),
  tools: CRIB,
  materialSfmMin: 300,
  materialSfmMax: 700,
  materialName: "Steel 4140",
  chuckMaxRpm: 3000,
  ...over,
});

const types = (r: ReturnType<typeof planTurning>) => r.operations.map((o) => o.type);

/* ---------------- It plans an ordinary part ---------------- */

test("a plain bar turns into face, rough, finish, part off", () => {
  const r = planTurning(input());
  assert.deepEqual(types(r), ["FACE", "OD_ROUGH", "OD_FINISH", "PART_OFF"]);
  assert.deepEqual(r.refusals, []);
});

test("operation numbers run 10, 20, 30 the way a machinist reads them", () => {
  const r = planTurning(input());
  assert.deepEqual(
    r.operations.map((o) => o.operationNumber),
    [10, 20, 30, 40],
  );
});

test("each operation names a real station from the crib", () => {
  const r = planTurning(input());
  const byType = Object.fromEntries(r.operations.map((o) => [o.type, o.toolStation]));
  assert.equal(byType.FACE, "0303");
  assert.equal(byType.OD_ROUGH, "0101");
  assert.equal(byType.OD_FINISH, "0202");
  assert.equal(byType.PART_OFF, "0707");
});

test("roughing leaves stock on the diameter and finishing takes it to size", () => {
  const r = planTurning(input({ profile: profile([seg({ id: "s1", diameterStart: 1.5, diameterEnd: 1.5, zEnd: 2 })]) }));
  const rough = r.operations.find((o) => o.type === "OD_ROUGH")!;
  const finish = r.operations.find((o) => o.type === "OD_FINISH")!;
  assert.ok(Math.abs(rough.endDiameter - (1.5 + FINISH_ALLOWANCE)) < 1e-9, "roughing cut straight to size");
  assert.equal(finish.endDiameter, 1.5);
  assert.equal(rough.params.finishAllowance, FINISH_ALLOWANCE);
  assert.equal(finish.params.finishAllowance, 0);
});

test("the sequence bores before it finishes the OD", () => {
  // A boring bar pushing outward marks an OD that is already on size.
  const r = planTurning(
    input({
      profile: profile([seg({ id: "od", zEnd: 2 }), seg({ id: "bore", internal: true, kind: "BORE", diameterStart: 1, diameterEnd: 1, zEnd: 1.5 })]),
    }),
  );
  const t = types(r);
  assert.ok(t.indexOf("ID_BORE_FINISH") < t.indexOf("OD_FINISH"), `bore came after the OD finish: ${t.join(",")}`);
  assert.ok(t.indexOf("OD_ROUGH") < t.indexOf("ID_BORE_ROUGH"), "the envelope was not roughed first");
});

/* ---------------- It refuses rather than guessing ---------------- */

test("no material on file means no plan at all, and says so", () => {
  // THE RULE THE MILL ALREADY APPLIES. A carbide-in-steel window applied to
  // whatever is in the chuck reads as a plausible S-number and is six times
  // too fast for Inconel.
  const r = planTurning(input({ materialSfmMin: null, materialSfmMax: null, materialName: "Inconel 718" }));
  assert.equal(r.operations.length, 0);
  assert.ok(r.refusals.length > 0);
  assert.ok(r.refusals.every((x) => /surface speed window/i.test(x)));
  assert.ok(r.refusals.some((x) => /Inconel 718/.test(x)), "the refusal does not name the material");
});

test("a missing tool class refuses that operation and keeps the rest", () => {
  const r = planTurning(input({ tools: CRIB.filter((t) => t.toolClass !== "PARTING") }));
  assert.ok(!types(r).includes("PART_OFF"));
  assert.ok(types(r).includes("OD_FINISH"), "one missing tool threw the whole plan away");
  assert.ok(r.refusals.some((x) => /no parting tool/i.test(x)));
});

test("a tool with no recorded speed refuses, naming the tool", () => {
  const r = planTurning(input({ tools: CRIB.map((t) => (t.toolClass === "OD_FINISHING" ? { ...t, surfaceSpeedMin: null } : t)) }));
  assert.ok(!types(r).includes("OD_FINISH"));
  assert.ok(r.refusals.some((x) => /T0202|OD_FINISHING/.test(x) && /surface speed/i.test(x)));
});

test("a bore smaller than the bar will not fit, and is refused by the number", () => {
  const r = planTurning(
    input({ profile: profile([seg({ id: "od", zEnd: 2 }), seg({ id: "bore", internal: true, kind: "BORE", diameterStart: 0.5, diameterEnd: 0.5 })]) }),
  );
  assert.ok(!types(r).includes("ID_BORE_ROUGH"));
  const why = r.refusals.find((x) => /will not fit the hole/i.test(x))!;
  assert.ok(why, "the bore was skipped with no reason");
  assert.match(why, /0\.5000/);
  assert.match(why, /0\.800/);
});

test("a groove narrower than the tool is refused, not cut oversize", () => {
  const r = planTurning(
    input({ profile: profile([seg({ id: "od", zEnd: 2 }), seg({ id: "g", kind: "GROOVE", zStart: 1, zEnd: 1.05, diameterStart: 1.3, diameterEnd: 1.3 })]) }),
  );
  assert.ok(!types(r).includes("GROOVE_OD"));
  assert.ok(r.refusals.some((x) => /will not fit/i.test(x) && /0\.1180/.test(x)));
});

test("a thread with no readable pitch is refused", () => {
  const bad = planTurning(
    input({ profile: profile([seg({ id: "t", kind: "THREAD", thread: "some big thread", diameterStart: 0.75, diameterEnd: 0.75 })]) }),
  );
  assert.ok(!types(bad).includes("THREAD_OD"));
  assert.ok(bad.refusals.some((x) => /not a designation/i.test(x)));

  const none = planTurning(input({ profile: profile([seg({ id: "t", kind: "THREAD", diameterStart: 0.75, diameterEnd: 0.75 })]) }));
  assert.ok(none.refusals.some((x) => /no designation/i.test(x)));
});

test("a profile larger than its stock is refused outright", () => {
  const r = planTurning(input({ profile: profile([seg({ id: "s1", diameterStart: 3, diameterEnd: 3 })], { stockDiameter: 2 }) }));
  assert.equal(r.operations.length, 0);
  assert.ok(r.refusals.some((x) => /nothing to cut this from/i.test(x)));
});

test("an empty profile is refused rather than producing an empty plan silently", () => {
  const r = planTurning(input({ profile: profile([]) }));
  assert.equal(r.operations.length, 0);
  assert.ok(r.refusals.some((x) => /no segments/i.test(x)));
});

/* ---------------- Speeds and feeds ---------------- */

test("RPM is computed at the diameter each cut actually runs on", () => {
  // Constant surface speed means the same SFM is different RPM on different
  // diameters. A single RPM for the whole part is the thing CSS exists to
  // avoid.
  const r = planTurning(
    input({
      profile: profile([seg({ id: "big", diameterStart: 2, diameterEnd: 2, zEnd: 1 }), seg({ id: "small", diameterStart: 0.5, diameterEnd: 0.5, zStart: 1, zEnd: 2 })]),
    }),
  );
  const finishes = r.operations.filter((o) => o.type === "OD_FINISH");
  assert.equal(finishes.length, 2);
  const big = finishes.find((o) => o.label.includes("big"))!;
  const small = finishes.find((o) => o.label.includes("small"))!;
  assert.ok(small.params.rpm > big.params.rpm, "the small diameter did not spin faster");
});

test("the chuck's RPM limit caps the spindle when one is recorded", () => {
  const capped = planTurning(input({ chuckMaxRpm: 500 }));
  assert.ok(capped.operations.every((o) => o.params.rpm <= 500), "a cut exceeded the chuck limit");
  // And with no limit recorded, nothing is invented to stand in for one.
  const free = planTurning(input({ chuckMaxRpm: null }));
  assert.ok(free.operations.some((o) => o.params.rpm > 500));
});

test("surface speed sits inside both the tool's window and the material's", () => {
  const r = planTurning(input({ materialSfmMin: 300, materialSfmMax: 500 }));
  for (const o of r.operations) {
    if (o.params.surfaceSpeed === null) continue;
    assert.ok(o.params.surfaceSpeed >= 300 && o.params.surfaceSpeed <= 500, `${o.label} runs at ${o.params.surfaceSpeed} SFM`);
  }
});

test("a thread's feed is its pitch, not the tool's finishing feed", () => {
  // Feeding a thread at the tool's finish rate cuts a thread of the wrong lead.
  const r = planTurning(
    input({ profile: profile([seg({ id: "t", kind: "THREAD", thread: "3/4-16 UNF-2A", diameterStart: 0.75, diameterEnd: 0.75 })]) }),
  );
  const th = r.operations.find((o) => o.type === "THREAD_OD")!;
  assert.ok(Math.abs(th.params.feedPerRev - 1 / 16) < 1e-9, `thread fed at ${th.params.feedPerRev}`);
  assert.equal(th.params.cssEnabled, false, "a thread was cut under constant surface speed");
});

test("roughing feeds faster than finishing, from the same recorded range", () => {
  const r = planTurning(input());
  const rough = r.operations.find((o) => o.type === "OD_ROUGH")!;
  const finish = r.operations.find((o) => o.type === "OD_FINISH")!;
  assert.ok(rough.params.feedPerRev > finish.params.feedPerRev);
  assert.equal(rough.params.feedPerRev, 0.015);
  assert.equal(finish.params.feedPerRev, 0.004);
});

test("roughing depth comes from the crib's ceiling for that tool", () => {
  const r = planTurning(input());
  assert.equal(r.operations.find((o) => o.type === "OD_ROUGH")!.params.doc, 0.15);
});

/* ---------------- The plan says what it decided ---------------- */

test("the assumptions name the finish allowance and the sequence", () => {
  const r = planTurning(input());
  const all = r.assumptions.join(" ");
  assert.match(all, /planning convention/i);
  assert.match(all, /face, rough OD, bore, finish OD/i);
});

test("non-bar stock is not parted off, and the plan says why", () => {
  const r = planTurning(input({ profile: profile([seg({ id: "s1" })], { barStock: false }) }));
  assert.ok(!types(r).includes("PART_OFF"));
  assert.ok(r.assumptions.some((x) => /second operation nobody has planned/i.test(x)));
});

/* ---------------- No model ever writes machine motion ---------------- */

test("the planner contains no model call", () => {
  // Principle 6. This file generates the inputs to machine motion, which is on
  // the far side of a line an LLM does not cross.
  const src = readFileSync("src/lib/manufacturing/turn/planner.ts", "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/.*$/gm, "");
  for (const forbidden of ["anthropic", "openai", "askModel", "complete(", "generateText", "provider"]) {
    assert.ok(!src.toLowerCase().includes(forbidden.toLowerCase()), `the planner references ${forbidden}`);
  }
});

test("surface speed is not derived a second time here", () => {
  // The mill and the lathe must not drift apart on how fast to run, so the
  // intersection rule has one home and this file imports it.
  const src = readFileSync("src/lib/manufacturing/turn/planner.ts", "utf8");
  assert.match(src, /import \{ intersectSfm \}|intersectSfm,/);
  const body = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  assert.ok(!/Math\.max\(\s*tool\.surfaceSpeedMin/.test(body), "the intersection is being recomputed locally");
});

/* ---------------- Where the two windows miss each other ---------------- */

/**
 * Found by planning a real part and reading the numbers: at ⌀1.2503 the
 * finishing insert was running at 800 SFM in 4140 steel quoted 250-450.
 *
 * The cause was reusing the mill's non-overlap fallback, which takes the
 * TOOL's own rating. That is right for a tap — its speed is set by the
 * operation, not by the material's milling window — and wrong for a turning
 * insert, whose "500-1100 SFM" rating spans the materials it might see. On a
 * lathe the workpiece governs, and running the insert at its own rating burns
 * it. Sharing a rule that is not actually the same rule.
 */

test("with no overlap, a turning cut runs at the material's speed, not the tool's", () => {
  // Insert rated 500-1100, steel quoted 250-450. They do not meet.
  const r = planTurning(
    input({
      tools: CRIB.map((t) => (t.toolClass === "OD_FINISHING" ? { ...t, surfaceSpeedMin: 500, surfaceSpeedMax: 1100 } : t)),
      materialSfmMin: 250,
      materialSfmMax: 450,
    }),
  );
  const finish = r.operations.find((o) => o.type === "OD_FINISH")!;
  assert.ok(finish.params.surfaceSpeed !== null);
  assert.ok(
    finish.params.surfaceSpeed! <= 450,
    `the insert is running at ${finish.params.surfaceSpeed} SFM in a material quoted 250-450`,
  );
  assert.ok(finish.params.surfaceSpeed! >= 250);
});

test("running outside the tool's window is stated, naming the tool", () => {
  const r = planTurning(
    input({
      tools: CRIB.map((t) => (t.toolClass === "OD_FINISHING" ? { ...t, surfaceSpeedMin: 500, surfaceSpeedMax: 1100, description: "CNMG finisher" } : t)),
      materialSfmMin: 250,
      materialSfmMax: 450,
      materialName: "Steel 4140",
    }),
  );
  // Matched on the note's own words, not "rated window" — the generic
  // assumption about how surface speed is chosen contains that phrase too, so
  // a loose match finds the wrong sentence and passes on it.
  const note = r.assumptions.find((a) => /run at the material's surface speed/i.test(a));
  assert.ok(note, "a tool was run outside its rating with no word about it");
  assert.match(note!, /CNMG finisher/);
  assert.match(note!, /Steel 4140/);
  assert.match(note!, /insert grade/i);
});

test("an ordinary overlapping plan says nothing about tool windows", () => {
  // The note has to be quiet when it does not apply, or it is noise.
  const r = planTurning(input());
  assert.ok(!r.assumptions.some((a) => /run at the material's surface speed/i.test(a)));
});
