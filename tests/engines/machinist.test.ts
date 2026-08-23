import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  planApproach,
  planAllApproaches,
  THOUGHT_PATTERNS,
  PHILOSOPHIES,
  type PlanInput,
  type MachinistPlan,
} from "@/lib/engines/machinist";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool, MachineProfile } from "@/lib/domain/shop";

/**
 * The planner produces several complete plans and lets arithmetic compare
 * them. Nothing here writes to a part, so a wrong plan does not cut metal on
 * its own — but a machinist reads it and a plan that names a tool which
 * cannot make the feature, or lists an operation that removes nothing, spends
 * their trust in the first thirty seconds.
 *
 * These do NOT pin the planner's judgement. Which tool is "right" for a
 * pocket is exactly the thing the five thought patterns are supposed to
 * disagree about, and freezing it would stop them being able to. What is
 * pinned is the part that is not a matter of opinion: that every planned
 * operation is physically possible, that a missing input is reported rather
 * than defaulted, and that a plan never contains work that does nothing.
 */

const tool = (o: { id: string; n: number; cls: string; d: number; flute?: number; stick?: number }): Tool =>
  ({
    id: o.id, toolNumber: o.n, toolClass: o.cls, description: `${o.cls} ⌀${o.d}`, diameter: o.d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: o.flute ?? 1.5,
    overallLength: 4, stickout: o.stick ?? 2.5, holder: "CAT40", holderNoseDiameter: 1.5,
    maxRPM: 8000, recommendedMaterials: [], chiploadMin: 0.001, chiploadMax: 0.006,
    sfmMin: 300, sfmMax: 900, coolant: "FLOOD", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  }) as unknown as Tool;

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 1.0, material: "Aluminum 6061" } as Stock;
const MACHINE = { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile;

const CRIB = [
  tool({ id: "fm", n: 1, cls: "FACE_MILL", d: 2 }),
  tool({ id: "em25", n: 2, cls: "FLAT_END_MILL", d: 0.25 }),
  tool({ id: "em375", n: 3, cls: "FLAT_END_MILL", d: 0.375 }),
  tool({ id: "em50", n: 4, cls: "FLAT_END_MILL", d: 0.5 }),
  tool({ id: "spot", n: 5, cls: "SPOT_DRILL", d: 0.25 }),
  tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201 }),
  tool({ id: "bore", n: 7, cls: "BORING_TOOL", d: 1.5 }),
  tool({ id: "cham", n: 8, cls: "CHAMFER_MILL", d: 0.5 }),
];

const f = (o: Record<string, unknown>): Feature =>
  ({ functionalRole: "CLEARANCE", critical: false, ...o }) as unknown as Feature;

const input = (over: Partial<PlanInput> = {}): PlanInput => ({
  stock: STOCK, features: [], machine: MACHINE, tools: CRIB, workholding: null, finishedHeight: 0.9,
  ...over,
});

const allOps = (p: MachinistPlan) => p.setups.flatMap((s) => s.operations);
const toolById = (id: string | null) => CRIB.find((t) => t.id === id) ?? null;

/* ---------------- Every planned operation must be possible ---------------- */

test("a bore is never assigned a cutter it cannot circle inside", () => {
  // fitsInternalCorner only asks that tool radius <= corner radius, which for
  // a bore reduces to tool diameter <= bore diameter — satisfied by equality.
  // FASTEST_CYCLE takes the largest candidate, so a 0.5" bore with a 0.5" end
  // mill in the crib selected that end mill and planned a POCKET_2D at 60%
  // stepover. A cutter the size of the bore can only plunge; it cannot
  // interpolate, and that toolpath cannot exist.
  const bore = f({ id: "b1", kind: "BORE", label: "0.5 bore", diameter: 0.5, depth: 0.4, centerX: 0, centerY: 0 });
  for (const pattern of THOUGHT_PATTERNS) {
    const p = planApproach(pattern, input({ features: [bore] }));
    for (const op of allOps(p).filter((o) => o.featureId === "b1" && o.type === "POCKET_2D")) {
      const t = toolById(op.toolId);
      assert.ok(t, `${pattern}: op has no tool`);
      assert.ok(t.diameter < 0.5, `${pattern}: ⌀${t.diameter} cannot interpolate a ⌀0.5 bore`);
    }
  }
});

