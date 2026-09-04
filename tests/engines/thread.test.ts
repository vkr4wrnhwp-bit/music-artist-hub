import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  parseThread,
  sameThread,
  tapDrill,
  threadEngagement,
  threadMinor,
} from "@/lib/engines/cam/thread";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { planApproach } from "@/lib/engines/machinist";
import { arcGeometry, isArc } from "@/lib/engines/cam/arc";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * A TAPPED HOLE WAS NEVER THREADED.
 *
 * The planner had no TAP branch at all. `tapToolpath` has existed since Phase
 * 1, the operation type has always existed, the seeded crib holds a 1/4-20 tap
 * — and nothing ever emitted the operation. Four "1/4-20 mounting hole"
 * features on the seeded part came out as four plain ⌀0.201 holes, and the
 * coverage gate passed them because the feature HAS operations: it was spotted
 * and it was drilled. A part with no threads in it, and a plan that reads
 * complete.
 */

const tool = (o: { id: string; n: number; cls: string; d: number; over?: Partial<Tool> }): Tool =>
  ({
    id: o.id, toolNumber: o.n, toolClass: o.cls, description: `${o.cls} ⌀${o.d}`, diameter: o.d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1, overallLength: 4, stickout: 2.5,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0, ...o.over,
  }) as unknown as Tool;

const TAP = tool({ id: "tap", n: 10, cls: "TAP", d: 0.25, over: { threadDesignation: "1/4-20 UNC", maxRPM: 4000 } });
const TM = tool({ id: "tm", n: 11, cls: "THREAD_MILL", d: 0.14, over: { threadDesignation: "1/4-20", fluteLength: 0.75 } });
const D201 = tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201, over: { pointAngle: 118, tipDiameter: 0 } });
const SPOT = tool({ id: "spot", n: 5, cls: "SPOT_DRILL", d: 0.5, over: { pointAngle: 90, tipDiameter: 0 } });

/* ---------------- Reading a designation ---------------- */

test("a designation gives a major diameter and a pitch, or nothing", () => {
  const t = parseThread("1/4-20 UNC")!;
  assert.equal(t.major, 0.25);
  assert.equal(t.pitch, 1 / 20);
  assert.equal(parseThread("M6x1.0")!.pitch, 1 / 25.4);
  assert.equal(parseThread("#10-32")!.pitch, 1 / 32);
  // Half a designation is not a thread: both numbers are needed to cut one.
  assert.equal(parseThread("UNC"), null);
  assert.equal(parseThread(""), null);
  assert.equal(parseThread(null), null);
});

test("two taps are the same tap when the numbers match, not when the text does", () => {
  /*
   * The reason the tool carries a designation at all: a 1/4-20 tap and a
   * 1/4-28 tap are both ⌀0.250, and picking one by size puts a 28-pitch tap in
   * a hole drilled for 20 and snaps it off in the part.
   */
  assert.equal(sameThread("1/4-20 UNC", "1/4-20"), true);
  assert.equal(sameThread("M6x1.0", "M6 x 1"), true);
  assert.equal(sameThread("1/4-20", "1/4-28"), false, "a coarse tap matched a fine hole");
  assert.equal(sameThread("1/4-20", "5/16-20"), false, "two different sizes at one pitch matched");
  assert.equal(sameThread(null, "1/4-20"), false, "a tool with no thread matched a thread");
  assert.equal(sameThread("1/4-20", undefined), false);
});

test("the tap drill leaves material to cut a thread in", () => {
  // major − pitch, which lands near 77% engagement: 1/4-20 gives 0.200 and the
  // shop reaches for the #7 at 0.201.
  const t = parseThread("1/4-20")!;
  assert.equal(Number(tapDrill(t).toFixed(4)), 0.2);
  assert.ok(Math.abs(threadEngagement(t, 0.201) - 75.4) < 1, threadEngagement(t, 0.201).toFixed(1));
  // A hole at the thread's own major diameter has nothing left to thread.
  assert.equal(threadEngagement(t, 0.25), 0);
  // And the minor is where the crest of an internal thread sits.
  assert.ok(Math.abs(threadMinor(t) - 0.185) < 0.001);
});

/* ---------------- The thread mill ---------------- */

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

