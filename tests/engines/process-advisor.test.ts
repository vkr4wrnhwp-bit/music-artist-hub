import { test } from "node:test";
import assert from "node:assert/strict";
import { analyzeProcesses, PROCESS_LABEL, PROCESSES, type ProcessInput } from "@/lib/engines/process-advisor";
import { emptyPartIntent, type PartIntent } from "@/lib/domain/part-intent";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Provenanced } from "@/lib/provenance";

/**
 * Locked principle 8: do not assume CNC is the answer. Locked principle 9:
 * understand what the part DOES before recommending a substantial
 * manufacturing change — "never recommend a cheaper process merely because
 * the geometry looks compatible".
 *
 * Those two pull against each other, and this engine is where the tension
 * lives. So the tests are about the boundary between them: a process that
 * changes the material's properties must stay silent until the part's
 * responsibility is known, and a process that cannot physically produce the
 * geometry must not be offered however good the economics look.
 *
 * The volume bands are not pinned as truth. They are trade rules of thumb and
 * a shop may disagree; what is pinned is that they are ordered sensibly and
 * that they are labelled as what they are rather than as a calculation.
 */

const P = <T,>(value: T): Provenanced<T> => ({
  value, source: "USER", confidence: "HIGH", confirmedByUser: true,
});

const intent = (o: Partial<PartIntent> = {}): PartIntent => ({ ...emptyPartIntent("Bracket"), ...o });

/** An intent with the responsibility profile fully answered. */
const known = (o: Partial<PartIntent> = {}): PartIntent =>
  intent({
    quantity: P(100), material: P("6061-T6"),
    loadBearing: P(false), failureConsequence: P("LOW"),
    ...o,
  });

const PLATE = { form: "RECTANGULAR", x: 8, y: 6, z: 0.25, material: "6061" } as Stock;
const BLOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 2, material: "6061" } as Stock;

const feature = (o: Record<string, unknown>): Feature =>
  ({ functionalRole: "CLEARANCE", critical: false, ...o }) as unknown as Feature;

const run = (over: Partial<ProcessInput> = {}) =>
  analyzeProcesses({
    intent: known(), stock: null, features: [], finishedVolume: null, machinedUnitCost: 40, ...over,
  });

const verdictOf = (a: ReturnType<typeof run>, p: string) =>
  a.recommendations.find((r) => r.process === p)?.verdict;

/* ---------------- A property change waits for the responsibility profile ---------------- */

test("no process that changes the material speaks while responsibility is unknown", () => {
  // The headline said "CANVAS will not compare alternative processes until 2
  // outstanding inputs are resolved" — and FORGING sat at INVESTIGATE
  // directly beneath it, as did powder-bed fusion. CASTING, the process
  // nearest to forging, correctly said INSUFFICIENT_DATA on the same inputs.
  // Two near-identical answers to the same question, and the unsafe one spoke.
  const a = run({
    intent: intent({ quantity: P(5000), annualVolume: P(5000), material: P("6061") }),
  });
  assert.ok(a.blockedBy.length > 0, "precondition: the profile is incomplete");
  for (const p of ["CASTING", "FORGING", "METAL_ADDITIVE_PBF", "HYBRID_ADDITIVE_SUBTRACTIVE"]) {
    assert.equal(verdictOf(a, p), "INSUFFICIENT_DATA", `${p} answered while the profile was incomplete`);
  }
});

test("the headline's promise and the recommendation list agree", () => {
  const a = run({ intent: intent({ quantity: P(5000), annualVolume: P(5000) }) });
  assert.match(a.headline, /will not compare alternative processes/i);
  const speaking = a.recommendations.filter(
    (r) => r.process !== "CNC_BILLET" && (r.verdict === "INVESTIGATE" || r.verdict === "RECOMMENDED" || r.verdict === "VIABLE"),
  );
  assert.deepEqual(speaking, [], `the headline says nothing is being compared, but ${speaking.map((r) => r.process).join(", ")} is`);
});

test("each missing input is named so it can be answered", () => {
  const a = run({ intent: intent() });
  for (const pattern of [/load bearing/i, /failure consequence/i, /quantity/i, /material/i]) {
    assert.ok(a.blockedBy.some((b) => pattern.test(b)), `${pattern} is not named`);
  }
});