test("a bore no cutter fits is a concern, not a plan", () => {
  const bore = f({ id: "b1", kind: "BORE", label: "tiny bore", diameter: 0.2, depth: 0.3, centerX: 0, centerY: 0 });
  const p = planApproach("FASTEST_CYCLE", input({ features: [bore] }));
  assert.equal(allOps(p).filter((o) => o.featureId === "b1").length, 0);
  assert.ok(p.concerns.some((c) => /tiny bore/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("a drill is sized to the hole rather than taken off the top of the crib", () => {
  // This planned ONE operation for every hole in the part, using the first
  // drill in the crib at the DEEPEST hole's depth. A 0.201 hole and a 0.500
  // hole came back as "drill both with the ⌀0.201, 0.900 deep": the large
  // hole was never produced, the small one was drilled through the bottom of
  // the part, and nothing was flagged.
  const p = planApproach("LOWEST_RISK", input({
    tools: [...CRIB, tool({ id: "d50", n: 9, cls: "DRILL", d: 0.5 })],
    features: [
      f({ id: "h1", kind: "DRILLED_HOLE", label: "small", diameter: 0.201, depth: 0.3, centerX: 0, centerY: 0 }),
      f({ id: "h2", kind: "DRILLED_HOLE", label: "big", diameter: 0.5, depth: 0.9, centerX: 1, centerY: 0 }),
    ],
  }));
  const drilling = allOps(p).filter((o) => o.type === "DRILL" || o.type === "PECK_DRILL");
  const bySize = drilling.filter((o) => o.toolNumber === 6 || o.toolNumber === 9);
  assert.equal(bySize.length, 2, `one operation per diameter; got [${drilling.map((o) => o.label).join(" | ")}]`);

  const small = bySize.find((o) => o.toolNumber === 6)!;
  const big = bySize.find((o) => o.toolNumber === 9)!;
  assert.equal(small.finalZ, -0.3, "the small hole is drilled to ITS depth, not the deep one's");
  assert.equal(big.finalZ, -0.9);
});

test("a hole with no drill of that size is refused, and the near miss is named", () => {
  const p = planApproach("LOWEST_RISK", input({
    features: [f({ id: "h2", kind: "DRILLED_HOLE", label: "big", diameter: 0.5, depth: 0.4, centerX: 0, centerY: 0 })],
  }));
  const drilling = allOps(p).filter((o) => o.type === "DRILL" || o.type === "PECK_DRILL");
  assert.equal(drilling.length, 0, "no drill of that size means no drilling operation");
  const concern = p.concerns.find((c) => /0\.5000/.test(c));
  assert.ok(concern, `got [${p.concerns.join(" | ")}]`);
  assert.match(concern, /0\.2010/, "the nearest drill is named so the machinist can judge the substitution");
  assert.match(concern, /not the same hole/i, "and it is not offered as a substitute");
});

test("no crib drill at all is stated once per size, not silently skipped", () => {
  const p = planApproach("LOWEST_RISK", input({
    tools: CRIB.filter((t) => t.toolClass !== "DRILL"),
    features: [f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.3, centerX: 0, centerY: 0 })],
  }));
  assert.ok(p.concerns.some((c) => /no drill in the crib/i.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("every planned operation cuts something", () => {
  // A pocket with no recorded depth fell through to 0 and produced a real
  // operation with finalZ: 0 — a pass that travels the whole toolpath at the
  // top of the stock and removes nothing, while still counting toward cycle
  // time and tool changes.
  const mystery = f({ id: "pk", kind: "RECT_POCKET", label: "mystery pocket", centerX: 0, centerY: 0, width: 1, length: 1, cornerRadius: 0.25 });
  for (const pattern of THOUGHT_PATTERNS) {
    const p = planApproach(pattern, input({ features: [mystery] }));
    assert.equal(allOps(p).filter((o) => o.featureId === "pk").length, 0, `${pattern} planned an unknown-depth pocket`);
    assert.ok(p.concerns.some((c) => /mystery pocket/.test(c) && /depth/i.test(c)), `${pattern} said nothing about it`);
  }
});

test("no operation anywhere is planned to zero depth", () => {
  const p = planApproach("BEST_FINISH", input({
    features: [
      f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
      f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 1, centerY: 0 }),
    ],
  }));
  for (const op of allOps(p)) {
    if (op.type === "FACE") continue; // facing runs from the allowance down to Z0 by definition
    assert.ok(op.finalZ < 0, `${op.label} is planned to finalZ ${op.finalZ} and removes nothing`);
  }
});

test("every operation names a tool that exists in the crib", () => {
  const p = planApproach("FASTEST_CYCLE", input({
    features: [
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.25, depth: 0.3 }),
      f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 1, centerY: 0 }),
    ],
  }));
  for (const op of allOps(p)) {
    assert.ok(op.toolId, `${op.label} has no tool`);
    const t = toolById(op.toolId);
    assert.ok(t, `${op.label} names a tool not in the crib`);
    assert.equal(op.toolNumber, t.toolNumber, `${op.label} tool number disagrees with the tool`);
  }
});

