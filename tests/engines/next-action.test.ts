import { test } from "node:test";
import assert from "node:assert/strict";
import { nextActions } from "@/lib/engines/next-action";
import { READINESS_GATE_IDS, type ReadinessGate, type ReadinessGateId, type ReadinessReport, type GateStatus } from "@/lib/engines/readiness";
import type { WorkholdingAssessment } from "@/lib/engines/workholding";

/**
 * "Of everything unresolved, what is the single most useful thing to do
 * next?" — and by default the operator is shown three answers. So the failure
 * that matters is not a wrong ordering in the abstract: it is a blocking item
 * falling off the end of a three-item list, or an action arriving with
 * nowhere to go and do it.
 *
 * The resolution ORDER itself is not pinned item by item. Whether corners
 * should be resolved before tools is a judgement a shop might argue with.
 * What is pinned is that every gate has a place in it and a route, that
 * blocking always precedes review, and that nothing blocking is silently
 * dropped.
 */

const gate = (id: ReadinessGateId, status: GateStatus, actions = [`Do the ${id} thing`]): ReadinessGate => ({
  id, label: id, status, detail: `Detail for ${id}`, blocking: true, actions,
});

const report = (gates: ReadinessGate[], overall: ReadinessReport["overall"] = "NOT_READY_TO_RUN"): ReadinessReport => ({
  gates, overall, criticalApplication: false, blockingCount: 0, capability: [],
});

const margin = (verdict: string, recommendations = ["Cut soft jaws with a 0.375 step"]) =>
  ({
    holdingMargin: {
      verdict, margin: 0.8, recommendations,
      primaryRisk: "The part will slide at peak load.",
    },
  }) as unknown as WorkholdingAssessment;

/* ---------------- Every gate has somewhere to go ---------------- */

test("every gate readiness can emit has a route the operator can follow", () => {
  // tool-loading and critical-review were both missing from the route table.
  // The action read "load T3 and T7 into the changer" with href null — an
  // instruction with nowhere to carry it out. tool-loading was added during
  // this session's work and neither table was updated, which is what an
  // untested lookup table does.
  for (const id of READINESS_GATE_IDS) {
    const [action] = nextActions(report([gate(id, "MISSING")]), "p1", null, 1);
    assert.ok(action, `${id} produced no action`);
    assert.ok(action.href, `${id} offers no link`);
    assert.ok(action.linkLabel, `${id} offers no link label`);
  }
});

test("every gate has a place in the resolution order", () => {
  // A gate absent from the order ranks last among its peers, so it is the
  // thing an operator is told about only after everything else.
  //
  // Each gate is paired against `approval`, which is deliberately the last
  // entry in the order. Anything that sorts behind approval is not in the
  // list at all.
  for (const id of READINESS_GATE_IDS) {
    if (id === "approval") continue;
    const actions = nextActions(report([gate("approval", "MISSING"), gate(id, "MISSING")]), "p1", null, 5);
    assert.equal(actions[0].gateId, id, `${id} sorts behind approval, so it is missing from the resolution order`);
  }
});

test("an action names what to do, why, and where", () => {
  const [a] = nextActions(report([gate("workholding", "FAIL")]), "p1", null, 1);
  assert.ok(a.action.length > 5);
  assert.ok(a.reason.length > 5, "the reason is the gate's evidence, not a restatement of its label");
  assert.notEqual(a.action, a.reason);
  assert.equal(a.gateId, "workholding");
});

test("a gate with no suggested actions still produces an instruction", () => {
  const [a] = nextActions(report([gate("geometry", "MISSING", [])]), "p1", null, 1);
  assert.ok(a.action.length > 5, "a gate that suggests nothing must not produce an empty instruction");
});

/* ---------------- Blocking is never dropped ---------------- */

test("a blocking holding-margin recommendation survives a three-item list", () => {
  // The replacement was pushed onto the end of an ALREADY SORTED array when
  // the workholding gate itself had passed, so a verdict of INSUFFICIENT
  // landed behind every review item and, at the default limit of three, was
  // cut off entirely. The engine whose whole job is naming the most useful
  // next thing dropped a blocking workholding finding on the floor.
  const actions = nextActions(
    report([gate("tolerance", "REVIEW"), gate("inspection", "REVIEW"), gate("nc", "REVIEW")]),
    "p1",
    margin("INSUFFICIENT"),
    3,
  );
  assert.ok(actions.some((a) => /soft jaws/.test(a.action)), `dropped: [${actions.map((a) => a.action).join(" | ")}]`);
  assert.equal(actions[0].severity, "BLOCKING", "and it leads, because nothing else here blocks");
});

test("nothing blocking ever sits behind something that only needs review", () => {
  const actions = nextActions(
    report([
      gate("tolerance", "REVIEW"), gate("inspection", "REVIEW"),
      gate("geometry", "MISSING"), gate("nc", "FAIL"),
    ]),
    "p1",
    margin("INSUFFICIENT"),
    10,
  );
  const firstReview = actions.findIndex((a) => a.severity !== "BLOCKING");
  if (firstReview === -1) return;
  for (const a of actions.slice(firstReview)) {
    assert.notEqual(a.severity, "BLOCKING", `a blocking action sits behind a review one: ${a.action}`);
  }
});

