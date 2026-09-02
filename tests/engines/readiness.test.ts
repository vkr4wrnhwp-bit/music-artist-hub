import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evaluateReadiness, type ReadinessInput } from "@/lib/engines/readiness";
import { emptyPartIntent } from "@/lib/domain/part-intent";

/**
 * Readiness is gate-based and the aggregate is the worst unresolved required
 * gate. These tests pin the aggregation invariants rather than any single
 * gate's wording — the rule that must never regress is that no arithmetic
 * ever averages a failure away.
 */

const emptyInput = (): ReadinessInput => ({
  intent: emptyPartIntent("Test part"),
  stock: null,
  features: [],
  machine: null,
  tools: [],
  workholding: null,
  workholdingAssessment: null,
  hasInspectionPlan: false,
  instruments: [],
  simulationRun: false,
  ncGenerated: false,
  operatorApproved: false,
});

test("an empty part is NOT_READY_TO_RUN with blocking gates, never a score", () => {
  const r = evaluateReadiness(emptyInput());
  assert.equal(r.overall, "NOT_READY_TO_RUN");
  assert.ok(r.blockingCount > 0);
});

test("READY_TO_RUN holds exactly when every blocking gate passes and nothing fails", () => {
  // The invariant, checked against the report the engine itself produced:
  // overall must be derivable from the gates by worst-case rules alone.
  const r = evaluateReadiness(emptyInput());
  const blockingClean = r.gates.every((g) => !g.blocking || g.status === "PASS");
  const anyFail = r.gates.some((g) => g.status === "FAIL" || g.status === "MISSING");
  if (r.overall === "READY_TO_RUN") {
    assert.ok(blockingClean && !anyFail);
  } else {
    assert.ok(!blockingClean || anyFail || r.gates.some((g) => g.status !== "PASS"));
  }
});

test("zero critical features is NOT_ATTEMPTED on the tolerance gate, not a pass", () => {
  const r = evaluateReadiness(emptyInput());
  const tolerance = r.gates.find((g) => g.id === "tolerance");
  assert.ok(tolerance);
  assert.equal(tolerance!.status, "NOT_ATTEMPTED");
});

test("blockingCount counts only blocking gates that are not PASS", () => {
  const r = evaluateReadiness(emptyInput());
  const derived = r.gates.filter((g) => g.blocking && g.status !== "PASS").length;
  assert.equal(r.blockingCount, derived);
});

/* ------------------------------------------------------------------ */
/* Tooling loaded — the carousel gate                                  */
/* ------------------------------------------------------------------ */

/**
 * Two distinctions carry this gate, and both are easy to get wrong.
 *
 * A changer nobody has mapped must not read the same as a changer that is
 * missing a cutter — absence of evidence is not evidence of absence.
 *
 * And the check is PER SETUP, because `Setup.machineId` is per setup. A part
 * roughed on one machine and finished on another has tools that belong to
 * different changers, and an earlier version of this gate checked every tool
 * against one "primary" machine — which reported correctly-loaded tools as
 * missing the moment a part spanned two machines.
 */

type Loading = NonNullable<ReadinessInput["toolLoading"]>;

const loadingGate = (r: ReturnType<typeof evaluateReadiness>) => r.gates.find((g) => g.id === "tool-loading");

function requireLoadingGate(r: ReturnType<typeof evaluateReadiness>) {
  const g = loadingGate(r);
  assert.ok(g, "the tooling-loaded gate must exist once a setup needs tools");
  return g;
}

const withLoading = (toolLoading: Loading) => evaluateReadiness({ ...emptyInput(), toolLoading });

test("an unmapped changer is NOT_ATTEMPTED, and never claims the tool is absent", () => {
  const g = requireLoadingGate(
    withLoading([{ setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1], loadedToolNumbers: null }]),
  );
  assert.equal(g.status, "NOT_ATTEMPTED");
  assert.ok(!/not in the/i.test(g.detail));
});

test("an empty carousel list is unmapped, not an empty machine", () => {
  const g = requireLoadingGate(
    withLoading([{ setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1], loadedToolNumbers: [] }]),
  );
  assert.equal(g.status, "NOT_ATTEMPTED");
});