test("a tool is never planned deeper than it can reach", () => {
  const shortTool = tool({ id: "short", n: 20, cls: "FLAT_END_MILL", d: 0.25, flute: 0.3, stick: 0.4 });
  const p = planApproach("MINIMUM_SETUPS", input({
    tools: [shortTool],
    features: [f({ id: "pk", kind: "RECT_POCKET", label: "deep pocket", centerX: 0, centerY: 0, width: 1, length: 1, cornerRadius: 0.125, depth: 0.9 })],
  }));
  for (const op of allOps(p)) {
    const t = toolById(op.toolId);
    if (!t) continue;
    assert.ok(t.stickout >= Math.abs(op.finalZ), `${op.label}: ${t.stickout}" of stickout into ${Math.abs(op.finalZ)}"`);
  }
  assert.ok(p.concerns.some((c) => /deep pocket/.test(c)));
});

/* ---------------- A plan never contains work that does nothing ---------------- */

test("a flip is only planned when there is something to do after it", () => {
  // Setup 2 was pushed unconditionally for every pattern except
  // MINIMUM_SETUPS. A part with no outside profile and no face mill in the
  // crib got a second setup with zero operations — counted against the plan
  // in setups and cycle time, and carrying a soft-jaw concern about gripping
  // for an operation that did not exist.
  const p = planApproach("FASTEST_CYCLE", input({
    tools: [tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201 })],
    features: [f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 0, centerY: 0 })],
  }));
  for (const s of p.setups) assert.ok(s.operations.length > 0, `${s.name} has no operations`);
  assert.ok(p.concerns.some((c) => /nothing in this part needs a second setup/i.test(c)));
});

test("a dropped setup leaves no concern behind about how hard it grips", () => {
  const p = planApproach("FASTEST_CYCLE", input({
    tools: [tool({ id: "d201", n: 6, cls: "DRILL", d: 0.201 })],
    features: [f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 0, centerY: 0 })],
  }));
  assert.equal(p.setups.length, 1);
  assert.ok(!p.concerns.some((c) => /setup 2 grips/i.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("no setup in any plan is empty", () => {
  const features = [
    f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
    f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
    f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 }),
  ];
  for (const p of planAllApproaches(input({ features }))) {
    for (const s of p.setups) assert.ok(s.operations.length > 0, `${p.pattern}/${s.name} is empty`);
  }
});

test("the bottom facing operation does not claim the top face", () => {
  // Both operations pointed at c.faces[0], so SHOW ME framed the wrong
  // surface and two operations on opposite sides of the part were attributed
  // to one feature.
  const p = planApproach("LOWEST_RISK", input({
    features: [
      f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
      f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 }),
    ],
  }));
  const bottom = p.setups[1]?.operations.find((o) => /bottom/i.test(o.label));
  assert.ok(bottom, "there is a bottom facing operation");
  assert.notEqual(bottom.featureId, "top", "the top face is machined in Setup 1");
});

