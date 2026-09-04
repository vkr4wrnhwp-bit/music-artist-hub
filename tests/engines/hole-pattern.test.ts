import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { getPost } from "@/lib/engines/cam/post";
import { planApproach, THOUGHT_PATTERNS, type ThoughtPattern } from "@/lib/engines/machinist";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";
import type { Toolpath } from "@/lib/engines/cam/types";

/**
 * HOLE PATTERNS
 *
 * The planner emitted ONE operation labelled "Drill 6 × ⌀0.2010" pointed at
 * `holes[0].id`, and the toolpath engine drilled that one hole. Five holes were
 * never produced, no error was raised, the operation reported real motion, and
 * the pre-flight said every operation had produced motion. An operator read a
 * label promising six holes, ran it, and took a part with one out of the
 * machine.
 *
 * Found by an independent audit of the engine, not by any test here — which is
 * why the guards below are about the shape of the plan rather than about one
 * example.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));

const tool = (o: { id: string; n: number; cls: string; d: number }): Tool =>
  ({
    id: o.id, toolNumber: o.n, toolClass: o.cls, description: `${o.cls} ⌀${o.d}`, diameter: o.d,
    cornerRadius: 0, flutes: 2, material: "CARBIDE", fluteLength: 2.5, overallLength: 5, stickout: 3,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  }) as unknown as Tool;

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 1.5, material: "Aluminum 6061" } as Stock;
const CRIB = [
  tool({ id: "spot", n: 5, cls: "SPOT_DRILL", d: 0.25 }),
  tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201 }),
];

const hole = (id: string, over: Record<string, unknown> = {}): Feature =>
  ({
    id, kind: "DRILLED_HOLE", label: `hole ${id}`, diameter: 0.201, depth: 0.4,
    centerX: 0, centerY: 0, functionalRole: "CLEARANCE", critical: false, ...over,
  }) as unknown as Feature;

const plan = (features: Feature[], pattern: ThoughtPattern = "FASTEST_CYCLE") =>
  planApproach(pattern, {
    stock: STOCK,
    features,
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
    tools: CRIB,
    workholding: null,
    finishedHeight: 1.4,
  });

const opsOf = (features: Feature[], pattern: ThoughtPattern = "FASTEST_CYCLE") =>
  plan(features, pattern).setups.flatMap((s) => s.operations);

/* ---------------- The plan ---------------- */

const SIX = ["h1", "h2", "h3", "h4", "h5", "h6"].map((id, i) =>
  hole(id, { label: `bolt hole ${i + 1}`, centerX: Math.cos((i * Math.PI) / 3), centerY: Math.sin((i * Math.PI) / 3) }),
);

test("a bolt circle is six operations, one per hole, under every thought pattern", () => {
  // Which tool and which order are exactly what the patterns are meant to
  // disagree about. How many holes get cut is not.
  for (const pattern of THOUGHT_PATTERNS) {
    const drills = opsOf(SIX, pattern).filter((o) => o.type === "DRILL" && o.toolId === "d201");
    assert.equal(drills.length, 6, `${pattern}: ${drills.length} operations for six holes`);
    assert.deepEqual(
      drills.map((o) => o.featureId).sort(),
      SIX.map((h) => h.id).sort(),
      `${pattern}: the operations do not cover every hole`,
    );
  }
});

test("every hole is spotted, not just the first", () => {
  // LOWEST_RISK spots; FASTEST_CYCLE and MINIMUM_TOOLING decline the tool
  // change, which is their judgement to make and not what this is about.
  const ops = opsOf(SIX, "LOWEST_RISK");
  const spots = ops.filter((o) => o.toolId === "spot");
  assert.equal(spots.length, 6);
  assert.deepEqual(spots.map((o) => o.featureId).sort(), SIX.map((h) => h.id).sort());
  // And spotting still comes before drilling, which is the whole point of it.
  assert.ok(
    Math.max(...spots.map((o) => o.sequence)) <
      Math.min(...ops.filter((o) => o.toolId === "d201").map((o) => o.sequence)),
    "a hole is drilled before it is spotted",
  );
  for (const s of spots) {
    const f = SIX.find((h) => h.id === s.featureId)!;
    assert.equal(s.label, `Spot ${f.label}`);
  }
});

test("a label names the one hole the operation makes", () => {
  // "Drill 6 × ⌀0.2010" for one hole. The label is the part an operator reads
  // and believes.
  for (const op of opsOf(SIX).filter((o) => o.toolId === "d201")) {
    const f = SIX.find((h) => h.id === op.featureId)!;
    assert.equal(op.label, `Drill ${f.label}`, `label "${op.label}" does not name its hole`);
  }
  assert.equal(/\d+ ×/.test(opsOf(SIX).map((o) => o.label).join(" ")), false, "a label still counts a group");
});

