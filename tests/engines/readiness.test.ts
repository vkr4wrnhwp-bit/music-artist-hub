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
 * The distinction these pin down is the whole reason the gate is separate
 * from tool availability: a changer nobody has mapped must not read the same
 * as a changer that is missing a cutter. Absence of evidence is not evidence
 * of absence, and a gate that confuses the two lies in one direction or the
 * other every time it is asked.
 */

const MACHINE = {
  id: "m1",
  manufacturer: "Haas",
  model: "VF-2",
  controller: "HAAS_NGC",
  machineType: "VMC_3AXIS",
  axisCount: 3,
  travelsX: 30, travelsY: 16, travelsZ: 20,
  tableX: 36, tableY: 14,
  maxSpindleRPM: 8100, maxSpindlePower: 30, maxSpindleTorque: 90,
  maxFeed: 500, maxRapid: 1000, axisAccel: null,
  toolChangerCapacity: 20, maxToolDiameter: 3, maxToolLength: 12, maxToolWeight: 12,
  coolantTypes: ["FLOOD"], throughSpindleCoolant: false,
  probe: false, toolSetter: false, fourthAxis: false, fifthAxis: false,
  supportedPostProcessor: "haas-ngc-dev", isReferenceProfile: false,
} as ReadinessInput["machine"];

function toolNumbered(n: number) {
  return {
    id: `t${n}`, toolNumber: n, toolClass: "FLAT_END_MILL", description: `T${n}`,
    diameter: 0.5, cornerRadius: 0, flutes: 3, material: "CARBIDE",
    fluteLength: 1, overallLength: 3, stickout: 1.5,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8100,
    recommendedMaterials: [], chiploadMin: 0.002, chiploadMax: 0.005,
    sfmMin: 600, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
    condition: "GOOD", regrindCount: 0,
  } as ReadinessInput["tools"][number];
}

const loadingGate = (r: ReturnType<typeof evaluateReadiness>) => r.gates.find((g) => g.id === "tool-loading");

/** Same lookup, but asserts the gate is present so the tests read cleanly. */
function requireLoadingGate(r: ReturnType<typeof evaluateReadiness>) {
  const g = loadingGate(r);
  assert.ok(g, "the tooling-loaded gate must exist once tools are assigned");
  return g;
}

test("an unmapped changer is NOT_ATTEMPTED, never a pass and never MISSING", () => {
  const r = evaluateReadiness({ ...emptyInput(), machine: MACHINE, tools: [toolNumbered(1)], carousel: null });
  const g = requireLoadingGate(r);
  assert.equal(g.status, "NOT_ATTEMPTED");
  // It must not claim the tool is absent — that is the failure mode.
  assert.ok(!/not in the/i.test(g.detail));
});

test("an empty carousel list is treated as unmapped, not as an empty machine", () => {
  const r = evaluateReadiness({
    ...emptyInput(), machine: MACHINE, tools: [toolNumbered(1)],
    carousel: { machineId: "m1", loadedToolNumbers: [] },
  });
  assert.equal(requireLoadingGate(r).status, "NOT_ATTEMPTED");
});

test("a mapped changer missing a required tool is MISSING and names it", () => {
  const r = evaluateReadiness({
    ...emptyInput(), machine: MACHINE, tools: [toolNumbered(1), toolNumbered(7)],
    carousel: { machineId: "m1", loadedToolNumbers: [1, 2, 3] },
  });
  const g = requireLoadingGate(r);
  assert.equal(g.status, "MISSING");
  assert.ok(g.detail.includes("T7"), "the gate must name the tool that is not loaded");
  assert.ok(!g.detail.includes("T1"), "a loaded tool must not be reported as absent");
});

test("a mapped changer holding every required tool passes", () => {
  const r = evaluateReadiness({
    ...emptyInput(), machine: MACHINE, tools: [toolNumbered(1), toolNumbered(2)],
    carousel: { machineId: "m1", loadedToolNumbers: [1, 2, 3] },
  });
  assert.equal(requireLoadingGate(r).status, "PASS");
});

test("no assigned machine means no changer to check against", () => {
  const r = evaluateReadiness({ ...emptyInput(), machine: null, tools: [toolNumbered(1)], carousel: null });
  assert.equal(requireLoadingGate(r).status, "NOT_ATTEMPTED");
});

test("the gate does not appear at all when no tools are assigned", () => {
  const r = evaluateReadiness({ ...emptyInput(), machine: MACHINE, tools: [] });
  assert.equal(loadingGate(r), undefined);
});

test("a missing tool never averages away — it blocks READY_TO_RUN", () => {
  const r = evaluateReadiness({
    ...emptyInput(), machine: MACHINE, tools: [toolNumbered(1), toolNumbered(9)],
    carousel: { machineId: "m1", loadedToolNumbers: [1] },
  });
  assert.notEqual(r.overall, "READY_TO_RUN");
  assert.ok(r.blockingCount > 0);
});