/* ---------------- Missing inputs are reported, not defaulted ---------------- */

test("no vise is declared as an assumption rather than silently assumed", () => {
  const p = planApproach("LOWEST_RISK", input({ workholding: null }));
  assert.ok(p.assumptions.some((a) => /vise/i.test(a)), `got [${p.assumptions.join(" | ")}]`);
});

test("a real vise removes the assumption and sets the grip length", () => {
  const p = planApproach("LOWEST_RISK", input({
    workholding: { id: "w", type: "VISE", description: '4" vise', jawWidth: 4, jawHeight: 1.5, maxOpening: 4, fixtureHeight: 3 } as unknown as PlanInput["workholding"],
    features: [f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 })],
  }));
  assert.ok(!p.assumptions.some((a) => /vise/i.test(a)));
  for (const s of p.setups) assert.ok(s.gripLength <= 4, `grip length ${s.gripLength} exceeds a 4" jaw`);
});

test("a hole with no diameter is reported rather than drilled with something", () => {
  const p = planApproach("LOWEST_RISK", input({
    features: [f({ id: "h1", kind: "DRILLED_HOLE", label: "unsized hole", depth: 0.3, centerX: 0, centerY: 0 })],
  }));
  assert.equal(allOps(p).filter((o) => o.featureId === "h1").length, 0);
  assert.ok(p.concerns.some((c) => /unsized hole/.test(c) && /diameter/i.test(c)));
});

/* ---------------- Grip is physically coherent ---------------- */

test("no setup grips more of the part than exists", () => {
  for (const p of planAllApproaches(input({
    features: [f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 })],
  }))) {
    for (const s of p.setups) {
      assert.ok(s.gripDepth > 0, `${p.pattern}/${s.name}: grip must be positive`);
      assert.ok(s.gripDepth < STOCK.z, `${p.pattern}/${s.name}: grips ${s.gripDepth} of ${STOCK.z} stock`);
      assert.ok(s.stockProjection > 0, `${p.pattern}/${s.name}: nothing stands proud of the jaws`);
    }
  }
});

test("the risk-averse machinist grips harder than the fast one", () => {
  const features = [f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 })];
  const safe = planApproach("LOWEST_RISK", input({ features }));
  const fast = planApproach("FASTEST_CYCLE", input({ features }));
  assert.ok(safe.setups[0].gripDepth > fast.setups[0].gripDepth, "that is the whole difference between them");
});

/* ---------------- The patterns genuinely differ ---------------- */

test("each pattern returns its own philosophy, and they are all distinct", () => {
  const plans = planAllApproaches(input({
    features: [f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 })],
  }));
  assert.equal(plans.length, THOUGHT_PATTERNS.length);
  for (const p of plans) {
    assert.equal(p.philosophy, PHILOSOPHIES[p.pattern]);
    assert.ok(p.philosophy.tradeoff.length > 20, `${p.pattern} names no tradeoff`);
  }
  assert.equal(new Set(plans.map((p) => p.pattern)).size, plans.length);
});

test("the finish machinist plans more operations than the fast one", () => {
  const features = [f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 })];
  const finish = planApproach("BEST_FINISH", input({ features }));
  const fast = planApproach("FASTEST_CYCLE", input({ features }));
  assert.ok(allOps(finish).length > allOps(fast).length, "a separate finish pass is the point of BEST_FINISH");
});

test("fewest-setups says so when the part will not allow it", () => {
  const p = planApproach("MINIMUM_SETUPS", input({
    features: [f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 })],
  }));
  assert.ok(
    p.concerns.some((c) => /cannot be done in one setup/i.test(c)),
    "an outside profile is the surface being gripped — claiming one setup would be a lie",
  );
});

test("every operation carries a rationale that can be argued with", () => {
  const p = planApproach("FASTEST_CYCLE", input({
    features: [
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
      f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 1, centerY: 0 }),
    ],
  }));
  for (const op of allOps(p)) assert.ok(op.rationale.length > 20, `${op.label} gives no reason`);
});

/* ---------------- Bookkeeping ---------------- */