test("a setup with no machine has nothing to check against", () => {
  const g = requireLoadingGate(
    withLoading([{ setupName: "Setup 01", machineLabel: null, requiredToolNumbers: [1], loadedToolNumbers: null }]),
  );
  assert.equal(g.status, "NOT_ATTEMPTED");
  assert.ok(/no machine assigned/i.test(g.detail));
});

test("a mapped changer missing a required tool is MISSING and names it", () => {
  const g = requireLoadingGate(
    withLoading([
      { setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1, 7], loadedToolNumbers: [1, 2, 3] },
    ]),
  );
  assert.equal(g.status, "MISSING");
  assert.ok(g.detail.includes("T7"), "the gate must name the tool that is not loaded");
  assert.ok(!g.detail.includes("T1"), "a loaded tool must not be reported as absent");
});

test("a mapped changer holding every required tool passes", () => {
  const g = requireLoadingGate(
    withLoading([{ setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1, 2], loadedToolNumbers: [1, 2, 3] }]),
  );
  assert.equal(g.status, "PASS");
});

test("tools are checked against their own setup's machine, not one primary machine", () => {
  // T5 is in the Mori's changer and nowhere near the Haas. Checking both
  // setups against one machine is what the earlier version got wrong.
  const g = requireLoadingGate(
    withLoading([
      { setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1, 2], loadedToolNumbers: [1, 2] },
      { setupName: "Setup 02", machineLabel: "Mori NH4000", requiredToolNumbers: [5], loadedToolNumbers: [5, 6] },
    ]),
  );
  assert.equal(g.status, "PASS", "every tool is in its own setup's changer");
});

test("a tool absent from its own setup's changer is still caught across machines", () => {
  const g = requireLoadingGate(
    withLoading([
      { setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1], loadedToolNumbers: [1] },
      { setupName: "Setup 02", machineLabel: "Mori NH4000", requiredToolNumbers: [5], loadedToolNumbers: [6] },
    ]),
  );
  assert.equal(g.status, "MISSING");
  assert.ok(g.detail.includes("Setup 02"), "the finding must say which setup");
  assert.ok(g.detail.includes("Mori NH4000"), "and which changer");
  assert.ok(g.detail.includes("T5"));
});

test("a real finding outranks an unknown when both are present", () => {
  const g = requireLoadingGate(
    withLoading([
      { setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [9], loadedToolNumbers: [1] },
      { setupName: "Setup 02", machineLabel: "Mori NH4000", requiredToolNumbers: [5], loadedToolNumbers: null },
    ]),
  );
  assert.equal(g.status, "MISSING", "a tool definitely absent is worse than a changer nobody mapped");
});

test("the gate does not appear when no setup needs a tool", () => {
  assert.equal(loadingGate(withLoading([])), undefined);
  assert.equal(
    loadingGate(withLoading([{ setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [], loadedToolNumbers: [1] }])),
    undefined,
  );
});

test("a missing tool never averages away — it blocks READY_TO_RUN", () => {
  const r = withLoading([
    { setupName: "Setup 01", machineLabel: "Haas VF-2", requiredToolNumbers: [1, 9], loadedToolNumbers: [1] },
  ]);
  assert.notEqual(r.overall, "READY_TO_RUN");
  assert.ok(r.blockingCount > 0);
});

/* ---------------- Principle 1: the aggregate is the worst gate ---------------- */

import { inferred, unknown, userValue, value } from "@/lib/provenance";
import { aggregate, SEVERITY, GATE_STATUS, type GateStatus, type ReadinessGate } from "@/lib/engines/readiness";

const g = (status: GateStatus, blocking: boolean, id = "geometry"): ReadinessGate =>
  ({ id, label: id, status, detail: "d", blocking, actions: [] }) as ReadinessGate;

test("a FAIL is the most severe status there is", () => {
  // Inverting this ordering so FAIL ranked LEAST severe broke none of the
  // tests above. That is latent rather than live — every gate that can emit
  // FAIL is also blocking, so blockingFailures catches it first — but `worst`
  // exists to survive someone adding a non-blocking FAIL later, and nothing
  // was checking that it would.
  for (const s of GATE_STATUS) {
    if (s === "FAIL") continue;
    assert.ok(SEVERITY.FAIL > SEVERITY[s], `FAIL must outrank ${s}`);
  }
});