test("each hole is drilled to its own depth, not the group's deepest", () => {
  /*
   * The group's depth was `Math.max(...depths)`. Applied to the shallow hole
   * beside it, that is a drill through the bottom of the part and into
   * whatever is holding it.
   */
  const holes = [hole("shallow", { depth: 0.15 }), hole("deep", { depth: 1.2, centerX: 1 })];
  const drills = opsOf(holes).filter((o) => o.toolId === "d201");
  assert.equal(drills.length, 2);
  assert.equal(drills.find((o) => o.featureId === "shallow")!.finalZ, -0.15);
  assert.equal(drills.find((o) => o.featureId === "deep")!.finalZ, -1.2);
});

test("the peck decision is the hole's own depth to diameter, not the group's", () => {
  // 1.2/0.201 is 6:1 and pecks. 0.15/0.201 is under 1:1 and does not — and
  // pecking it would be six retracts through a hole shallower than one peck.
  const holes = [hole("shallow", { depth: 0.15 }), hole("deep", { depth: 1.2, centerX: 1 })];
  const drills = opsOf(holes).filter((o) => o.toolId === "d201");
  assert.equal(drills.find((o) => o.featureId === "deep")!.type, "PECK_DRILL");
  assert.equal(drills.find((o) => o.featureId === "shallow")!.type, "DRILL", "a 0.15\" hole is pecked");
});

test("a hole with no depth still does not take the group's", () => {
  // The group cannot be planned at all when one hole has no depth recorded —
  // it says so rather than borrowing the neighbour's number.
  const p = plan([hole("h1", { depth: 0.4 }), hole("h2", { depth: undefined, centerX: 1 })]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.toolId === "d201").length, 0);
  assert.ok(p.concerns.some((cn) => /not every one records a depth/.test(cn)), `got [${p.concerns.join(" | ")}]`);
});

/* ---------------- The shape that caused it ---------------- */

test("no planned operation points at the first of a group of features", () => {
  /*
   * The signature of the defect: `featureId: <something>[0].id` while the
   * label counts the whole group. It appeared three times — drills, spotting
   * and chamfers — and every one of them cut one feature out of N. A face is
   * the one legitimate case: facing the stock top is one operation over the
   * whole face, whatever a part records as separate faces.
   */
  const firstOfGroup = [...planner.matchAll(/featureId:\s*(?:c\.)?(\w+)\[0\]\.id/g)].map((m) => m[1]);
  assert.deepEqual(firstOfGroup, ["faces"], `operations still planned against the first of: ${firstOfGroup.join(", ")}`);
});

