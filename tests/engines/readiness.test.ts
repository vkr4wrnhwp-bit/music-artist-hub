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