test("machining stays the working assumption while the profile is incomplete", () => {
  // The safe default is the one that does not change the material.
  const a = run({ intent: intent() });
  assert.ok(["RECOMMENDED", "VIABLE"].includes(verdictOf(a, "CNC_BILLET")!));
  assert.deepEqual(a.recommendations.find((r) => r.process === "CNC_BILLET")!.blockers, []);
});

test("with the profile answered, high volume does open the near-net conversation", () => {
  const a = run({ intent: known({ quantity: P(5000), annualVolume: P(5000) }) });
  assert.deepEqual(a.blockedBy, []);
  assert.equal(verdictOf(a, "CASTING"), "INVESTIGATE");
  assert.equal(verdictOf(a, "FORGING"), "INVESTIGATE");
  assert.match(a.headline, /unlikely to be the right long-term process/i);
});

test("a critical part with an unknown loading case still will not be cast", () => {
  // Cast material has different fatigue behaviour to wrought. Knowing the
  // part is load bearing is not the same as knowing how it is loaded.
  const a = run({
    intent: known({
      quantity: P(5000), annualVolume: P(5000),
      loadBearing: P(true), failureConsequence: P("CRITICAL"),
    }),
  });
  assert.deepEqual(a.blockedBy, [], "precondition: the baseline profile is complete");
  assert.equal(verdictOf(a, "CASTING"), "INSUFFICIENT_DATA");
  assert.ok(
    a.recommendations.find((r) => r.process === "CASTING")!.blockers.some((b) => /loading case/i.test(b)),
    "it must say which gap stopped it",
  );
});

/* ---------------- A process that cannot make the geometry is not offered ---------------- */

test("a blind slot stops the part being a through-profile", () => {
  // A waterjet cuts all the way through, everywhere. The flatness test asked
  // only about RECT_POCKET and CIRC_POCKET, so a 0.250 plate with a 0.100
  // deep SLOT was "essentially flat": waterjet came back VIABLE and the
  // headline told the shop to buy waterjet blanks — for a part with a
  // feature a waterjet cannot produce at all.
  const slot = feature({ id: "s1", kind: "SLOT", label: "keyway", depth: 0.1, width: 0.25, length: 2, centerX: 0, centerY: 0 });
  const a = run({ stock: PLATE, features: [slot] });
  assert.equal(verdictOf(a, "WATERJET"), "NOT_SUITABLE");
  assert.ok(!/waterjet/i.test(a.headline), `the headline still sells waterjet: ${a.headline}`);
});

test("the flatness test does not depend on what a feature is called", () => {
  // A pocket at that depth was caught and a slot was not, which is what an
  // allow-list of feature kinds does as soon as the feature list grows.
  const at = (kind: string) =>
    verdictOf(run({ stock: PLATE, features: [feature({ id: "f1", kind, label: kind, depth: 0.1, width: 1, length: 1, cornerRadius: 0.1, diameter: 0.5, centerX: 0, centerY: 0 })] }), "WATERJET");
  const kinds = ["SLOT", "RECT_POCKET", "CIRC_POCKET", "ENGRAVING", "CHAMFER"];
  const verdicts = kinds.map(at);
  assert.equal(new Set(verdicts).size, 1, `partial-depth features disagree by name: ${kinds.map((k, i) => `${k}=${verdicts[i]}`).join(", ")}`);
  assert.equal(verdicts[0], "NOT_SUITABLE");
});

test("a genuinely flat part with only through features is a waterjet candidate", () => {
  const through = feature({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.25, through: true, centerX: 0, centerY: 0 });
  const a = run({ stock: PLATE, features: [through], intent: known({ quantity: P(100), annualVolume: P(100) }) });
  assert.ok(["VIABLE", "INVESTIGATE"].includes(verdictOf(a, "WATERJET")!), `got ${verdictOf(a, "WATERJET")}`);
  assert.match(a.headline, /through-cut/i);
});

test("a thick block is never a waterjet candidate", () => {
  const a = run({ stock: BLOCK, features: [] });
  assert.equal(verdictOf(a, "WATERJET"), "NOT_SUITABLE");
  assert.ok(
    a.recommendations.find((r) => r.process === "WATERJET")!.blockers.length > 0,
    "it must say why",
  );
});