test("the spot count is not parsed back out of a sentence the planner wrote", () => {
  // It used to read the number of holes out of the drill operation's own
  // label with a regex, and then built the spot's label by editing it.
  assert.equal(/exec\(o\.label\)/.test(planner), false, "the plan reads its own prose to count holes");
  assert.equal(/label\.replace\(/.test(planner), false, "an operation label is built by editing another one");
});

test("one chamfer operation per chamfer feature", () => {
  // "Chamfer top edges" pointed at `chamfers[0]` was the same defect: every
  // other chamfer on the part went uncut and the label did not say which one
  // it meant.
  assert.ok(/for \(const f of c\.chamfers\) \{/.test(planner), "chamfers are not planned per feature");
});

/* ---------------- The program stays idiomatic ---------------- */

const machine = {
  manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20,
  maxSpindleRPM: 8100, maxFeed: 500, maxRapid: 1000,
} as unknown as MachineProfile;

const drill = (x: number, y: number, over: Record<string, unknown> = {}): Toolpath =>
  ({
    operationId: `op${x}${y}`, type: "DRILL", toolId: "t6", toolNumber: 6,
    moves: [
      { type: "RAPID", x, y, z: 0.1, feed: null },
      { type: "PLUNGE", x, y, z: -0.5, feed: 20 },
      { type: "RETRACT", x, y, z: 1, feed: null },
    ],
    parameters: { rpm: 3000, feed: 20, coolant: "FLOOD" },
    cycleTimeMinutes: 0.1, materialRemoved: 0.01, cuttingDistance: 0.6, warnings: [], isPlaceholder: false,
    cannedCycle: { code: "G81", x, y, z: -0.5, r: 0.1, feed: 20, rpm: 3000, ...over },
  }) as unknown as Toolpath;

const ctx = {
  programNumber: "1001", programName: "TEST", machine, workOffset: "G54", units: "IN" as const,
  toolTable: [{ toolNumber: 6, description: "#7 drill", lengthOffset: 6, diameterOffset: 6, diameter: 0.201 }],
  safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-09-04T00:00:00Z",
};

const emit = (tps: Toolpath[]) => getPost("haas-ngc-dev")!.emit(tps, ctx);

/**
 * Cycle cancels, counted as their own blocks.
 *
 * `/\bG80\b/` over the whole program also finds the one in the safe-start line
 * `G17 G40 G49 G80 G90`, which is a different statement — it cancels any cycle
 * left modal from a previous program, and it is there whether or not this
 * program has a cycle at all.
 */
const cancels = (code: string) => code.split("\n").filter((l) => l.trim() === "G80").length;

test("holes that share a tool and a depth come out as one cycle with positions under it", () => {
  /*
   * Per-hole OPERATIONS do not mean a per-hole program. A control holds the
   * cycle modal: G81 X Y Z R F, then a bare X Y for every hole after it, then
   * one G80. Three lines instead of eleven per hole, and it is what a
   * machinist expects to single-block through.
   */
  const code = emit([drill(1, 1), drill(2, 1), drill(3, 1)]);
  assert.equal((code.match(/\bG81\b/g) ?? []).length, 1, "three holes produced three cycles");
  assert.equal(cancels(code), 1);
  assert.match(code, /^X2\.0000 Y1\.0000$/m, "the second hole is not a bare position");
  assert.match(code, /^X3\.0000 Y1\.0000$/m);
  assert.match(code, /DRILL 3 HOLES/);
  // One tool change, one spindle start, one G43.
  assert.equal((code.match(/T6 M6/g) ?? []).length, 1);
});

test("a different depth is a different cycle", () => {
  // Inheriting one hole's depth for the next is how a program drills through
  // a table.
  const code = emit([drill(1, 1), drill(2, 1, { z: -0.9 })]);
  assert.equal((code.match(/\bG81\b/g) ?? []).length, 2, "two depths were merged into one cycle");
  assert.equal(cancels(code), 2);
});

test("a different tool is a different cycle", () => {
  const other = { ...drill(2, 1), toolNumber: 7 } as Toolpath;
  const code = emit([drill(1, 1), other]);
  assert.equal((code.match(/\bG81\b/g) ?? []).length, 2);
});

test("everything the cycle asserts has to match, or it is a second cycle", () => {
  /*
   * The merged holes carry nothing but X and Y. Every other word — the cycle
   * itself, the depth, the R plane, the peck, the feed, the speed — is
   * inherited from the first hole of the group, so any of them differing has
   * to end the group. Each row here differs from the first hole in exactly one
   * of them.
   */
  const cycles = (code: string) => (code.match(/^G98 /gm) ?? []).length;
  const cases: [string, Record<string, unknown>][] = [
    // A tap merged under a drill cycle leaves the hole unthreaded and the part
    // goes out untapped; a drill merged under a tap cycle snaps the tap.
    ["a tap under a drill cycle", { code: "G84" }],
    ["a peck under a drill cycle", { code: "G83" }],
    // R is where rapid becomes feed. Inheriting a low one plunges at feed from
    // above a clamp; inheriting a high one air-cuts the top of the hole.
    ["a different R plane", { r: 0.6 }],
    ["a different feed", { feed: 6 }],
    ["a different speed", { rpm: 1200 }],
  ];
  for (const [what, over] of cases) {
    assert.equal(cycles(emit([drill(1, 1), drill(2, 1, over)])), 2, `${what} was merged into the cycle above it`);
  }
  /*
   * Q is inherited the same way, and needs a peck on both sides to isolate.
   * Today's engine derives it from the tool alone, so two G83s on one drill
   * always agree — but the post is a separate module and takes whatever
   * descriptor the engine hands it. A hole that needs a finer peck merged
   * under one that does not packs its flutes and snaps the drill in the hole.
   */
  const p1 = drill(1, 1, { code: "G83", q: 0.15 });
  assert.equal(cycles(emit([p1, drill(2, 1, { code: "G83", q: 0.05 })])), 2, "two peck increments in one cycle");
  assert.equal(cycles(emit([p1, drill(2, 1, { code: "G83" })])), 2, "a hole with no peck merged under a peck cycle");
  assert.equal(cycles(emit([p1, drill(2, 1, { code: "G83", q: 0.15 })])), 1);

  // And the control: identical in every one of them is one cycle.
  assert.equal(cycles(emit([drill(1, 1), drill(2, 1)])), 1);
});

test("a peck and a drill are different cycles even at the same depth", () => {
  const peck = drill(2, 1, { code: "G83", q: 0.15 });
  const code = emit([drill(1, 1), peck]);
  assert.match(code, /\bG81\b/);
  assert.match(code, /\bG83\b/);
  assert.match(code, /Q0\.1500/);
});

test("an operation with no toolpath engine is never merged into the cycle above it", () => {
  /*
   * A placeholder is an operation the engine could not produce motion for, and
   * the program says so and cuts nothing. Merging is by cycle DESCRIPTOR, and
   * nothing in the type stops a placeholder carrying one — so without the
   * check the group swallows it, the control drills a hole at its position,
   * and the program still prints HAS NO TOOLPATH ENGINE — SKIPPED two lines
   * above. A block that says it did nothing while the control cuts is the
   * worst shape a program can take.
   */
  const ghost = { ...drill(2, 1), isPlaceholder: true } as unknown as Toolpath;
  const code = emit([drill(1, 1), ghost, drill(3, 1)]);
  // Hyphen, not an em-dash: comment text is sanitised to the ASCII a
  // control's reader accepts. See commentText in cam/post.ts.
  assert.match(code, /HAS NO TOOLPATH ENGINE - SKIPPED/);
  assert.equal((code.match(/^G98 /gm) ?? []).length, 2, "a placeholder was merged into a cycle");
  assert.equal(/^X2\.0000 Y1\.0000$/m.test(code), false, "the placeholder was drilled as a position under the cycle");
});

test("a merged hole announces nothing", () => {
  /*
   * The first version of the merge skipped the cycle but not the operation
   * heading, so a six-hole pattern ended with five `(DRILL — T6 #7 drill)`
   * blocks with no motion under them. A heading with nothing beneath it is a
   * program a machinist stops and reads twice, looking for the operation that
   * did not come out.
   */
  const code = emit([drill(1, 1), drill(2, 1), drill(3, 1)]);
  assert.equal(
    (code.match(/^\(DRILL - T6/gm) ?? []).length,
    1,
    "merged holes still announce themselves as operations with no motion",
  );
});

test("a different coolant state is a different cycle", () => {
  // M8 belongs to the first hole of the group. Merging a dry hole under a
  // flooded one runs it wet, and merging the other way runs it dry.
  const dry = { ...drill(2, 1), parameters: { rpm: 3000, feed: 20, coolant: "OFF" } } as unknown as Toolpath;
  const code = emit([drill(1, 1), dry]);
  assert.equal((code.match(/\bG81\b/g) ?? []).length, 2, "a dry hole was merged under a flooded cycle");
});

/* ---------------- The posts that have no canned cycles ---------------- */

/*
 * GRBL, Heidenhain and Siemens drill as feed moves in this development build,
 * so a hole pattern is genuinely N operations there. What must not multiply is
 * the TOOL CHANGE: those posts announced one per operation, which was invisible
 * while a pattern was one operation and became twenty the moment it was twenty.
 */

test("GRBL does not stop for a manual tool change once per hole", () => {
  // M0 is a program pause. Twenty of them for a tool already in the spindle is
  // a program an operator learns to cycle-start through without reading, and
  // one of those pauses is a real tool change.
  const code = getPost("grbl-dev")!.emit([drill(1, 1), drill(2, 1), drill(3, 1)], ctx);
  assert.equal((code.match(/^M0$/gm) ?? []).length, 1, "GRBL pauses for a manual change once per hole");
  assert.equal((code.match(/MANUAL TOOL CHANGE REQUIRED/g) ?? []).length, 1);
  // The holes are still all drilled — as feed moves, which is what that post
  // says it does.
  assert.equal((code.match(/DRILLED AS FEED MOVES/g) ?? []).length, 3);
});

test("Heidenhain calls the tool once, and again when the speed changes", () => {
  const code = getPost("heidenhain-dev")!.emit([drill(1, 1), drill(2, 1)], ctx);
  assert.equal((code.match(/TOOL CALL 6 Z S3000/g) ?? []).length, 1, "one tool call per hole");

  // TOOL CALL carries the speed, so a speed change has to re-issue it.
  const faster = { ...drill(2, 1), parameters: { rpm: 4500, feed: 20, coolant: "FLOOD" } } as unknown as Toolpath;
  const code2 = getPost("heidenhain-dev")!.emit([drill(1, 1), faster], ctx);
  assert.match(code2, /TOOL CALL 6 Z S3000/);
  assert.match(code2, /TOOL CALL 6 Z S4500/, "a speed change did not re-issue the tool call");
});

test("Siemens changes the tool once", () => {
  const code = getPost("siemens-840d-dev")!.emit([drill(1, 1), drill(2, 1), drill(3, 1)], ctx);
  assert.equal((code.match(/M6/g) ?? []).length, 1, "a change macro per hole");
  assert.equal((code.match(/^D1$/gm) ?? []).length, 1);
  // Speed is re-stated per operation, which is one line and can legitimately
  // differ between them.
  assert.equal((code.match(/^S3000 M3$/gm) ?? []).length, 3);
});
