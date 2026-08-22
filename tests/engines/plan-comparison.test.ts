import { test } from "node:test";
import assert from "node:assert/strict";
import { comparePlans, type ScoredPlanSummary } from "@/lib/plan-comparison";
import { PHILOSOPHIES, type ThoughtPattern } from "@/lib/engines/machinist";
import type { RiskLevel } from "@/lib/engines/workholding";

/**
 * Five plans, scored by the same deterministic engines, put in front of the
 * person who owns the shop. The comparison deliberately declines to name an
 * overall winner — which axis matters is a business decision — so the failure
 * that matters is naming a winner on an axis nothing was measured on.
 */

const plan = (pattern: ThoughtPattern) => ({ pattern, philosophy: PHILOSOPHIES[pattern] }) as ScoredPlanSummary["plan"];

const scored = (
  pattern: ThoughtPattern,
  over: Partial<Omit<ScoredPlanSummary, "plan">> = {},
): ScoredPlanSummary => ({
  plan: plan(pattern),
  setupCount: 2, distinctTools: 5, operationCount: 8, cycleMinutes: 12,
  risk: "SAFE" as RiskLevel, unitCost: 50, errors: [],
  ...over,
});

const NAME = (p: ThoughtPattern) => PHILOSOPHIES[p].name;

/* ---------------- Nothing is named on an axis nobody measured ---------------- */

test("no plan is called safest when none of their workholding could be assessed", () => {
  // best() takes the minimum RISK_ORDER, and with every plan UNKNOWN it
  // returned the first one — a plan nominated as the safest of five when
  // nothing was known about the risk of any of them.
  const all = comparePlans([
    scored("FASTEST_CYCLE", { risk: "UNKNOWN" }),
    scored("LOWEST_RISK", { risk: "UNKNOWN" }),
    scored("BEST_FINISH", { risk: "UNKNOWN" }),
  ]);
  assert.equal(all.safest, null);
  assert.ok(all.fastest, "the axes that WERE measured are still compared");
  assert.ok(all.cheapest);
});

test("an unassessed plan never wins safest over an assessed one", () => {
  const c = comparePlans([
    scored("FASTEST_CYCLE", { risk: "UNKNOWN" }),
    scored("LOWEST_RISK", { risk: "REVIEW" }),
  ]);
  assert.equal(c.safest, NAME("LOWEST_RISK"), "a known REVIEW beats an unknown");
});

test("the safest plan is the one with the least risk, not the first one listed", () => {
  const c = comparePlans([
    scored("FASTEST_CYCLE", { risk: "HIGH_RISK" }),
    scored("MINIMUM_TOOLING", { risk: "REVIEW" }),
    scored("LOWEST_RISK", { risk: "SAFE" }),
  ]);
  assert.equal(c.safest, NAME("LOWEST_RISK"));
});

test("a definite high risk is never called safest ahead of an unknown", () => {
  // The inverse of the bug this file's header records: while UNKNOWN
  // outranked HIGH_RISK in the shared table, a plan KNOWN to be high risk was
  // nominated as safer than one whose risk could not be computed.
  const c = comparePlans([
    scored("FASTEST_CYCLE", { risk: "HIGH_RISK" }),
    scored("LOWEST_RISK", { risk: "UNKNOWN" }),
  ]);
  assert.equal(c.safest, NAME("FASTEST_CYCLE"), "the only assessed plan is the only candidate");
  // And it is assessed as high risk, which the operator reads beside the name.
});

/* ---------------- A plan the engines could not produce is not a candidate ---------------- */

test("a plan with errors is excluded from every axis", () => {
  const c = comparePlans([
    scored("FASTEST_CYCLE", { cycleMinutes: 1, unitCost: 1, setupCount: 1, distinctTools: 1, errors: ["no tool for the bore"] }),
    scored("LOWEST_RISK", { cycleMinutes: 30, unitCost: 90, setupCount: 3, distinctTools: 9 }),
  ]);
  for (const axis of ["fastest", "cheapest", "fewestSetups", "fewestTools"] as const) {
    assert.equal(c[axis], NAME("LOWEST_RISK"), `${axis} picked a plan the engines refused to produce`);
  }
});