const tapped = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "h1", kind: "TAPPED_HOLE", label: "1/4-20 mounting hole", centerX: 1, centerY: 0,
    diameter: 0.201, depth: 0.5, through: false, thread: "1/4-20 UNC", top: 0,
    functionalRole: "FASTENER", critical: false, ...over,
  }) as unknown as Feature;

const ctx = (t: Tool): MachiningContext => ({
  tool: t, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const req = (over: Partial<OperationRequest> = {}): OperationRequest =>
  ({
    id: "op1", type: "THREAD_MILL", label: "op", featureId: "h1", toolId: "tm", setupId: "s", pass: "ROUGH",
    overrides: {}, topZ: 0, finalZ: -0.5, clearanceZ: 0.1, retractZ: 1, ...over,
  }) as unknown as OperationRequest;

test("a thread mill cuts one turn rising one pitch, at the thread's major diameter", () => {
  /*
   * A full-form mill carries the whole profile on its flutes, so one 360° turn
   * rising a single pitch cuts the entire thread. The tool circles at
   * (major − toolDiameter) / 2, because an internal thread's MAJOR diameter is
   * its root — the deepest the cutter has to reach.
   */
  const r = generateToolpath(req(), tapped(), ctx(TM), STOCK);
  assert.ok(r.ok, r.ok ? "" : r.error.reason);
  const arcs = r.toolpath.moves.filter(isArc);
  // Lead in, two halves of the turn, lead out.
  assert.equal(arcs.length, 4);

  const cutting = r.toolpath.moves.filter((m) => m.type === "CUT" && isArc(m));
  assert.equal(cutting.length, 2, "the thread is not one full turn");
  const radius = (0.25 - 0.14) / 2;
  for (const m of cutting) {
    assert.ok(Math.abs(Math.hypot(m.x - 1, m.y) - radius) < 1e-9, `the turn is at r${Math.hypot(m.x - 1, m.y)}`);
  }
  // One pitch of rise across the turn, and counter-clockwise from the bottom,
  // which climb mills a right-hand internal thread.
  const rise = cutting[1].z - (r.toolpath.moves.find((m) => m.type === "LEAD_IN")!.z);
  assert.ok(Math.abs(rise - 1 / 20) < 1e-9, `rose ${rise} over the turn`);
  assert.ok(cutting.every((m) => m.cw === false), "the turn is clockwise");
});

test("the lead-in is tangential, not a radial dive into the wall", () => {
  // Entering radially at full depth leaves a witness at the entry and loads
  // the whole form at once. The lead-in is half a turn on the same helix.
  const r = generateToolpath(req(), tapped(), ctx(TM), STOCK);
  assert.ok(r.ok);
  const moves = r.toolpath.moves;
  const lead = moves.find((m) => m.type === "LEAD_IN")!;
  assert.ok(isArc(lead), "the lead-in is a straight move");
  const prev = moves[moves.indexOf(lead) - 1];
  const geo = arcGeometry(prev, lead)!;
  // It starts at the hole centre and swings out to the thread radius.
  assert.ok(Math.abs(prev.x - 1) < 1e-9 && Math.abs(prev.y) < 1e-9);
  assert.ok(Math.abs(geo.radius - (0.25 - 0.14) / 4) < 1e-9, `lead-in radius ${geo.radius}`);
  // Rising half a pitch, so it arrives on the helix rather than under it.
  assert.ok(Math.abs(lead.z - prev.z - 1 / 40) < 1e-9);
  assert.ok(moves.some((m) => m.type === "LEAD_OUT"), "the tool leaves the form radially");
});

test("a mill whose form is shorter than the thread is refused", () => {
  /*
   * One turn cuts the whole thread only where the form covers it. Past the
   * flute length the top of the thread is cut and the bottom is not, and the
   * hole gauges as a partial thread — which a plug gauge finds and a tapped
   * hole never would.
   */
  const short = tool({ id: "tms", n: 11, cls: "THREAD_MILL", d: 0.14, over: { threadDesignation: "1/4-20", fluteLength: 0.3 } });
  const r = generateToolpath(req(), tapped(), ctx(short), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /carries 0\.300" of form/);
  assert.match(r.ok ? "" : r.error.reason, /leave the bottom of it uncut/);
});

test("a mill ground for another pitch is refused, not run at this one", () => {
  const fine = tool({ id: "tmf", n: 11, cls: "THREAD_MILL", d: 0.14, over: { threadDesignation: "1/4-28", fluteLength: 0.75 } });
  const r = generateToolpath(req(), tapped(), ctx(fine), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /cuts 1\/4-28 and .* is 1\/4-20 UNC/);
  assert.match(r.ok ? "" : r.error.reason, /it cuts a thread of the wrong form/);
});

test("a mill with no thread recorded is refused rather than matched on its size", () => {
  const blank = tool({ id: "tmb", n: 11, cls: "THREAD_MILL", d: 0.14, over: { fluteLength: 0.75 } });
  const r = generateToolpath(req(), tapped(), ctx(blank), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /Matching on diameter alone puts a 28-pitch form in a hole cut for 20/);
});

test("a mill that does not fit the hole is refused", () => {
  const fat = tool({ id: "tmx", n: 11, cls: "THREAD_MILL", d: 0.19, over: { threadDesignation: "1/4-20", fluteLength: 0.75 } });
  const r = generateToolpath(req(), tapped(), ctx(fat), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /The tool does not go in the hole/);
});

test("a thread mill operation on anything but a tapped hole is refused", () => {
  const notThread = { ...(tapped() as unknown as Record<string, unknown>), kind: "DRILLED_HOLE", thread: undefined } as unknown as Feature;
  const r = generateToolpath(req(), notThread, ctx(TM), STOCK);
  assert.equal(r.ok, false);
  assert.match(r.ok ? "" : r.error.reason, /requires a tapped hole feature/);
  // And a milling cutter cannot stand in for a thread mill.
  const em = tool({ id: "em", n: 2, cls: "FLAT_END_MILL", d: 0.14 });
  const q = generateToolpath(req(), tapped(), ctx(em), STOCK);
  assert.equal(q.ok, false);
  assert.match(q.ok ? "" : q.error.reason, /no other cutter carries it/);
});

/* ---------------- The plan ---------------- */

const plan = (features: Feature[], tools: Tool[], pattern: "MINIMUM_SETUPS" | "BEST_FINISH" = "MINIMUM_SETUPS") =>
  planApproach(pattern, {
    stock: STOCK, features, tools, workholding: null, finishedHeight: 0.7,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
  });

const opsOf = (features: Feature[], tools: Tool[], pattern?: "MINIMUM_SETUPS" | "BEST_FINISH") =>
  plan(features, tools, pattern).setups.flatMap((s) => s.operations);

test("a tapped hole is threaded", () => {
  // The whole finding: it was spotted, it was drilled, and nothing threaded it.
  const ops = opsOf([tapped()], [SPOT, D201, TAP]);
  const tap = ops.find((o) => o.type === "TAP");
  assert.ok(tap, `no thread was cut: ${ops.map((o) => o.type).join(", ")}`);
  assert.equal(tap.featureId, "h1");
  assert.equal(tap.toolId, "tap");
  assert.match(tap.rationale, /The feed is the thread — 0\.0500" per revolution — not a number anybody chose/);
  // After the hole exists.
  assert.ok(ops.find((o) => o.type === "DRILL" && o.featureId === "h1")!.sequence < tap.sequence);
});

test("a tap of another pitch is not used because it is the same diameter", () => {
  const fine = tool({ id: "tapf", n: 10, cls: "TAP", d: 0.25, over: { threadDesignation: "1/4-28" } });
  const p = plan([tapped()], [D201, fine]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "TAP").length, 0);
  assert.ok(p.concerns.some((c) => /nothing in the crib cuts 1\/4-20 UNC/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("no tap and a full-form mill means the hole is milled", () => {
  const ops = opsOf([tapped()], [D201, TM]);
  const mill = ops.find((o) => o.type === "THREAD_MILL");
  assert.ok(mill, "the hole was left unthreaded with a thread mill in the crib");
  assert.match(mill.rationale, /a broken mill comes out of the hole where a broken tap does not/);
});

test("with both, the plan taps — unless the approach is chasing the fit", () => {
  // Tapping is faster and it is what a shop does. BEST_FINISH mills it,
  // because the size then comes off the D offset.
  assert.equal(opsOf([tapped()], [D201, TAP, TM]).find((o) => /TAP|THREAD_MILL/.test(o.type))!.type, "TAP");
  const best = opsOf([tapped()], [SPOT, D201, TAP, TM], "BEST_FINISH").find((o) => /TAP|THREAD_MILL/.test(o.type));
  assert.equal(best!.type, "THREAD_MILL");
  assert.match(best!.rationale, /how a class-3 fit is held/);
});

test("nothing that cuts the thread is a concern naming what would", () => {
  const p = plan([tapped()], [D201]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => /TAP|THREAD_MILL/.test(o.type)).length, 0);
  assert.ok(
    p.concerns.some((c) => /the hole will be drilled and left unthreaded otherwise/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
});

test("a thread mill whose form is too short is named as such, not left silent", () => {
  const short = tool({ id: "tms", n: 11, cls: "THREAD_MILL", d: 0.14, over: { threadDesignation: "1/4-20", fluteLength: 0.3 } });
  const p = plan([tapped()], [D201, short]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.type === "THREAD_MILL").length, 0);
  assert.ok(p.concerns.some((c) => /one turn would leave the bottom of it uncut/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a thread is never cut into a hole nobody drilled", () => {
  /*
   * A tap fed into solid material snaps on the first revolution. The crib here
   * has the right tap and no drill that makes the hole, which is the case that
   * would otherwise plan a tap over nothing.
   */
  const p = plan([tapped()], [SPOT, TAP]);
  const ops = p.setups.flatMap((s) => s.operations);
  assert.equal(ops.filter((o) => o.type === "TAP").length, 0, "a tap was planned into solid material");
  assert.equal(ops.filter((o) => o.type === "DRILL" && o.featureId === "h1").length, 0);
  assert.ok(
    p.concerns.some((c) => /its own hole is not being drilled, so there is nothing to thread/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
});

test("a hole recorded at the thread's own diameter is a concern", () => {
  /*
   * A ⌀0.250 hole for a 1/4-20 has no material left to cut a thread in. The
   * form asks for "Diameter" on a tapped hole and does not say which of the
   * two it means, so this is the check that catches the reading.
   */
  const p = plan([tapped({ diameter: 0.25 })], [D201, TAP]);
  assert.ok(
    p.concerns.some((c) => /leaves 0% of the thread form/.test(c) && /tap drill is ⌀0\.2000/.test(c)),
    `got [${p.concerns.join(" | ")}]`,
  );
});

test("a hole drilled tight enough to break the tap is a concern too", () => {
  // Past about 80% the strength barely moves and tap life falls off a cliff.
  const p = plan([tapped({ diameter: 0.19 })], [D201, TAP]);
  assert.ok(p.concerns.some((c) => /falls off a cliff/.test(c)), `got [${p.concerns.join(" | ")}]`);
  // And a hole at the usual drill says nothing at all.
  assert.equal(plan([tapped()], [D201, TAP]).concerns.some((c) => /thread form/.test(c)), false);
});

test("a thread nobody recorded is a concern, not a guessed pitch", () => {
  const p = plan([tapped({ thread: undefined })], [D201, TAP]);
  assert.ok(p.concerns.some((c) => /no thread designation recorded/.test(c)), `got [${p.concerns.join(" | ")}]`);
  const q = plan([tapped({ thread: "quarter twenty" })], [D201, TAP]);
  assert.ok(q.concerns.some((c) => /cannot be read for a pitch and a major diameter/.test(q.concerns.join(" "))), `got [${q.concerns.join(" | ")}]`);
});

/* ---------------- The shape that caused it ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the planner has a thread branch at all", () => {
  // It had none. The engine, the operation type and the seeded tap all existed
  // and nothing joined them up.
  const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));
  assert.ok(/type: "TAP",/.test(planner), "no plan ever emits a tap");
  assert.ok(/type: "THREAD_MILL",/.test(planner), "no plan ever emits a thread mill");
  assert.ok(/sameThread\(t\.threadDesignation, f\.thread\)/.test(planner), "a tap is matched on something other than its thread");
});

test("a thread is cut at the same stage however it is cut", () => {
  const seq = strip(readFileSync("src/lib/engines/sequencing.ts", "utf8"));
  const table = /FEATURE_STAGE: Record<OperationType, number> = \{[\s\S]*?\n\};/.exec(seq)!;
  const stage = (t: string) => Number(new RegExp(`${t}: (-?\\d+)`).exec(table[0])![1]);
  assert.equal(stage("THREAD_MILL"), stage("TAP"));
  assert.ok(stage("DRILL") < stage("TAP"));
  assert.ok(stage("TAP") < stage("CHAMFER"));
});