test("the workholding gate is replaced by the specific advice, not duplicated", () => {
  const actions = nextActions(
    report([gate("geometry", "MISSING"), gate("workholding", "FAIL")]),
    "p1",
    margin("INSUFFICIENT"),
    5,
  );
  assert.equal(actions.filter((a) => a.gateId === "workholding").length, 1);
  assert.match(actions.find((a) => a.gateId === "workholding")!.action, /soft jaws/);
});

test("an adequate margin adds nothing", () => {
  const actions = nextActions(report([gate("tolerance", "REVIEW")]), "p1", margin("ADEQUATE"), 5);
  assert.equal(actions.length, 1);
  assert.ok(!actions.some((a) => /soft jaws/.test(a.action)));
});

test("a margin with no recommendation does not invent one", () => {
  const actions = nextActions(report([gate("tolerance", "REVIEW")]), "p1", margin("INSUFFICIENT", []), 5);
  assert.ok(!actions.some((a) => a.gateId === "workholding"), "nothing to say is not the same as saying nothing useful");
});

test("a marginal verdict is review, an insufficient one blocks", () => {
  const at = (v: string) =>
    nextActions(report([gate("tolerance", "REVIEW")]), "p1", margin(v), 5).find((a) => a.gateId === "workholding");
  assert.equal(at("INSUFFICIENT")?.severity, "BLOCKING");
  assert.equal(at("MARGINAL")?.severity, "REVIEW");
});

/* ---------------- The operator is never told nothing ---------------- */

test("a part with nothing evaluated still gets an answer", () => {
  // This returned an empty array: no gate was unresolved because none had
  // been attempted, and the part was not ready. The one engine an operator
  // asks "what do I do next" said nothing at all.
  const actions = nextActions(
    report([gate("geometry", "NOT_ATTEMPTED"), gate("nc", "NOT_ATTEMPTED")], "NOT_READY_TO_RUN"),
    "p1",
    null,
    3,
  );
  assert.equal(actions.length, 1);
  assert.ok(actions[0].href, "and it says where to go");
  assert.ok(!/every gate passes/i.test(actions[0].reason), "it must not claim the gates passed");
});

test("a part that is ready is told to run it and record what happened", () => {
  const actions = nextActions(report([gate("geometry", "PASS")], "READY_TO_RUN"), "p1", null, 3);
  assert.equal(actions.length, 1);
  assert.equal(actions[0].severity, "IMPROVEMENT");
  assert.match(actions[0].action, /first article/i);
});

test("a ready part and an unevaluated one are not told the same thing", () => {
  const ready = nextActions(report([gate("geometry", "PASS")], "READY_TO_RUN"), "p1", null, 3);
  const untouched = nextActions(report([gate("geometry", "NOT_ATTEMPTED")], "NOT_READY_TO_RUN"), "p1", null, 3);
  assert.notEqual(ready[0].action, untouched[0].action);
  assert.notEqual(ready[0].severity, untouched[0].severity);
});

test("passing and not-attempted gates raise nothing on their own", () => {
  const actions = nextActions(
    report([gate("geometry", "PASS"), gate("nc", "NOT_ATTEMPTED"), gate("tolerance", "REVIEW")]),
    "p1",
    null,
    5,
  );
  assert.deepEqual(actions.map((a) => a.gateId), ["tolerance"]);
});

/* ---------------- Ordering ---------------- */

test("what invalidates what decides the order among equals", () => {
  // The file's own example: there is no point resolving the grip on setup 2
  // while the bore's nominal is still a guess, because the nominal decides
  // the tool, which decides the load, which decides the grip.
  const actions = nextActions(
    report([gate("workholding", "MISSING"), gate("tools", "MISSING"), gate("geometry", "MISSING")]),
    "p1",
    null,
    5,
  );
  assert.deepEqual(actions.map((a) => a.gateId), ["geometry", "tools", "workholding"]);
});

test("the limit is respected and defaults to three", () => {
  const gates = READINESS_GATE_IDS.slice(0, 6).map((id) => gate(id, "MISSING"));
  assert.equal(nextActions(report(gates), "p1", null).length, 3);
  assert.equal(nextActions(report(gates), "p1", null, 1).length, 1);
  assert.equal(nextActions(report(gates), "p1", null, 99).length, 6);
});

test("the part id reaches every link", () => {
  for (const id of READINESS_GATE_IDS) {
    const [a] = nextActions(report([gate(id, "MISSING")]), "part-42", null, 1);
    assert.ok(a.href, `${id} has no href`);
    // Some routes are shop-wide (machines, metrology) and correctly carry no
    // part id; the ones that are part-scoped must carry the right one.
    if (a.href.startsWith("/parts/")) assert.match(a.href, /^\/parts\/part-42(\/|$)/, `${id} -> ${a.href}`);
  }
});

test("the result is deterministic", () => {
  const r = report([gate("geometry", "MISSING"), gate("workholding", "FAIL"), gate("tolerance", "REVIEW")]);
  assert.deepEqual(nextActions(r, "p1", margin("INSUFFICIENT"), 5), nextActions(r, "p1", margin("INSUFFICIENT"), 5));
});