test("a plan with no cycle time is not a candidate either", () => {
  // Zero cycle means no toolpath was generated. Costing it against the
  // default cycle time and then calling it fastest would be a fabricated win.
  const c = comparePlans([
    scored("FASTEST_CYCLE", { cycleMinutes: 0, unitCost: 1 }),
    scored("LOWEST_RISK", { cycleMinutes: 30, unitCost: 90 }),
  ]);
  assert.equal(c.fastest, NAME("LOWEST_RISK"));
  assert.equal(c.cheapest, NAME("LOWEST_RISK"));
});

test("when no plan is usable, nothing is named on any axis", () => {
  const c = comparePlans([
    scored("FASTEST_CYCLE", { errors: ["x"] }),
    scored("LOWEST_RISK", { cycleMinutes: 0 }),
  ]);
  assert.deepEqual(c, { fastest: null, cheapest: null, safest: null, fewestSetups: null, fewestTools: null });
});

test("an empty list names nothing", () => {
  assert.deepEqual(comparePlans([]), { fastest: null, cheapest: null, safest: null, fewestSetups: null, fewestTools: null });
});

/* ---------------- Each axis measures its own quantity ---------------- */

test("every axis picks by its own number and they do not collapse into one", () => {
  const c = comparePlans([
    scored("FASTEST_CYCLE", { cycleMinutes: 5, unitCost: 90, setupCount: 3, distinctTools: 9, risk: "REVIEW" }),
    scored("MINIMUM_SETUPS", { cycleMinutes: 30, unitCost: 80, setupCount: 1, distinctTools: 7, risk: "REVIEW" }),
    scored("MINIMUM_TOOLING", { cycleMinutes: 25, unitCost: 70, setupCount: 2, distinctTools: 2, risk: "REVIEW" }),
    scored("LOWEST_RISK", { cycleMinutes: 40, unitCost: 60, setupCount: 4, distinctTools: 8, risk: "SAFE" }),
  ]);
  assert.equal(c.fastest, NAME("FASTEST_CYCLE"));
  assert.equal(c.cheapest, NAME("LOWEST_RISK"));
  assert.equal(c.fewestSetups, NAME("MINIMUM_SETUPS"));
  assert.equal(c.fewestTools, NAME("MINIMUM_TOOLING"));
  assert.equal(c.safest, NAME("LOWEST_RISK"));
});

test("fewest tools counts tools, not tool changes", () => {
  // A plan running tools 1, 2, 1, 2 needs two tools and makes four changes.
  // The field was called toolChanges and held the distinct count; the UI has
  // always labelled it "tools", so the number was right and the name was not.
  const c = comparePlans([
    scored("FASTEST_CYCLE", { distinctTools: 8 }),
    scored("MINIMUM_TOOLING", { distinctTools: 3 }),
  ]);
  assert.equal(c.fewestTools, NAME("MINIMUM_TOOLING"));
});

test("no overall winner is declared", () => {
  // Which axis matters belongs to the person who owns the shop.
  const c = comparePlans([scored("FASTEST_CYCLE"), scored("LOWEST_RISK")]);
  assert.ok(!("winner" in c), "the comparison must not pick for them");
  assert.ok(!("best" in c));
});

test("a tie keeps the first plan rather than reporting nothing", () => {
  const c = comparePlans([scored("FASTEST_CYCLE", { cycleMinutes: 10 }), scored("LOWEST_RISK", { cycleMinutes: 10 })]);
  assert.equal(c.fastest, NAME("FASTEST_CYCLE"));
});

test("comparison is deterministic", () => {
  const list = [scored("FASTEST_CYCLE", { cycleMinutes: 5 }), scored("LOWEST_RISK", { risk: "SAFE" })];
  assert.deepEqual(comparePlans(list), comparePlans(list));
});
