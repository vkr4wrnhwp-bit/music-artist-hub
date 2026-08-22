import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateTurnReadiness, type TurnReadinessInput } from "@/lib/manufacturing/turn/readiness";
import type { TurnAnalysis } from "@/lib/manufacturing/turn/analysis";

/**
 * The lathe's readiness gates. Principle 1 applies here the same way it does
 * to milling: the aggregate is the worst unresolved required gate, and a gate
 * that cannot fail is not a gate.
 */

const ok = (detail = "within the guideline"): TurnAnalysis => ({
  verdict: "PASS", detail, recommendations: [], missingInputs: [], assumptions: [], developmentAnalysis: true,
});
const bad = (detail = "outside the guideline"): TurnAnalysis => ({ ...ok(detail), verdict: "FAIL" });

const input = (over: Partial<TurnReadinessInput> = {}): TurnReadinessInput =>
  ({
    profile: { segments: [], stockDiameter: 1, stockLength: 6 },
    materialKnown: true,
    latheSelected: true,
    workholdingSelected: true,
    grip: ok(),
    stickout: ok(),
    boringBar: null,
    partOff: null,
    toolsAssigned: 2,
    toolsRequired: 2,
    chuckRpmKnown: true,
    inspectionCapable: true,
    postSelected: true,
    humanApproved: true,
    cssUsed: false,
    ...over,
  }) as unknown as TurnReadinessInput;

const gate = (over: Partial<TurnReadinessInput>, id: string) =>
  evaluateTurnReadiness(input(over)).gates.find((g) => g.id === id);

/* ---------------- A gate that cannot fail ---------------- */

test("the material gate fails when no material is recorded", () => {
  // buildTurnPackage passed `materialKnown: true` as a literal, and this is a
  // PASS/FAIL gate — so the material gate on every turned part could not
  // fail, whatever the part actually said.
  assert.equal(gate({ materialKnown: false }, "material")?.status, "FAIL");
  assert.equal(gate({ materialKnown: true }, "material")?.status, "PASS");
});

test("an unrecorded material makes the part not ready to run", () => {
  assert.equal(evaluateTurnReadiness(input({ materialKnown: false })).overall, "NOT_READY_TO_RUN");
});

/* ---------------- A plan that bores with no bar ---------------- */

test("a plan that bores with no boring bar on file reports an unassessed gate", () => {
  // boringBar: null used to mean only "this plan does not bore". A plan that
  // DID bore with no bar recorded got the same null, so the gate vanished
  // from the report altogether — the length-to-diameter risk was neither
  // assessed nor mentioned.
  const g = gate({ boringBarUnrecorded: true }, "boring-bar");
  assert.ok(g, "the gate must appear");
  assert.equal(g.status, "NOT_ATTEMPTED");
  assert.match(g.detail, /no boring bar/i);
});

test("a plan that does not bore has no boring-bar gate at all", () => {
  // The other meaning of null, which stays.
  assert.equal(gate({ boringBar: null, boringBarUnrecorded: false }, "boring-bar"), undefined);
});

test("an unassessable boring bar blocks, rather than passing quietly", () => {
  assert.equal(evaluateTurnReadiness(input({ boringBarUnrecorded: true })).overall, "NOT_READY_TO_RUN");
});

test("a bar that was assessed reports its own verdict", () => {
  assert.equal(gate({ boringBar: ok("2.0xD within guideline") }, "boring-bar")?.status, "PASS");
  assert.equal(gate({ boringBar: bad("8.0xD against a 4xD guideline") }, "boring-bar")?.status, "FAIL");
});

/* ---------------- Worst-gate aggregation ---------------- */

test("everything passing is ready to run", () => {
  assert.equal(evaluateTurnReadiness(input()).overall, "READY_TO_RUN");
});

test("one blocking failure is enough, whatever else passes", () => {
  for (const over of [
    { materialKnown: false },
    { latheSelected: false },
    { workholdingSelected: false },
    { grip: bad() },
    { stickout: bad() },
    { humanApproved: false },
    { postSelected: false },
  ]) {
    assert.equal(
      evaluateTurnReadiness(input(over)).overall,
      "NOT_READY_TO_RUN",
      `${Object.keys(over)[0]} did not block`,
    );
  }
});

test("an unassessed blocking gate blocks as hard as a failed one", () => {
  // NOT_ATTEMPTED is this vocabulary's "could not be checked", and something
  // nobody checked is not something that passed.
  assert.equal(evaluateTurnReadiness(input({ grip: null })).overall, "NOT_READY_TO_RUN");
  assert.equal(evaluateTurnReadiness(input({ stickout: null })).overall, "NOT_READY_TO_RUN");
});

test("the aggregate is never better than its worst gate", () => {
  const r = evaluateTurnReadiness(input({ grip: bad(), stickout: ok(), materialKnown: true }));
  assert.equal(r.overall, "NOT_READY_TO_RUN");
  assert.ok(r.gates.some((g) => g.status === "PASS"), "and passing gates are still reported as passing");
});

test("every gate states a detail, not just a status", () => {
  for (const g of evaluateTurnReadiness(input({ boringBarUnrecorded: true })).gates) {
    assert.ok(g.label.length > 2, `${g.id} has no label`);
    assert.ok(g.detail.length > 5, `${g.id} states no detail`);
    assert.ok(!/undefined|NaN/.test(g.detail), `${g.id}: ${g.detail}`);
  }
});

test("gate ids are unique and the evaluation is deterministic", () => {
  const r = evaluateTurnReadiness(input({ boringBarUnrecorded: true }));
  assert.equal(new Set(r.gates.map((g) => g.id)).size, r.gates.length);
  assert.deepEqual(r, evaluateTurnReadiness(input({ boringBarUnrecorded: true })));
});