test("the tool list is exactly the tools the plan uses", () => {
  const p = planApproach("BEST_FINISH", input({
    features: [
      f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
      f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 1, centerY: 0 }),
    ],
  }));
  const used = [...new Set(allOps(p).map((o) => o.toolNumber))].sort((a, b) => a! - b!);
  assert.deepEqual(p.toolNumbers, used);
  assert.deepEqual(p.toolNumbers, [...p.toolNumbers].sort((a, b) => a - b), "listed in changer order");
});

test("operation sequence numbers are dense within each setup", () => {
  for (const p of planAllApproaches(input({
    features: [
      f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
      f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 }),
    ],
  }))) {
    for (const s of p.setups) {
      s.operations.forEach((op, i) => assert.equal(op.sequence, i + 1, `${p.pattern}/${s.name}`));
    }
  }
});

test("setups are numbered in order and use different work offsets", () => {
  const p = planApproach("LOWEST_RISK", input({
    features: [f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 })],
  }));
  p.setups.forEach((s, i) => assert.equal(s.sequence, i + 1));
  assert.equal(new Set(p.setups.map((s) => s.workOffset)).size, p.setups.length, "two setups cannot share G54");
});

test("planning is deterministic", () => {
  const i = input({
    features: [
      f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
      f({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.201, depth: 0.5, centerX: 1, centerY: 0 }),
    ],
  });
  assert.deepEqual(planApproach("FASTEST_CYCLE", i), planApproach("FASTEST_CYCLE", i));
});

test("every operation points at a feature that exists, or at none", () => {
  // Asserting an empty part plans zero operations was wrong: a block of stock
  // 1.000" thick with a 0.900" finished height still needs facing, and the
  // planner is right to say so. What must hold is narrower and more useful —
  // no operation may name a feature the part does not have, and no operation
  // may name a feature that belongs to a different face.
  const features = [
    f({ id: "top", kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", depth: 0.05 }),
    f({ id: "pk", kind: "RECT_POCKET", label: "pocket", centerX: 0, centerY: 0, width: 2, length: 1, cornerRadius: 0.125, depth: 0.3 }),
    f({ id: "prof", kind: "OUTSIDE_CONTOUR", label: "profile", depth: 0.9, cornerRadius: 0.25 }),
  ];
  const ids = new Set(features.map((x) => (x as unknown as { id: string }).id));
  for (const p of planAllApproaches(input({ features }))) {
    for (const op of allOps(p)) {
      if (op.featureId === null) continue;
      assert.ok(ids.has(op.featureId), `${p.pattern}: ${op.label} names feature ${op.featureId}, which the part does not have`);
    }
  }
});

test("a featureless block is still faced to thickness, and nothing else is invented", () => {
  const p = planApproach("LOWEST_RISK", input({ features: [] }));
  for (const op of allOps(p)) {
    assert.equal(op.type, "FACE", `${op.label} was planned for a part with no features`);
    assert.equal(op.featureId, null, "there is no feature for it to point at");
  }
});

/* ---------------- The warnings have to reach the operator ---------------- */

test("every narrative the planner writes for the operator is rendered by the machinist page", () => {
  // planApproach computes three arrays whose only purpose is to be read by a
  // human: what it assumed, what it is concerned about, and what it could
  // not produce. `assumptions` was computed and rendered nowhere, so a plan
  // whose grip lengths and stock projections came from an assumed 6" vise
  // looked exactly like one measured against a real vise. The numbers
  // reached the machinist; the reason they were only estimates did not.
  //
  // This is a source check because the arrays are consumed in JSX. It is
  // coarse on purpose: it cannot prove the panel reads well, only that a
  // narrative field is not silently dropped on the floor again.
  const page = readFileSync("src/app/(app)/parts/[id]/machinist/page.tsx", "utf8");
  for (const field of ["assumptions", "concerns"] as const) {
    assert.match(
      page,
      new RegExp(`plan\\.${field}\\.map\\(`),
      `plan.${field} is computed for the operator and never rendered on the machinist page`,
    );
  }
  assert.match(page, /errors\.map\(/, "operations that could not be produced are computed and never rendered");
});
