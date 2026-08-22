import { test } from "node:test";
import assert from "node:assert/strict";
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