test("no stock recorded means the geometry cannot be judged flat", () => {
  const a = run({ stock: null, features: [] });
  assert.equal(verdictOf(a, "WATERJET"), "NOT_SUITABLE");
});

test("waterjet still says the tolerances it cannot hold", () => {
  const through = feature({ id: "h1", kind: "DRILLED_HOLE", label: "hole", diameter: 0.25, through: true, centerX: 0, centerY: 0 });
  const a = run({ stock: PLATE, features: [through] });
  const rec = a.recommendations.find((r) => r.process === "WATERJET")!;
  assert.ok(rec.rationale.some((r) => /still need machining|tolerance/i.test(r)), "a blank is not a finished part");
});

/* ---------------- Nothing is presented as computed that is not ---------------- */

test("the volume crossovers say what they are", () => {
  // A fixed list of three numbers was gated on machinedUnitCost being
  // non-null while never reading it, so it appeared under "volume crossovers
  // to watch" as though it had been worked out against this part. The volumes
  // are identical whether the part costs $5 or $500.
  const cheap = run({ machinedUnitCost: 5 }).volumeCrossovers;
  const dear = run({ machinedUnitCost: 500 }).volumeCrossovers;
  assert.deepEqual(cheap, dear, "precondition: they do not depend on the cost");
  for (const c of cheap) {
    assert.match(c.note, /not computed against this part/i, `"${c.note}" implies it was calculated`);
  }
});

test("the crossovers appear whether or not a machining cost exists", () => {
  // Gating a constant on an input it does not use is what made it look
  // computed in the first place.
  assert.deepEqual(run({ machinedUnitCost: null }).volumeCrossovers, run({ machinedUnitCost: 40 }).volumeCrossovers);
});

test("the crossovers are in ascending order", () => {
  const v = run().volumeCrossovers.map((c) => c.volume);
  assert.deepEqual(v, [...v].sort((a, b) => a - b));
});

test("buying off the shelf is declared unimplemented rather than answered", () => {
  const rec = run().recommendations.find((r) => r.process === "PURCHASE_COTS")!;
  assert.equal(rec.verdict, "INSUFFICIENT_DATA");
  assert.ok(rec.blockers.some((b) => /no catalogue matching/i.test(b)), "a SHELL feature says so");
});

/* ---------------- Shape ---------------- */

test("every recommendation carries a reason, and a blocked one carries a blocker", () => {
  for (const inp of [run(), run({ intent: intent() }), run({ stock: PLATE })]) {
    for (const r of inp.recommendations) {
      assert.ok(r.rationale.length > 0, `${r.process} gives no rationale`);
      assert.ok(PROCESSES.includes(r.process), `${r.process} is outside the vocabulary`);
      assert.ok(PROCESS_LABEL[r.process], `${r.process} has no label`);
      assert.ok(r.volumeBand.length > 0, `${r.process} states no volume band`);
      if (r.verdict === "INSUFFICIENT_DATA") {
        assert.ok(r.blockers.length > 0, `${r.process} is blocked but names nothing`);
      }
    }
  }
});

test("machining is always in the list, because it is the baseline", () => {
  for (const inp of [run(), run({ intent: intent() }), run({ stock: PLATE }), run({ stock: BLOCK })]) {
    assert.ok(inp.recommendations.some((r) => r.process === "CNC_BILLET"));
  }
});

test("no process appears twice", () => {
  const list = run().recommendations.map((r) => r.process);
  assert.equal(new Set(list).size, list.length);
});

test("the headline never prints undefined or NaN", () => {
  for (const inp of [run(), run({ intent: intent() }), run({ stock: PLATE }), run({ intent: known({ quantity: P(5000), annualVolume: P(5000) }) })]) {
    assert.ok(!/undefined|NaN|null/.test(inp.headline), inp.headline);
  }
});

test("annual volume drives the answer ahead of lot quantity", () => {
  // Ten parts this month against five thousand a year is a five thousand a
  // year decision.
  const a = run({ intent: known({ quantity: P(10), annualVolume: P(5000) }) });
  assert.equal(a.quantity, 10);
  assert.equal(a.annualVolume, 5000);
  assert.equal(verdictOf(a, "CASTING"), "INVESTIGATE");
});

test("the analysis is deterministic", () => {
  assert.deepEqual(run({ stock: PLATE }), run({ stock: PLATE }));
});