test("the severity ordering is total — no two statuses share a rank", () => {
  const ranks = GATE_STATUS.map((s) => SEVERITY[s]);
  assert.equal(new Set(ranks).size, GATE_STATUS.length, "two statuses sharing a rank makes worst() order-dependent");
});

test("a passing status is the least severe, so nothing hides behind it", () => {
  for (const s of GATE_STATUS) {
    if (s === "PASS") continue;
    assert.ok(SEVERITY[s] > SEVERITY.PASS, `${s} must outrank PASS`);
  }
});

test("nine passes and one failure is not ready", () => {
  // Verbatim from the locked principle: "A part with nine passing gates and
  // one failure is not 90% ready; it is not ready."
  const nine = Array.from({ length: 9 }, () => g("PASS", true));
  assert.notEqual(aggregate([...nine, g("FAIL", true)]).overall, "READY_TO_RUN");
  assert.notEqual(aggregate([...nine, g("FAIL", false)]).overall, "READY_TO_RUN", "even when the failing gate is not blocking");
});

test("a non-blocking FAIL still stops a part being ready to run", () => {
  // The case `worst !== "FAIL"` exists for, and the one nothing reached.
  const r = aggregate([g("PASS", true), g("FAIL", false, "tolerance")]);
  assert.equal(r.overall, "REVIEW_REQUIRED");
  assert.equal(r.blockingCount, 0, "it is genuinely not a blocking gate");
});

test("a blocking gate short of PASS is never ready, whatever the status", () => {
  for (const s of GATE_STATUS) {
    if (s === "PASS") continue;
    const r = aggregate([g("PASS", true), g(s, true, "tools")]);
    assert.equal(r.overall, "NOT_READY_TO_RUN", `a blocking ${s} reported ${r.overall}`);
    assert.equal(r.blockingCount, 1);
  }
});

test("a non-blocking gate short of PASS asks for review rather than blocking", () => {
  for (const s of ["REVIEW", "MISSING", "NOT_ATTEMPTED"] as GateStatus[]) {
    const r = aggregate([g("PASS", true), g(s, false, "tolerance")]);
    assert.equal(r.overall, "READY_TO_RUN", `a non-blocking ${s} blocked the part`);
  }
});

test("everything passing is ready, and an empty gate list is not a claim of readiness by accident", () => {
  assert.equal(aggregate([g("PASS", true), g("PASS", false)]).overall, "READY_TO_RUN");
  // No gates at all means nothing was evaluated. It reports READY_TO_RUN by
  // construction, which is why computeReadiness always emits gates and why
  // next-action does not trust an empty list on its own.
  assert.equal(aggregate([]).overall, "READY_TO_RUN");
});

test("aggregation is a maximum, never an average", () => {
  // The arithmetic principle 1 forbids: no number of passes dilutes a FAIL.
  for (const passes of [0, 1, 5, 50]) {
    const gates = [...Array.from({ length: passes }, () => g("PASS", true)), g("FAIL", true)];
    assert.equal(aggregate(gates).overall, "NOT_READY_TO_RUN", `${passes} passes diluted a FAIL`);
  }
});

test("the blocking count is a count of blocking gates, not of all gates", () => {
  const r = aggregate([g("FAIL", true), g("MISSING", true), g("REVIEW", false), g("PASS", true)]);
  assert.equal(r.blockingCount, 2);
});

test("the material gate cannot be passed by an AI inference, at any score", () => {
  // Locked principle 3, at the gate rather than at the function. The
  // intake parser tags what it read from a drawing as AI_INFERENCE; that is
  // a proposal, and the gate says so until a human signs it.
  const withMaterial = (material: ReturnType<typeof emptyPartIntent>["material"]) =>
    evaluateReadiness({ ...emptyInput(), intent: { ...emptyPartIntent("Test part"), material } });

  const g = (r: ReturnType<typeof evaluateReadiness>) => r.gates.find((x) => x.id === "material")!;

  assert.equal(g(withMaterial(inferred("6061-T6", 0.99))).status, "REVIEW");
  assert.equal(g(withMaterial(value("6061-T6", "AI_INFERENCE", "VERIFIED"))).status, "REVIEW");
  // A human confirming it is what moves the gate — and it is still blocking
  // until they do.
  assert.equal(g(withMaterial(inferred("6061-T6", 0.5))).blocking, true);
  assert.equal(g(withMaterial(userValue("6061-T6"))).status, "PASS");
  assert.equal(g(withMaterial(value("6061-T6", "AI_INFERENCE", "LOW", { confirmedByUser: true }))).status, "PASS");
  // No material at all is MISSING, not REVIEW: there is nothing to confirm.
  assert.equal(g(withMaterial(unknown())).status, "MISSING");
});

/* ---- the counts on screen agree with the engine ---- */

/**
 * A part read NOT READY in the header with nothing beside it saying how many
 * things were in the way. The header recomputed "blocking" as FAIL or MISSING
 * only, while `aggregate` counts every blocking gate that is not PASS — so a
 * blocking gate at NOT_ATTEMPTED (an unmapped tool changer, a setup with no
 * machine assigned) held the part off READY_TO_RUN and appeared in no count.
 *
 * Two counts of the same thing is one count too many.
 */

test("a blocking gate that is not PASS is counted, whatever its status", () => {
  const statuses = ["FAIL", "MISSING", "NOT_ATTEMPTED", "REVIEW"] as const;
  for (const status of statuses) {
    const { blockingCount, overall } = aggregate([g(status, true)]);
    assert.equal(blockingCount, 1, `a blocking gate at ${status} is not counted`);
    assert.notEqual(overall, "READY_TO_RUN", `a blocking gate at ${status} let the part read ready`);
  }
});

test("the header takes the count from the engine rather than recomputing it", () => {
  const src = readFileSync("src/components/part-status.tsx", "utf8");
  assert.ok(
    /readiness\.blockingCount/.test(src),
    "the part status header counts blocking gates itself — it will drift from the verdict beside it",
  );
  assert.ok(
    !/g\.blocking && \(g\.status === "FAIL"/.test(src),
    "the header still keeps its own narrower idea of what blocks",
  );
});

test("the header's blocking and review counts do not overlap", () => {
  const src = readFileSync("src/components/part-status.tsx", "utf8");
  assert.ok(
    /!g\.blocking && g\.status === "REVIEW"/.test(src),
    "a blocking REVIEW gate is counted in both figures, so the two add up to more than there are gates",
  );
});

test("the action banner counts actions, and says so", () => {
  // The banner counts nextActions; the header counts gates. Both said
  // "blocking" and they disagreed on screen — 4 in one, 3 in the other.
  const src = readFileSync("src/components/workspace/workspace.tsx", "utf8");
  assert.ok(
    !/\{blocking\.length\} blocking — action required/.test(src),
    "the banner labels an action count as a gate count",
  );
  assert.ok(/required to clear the blocking gates/.test(src), "the banner does not say what its count is of");
});


/* ------------------------------------------------------------------ */
/* Generating an NC program must not make a part read as less ready    */
/* ------------------------------------------------------------------ */

test("the NC gate is non-blocking whether or not a program exists", () => {
  // It used to be blocking when a program had been generated and non-blocking
  // when none had, so producing a development post made the part read LESS
  // ready than never having produced one — the exact inverse of what the act
  // means. A shop running its own CAM has no CANVAS program and is not less
  // ready for it, and executable NC has its own export gates.
  const src = readFileSync("src/lib/engines/readiness.ts", "utf8");
  const block = /\/\* ---- NC ---- \*\/[\s\S]{0,1200}?\n  \);/.exec(src);
  assert.ok(block, "the NC gate moved — this test cannot check it any more");
  const calls = [...block![0].matchAll(/gate\(\s*"nc"[\s\S]*?,\s*(true|false),/g)].map((m) => m[1]);
  assert.equal(calls.length, 2, `expected both NC branches, found ${calls.length}`);
  assert.deepEqual(calls, ["false", "false"], "the NC gate blocks in one branch and not the other");
});
