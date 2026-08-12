import { test } from "node:test";
import assert from "node:assert/strict";
import {
  advance,
  back,
  canGoBack,
  currentStep,
  flowProgress,
  skip,
  startSession,
  type GuideContext,
} from "@/lib/guide/engine";
import { MAKE_A_PART } from "@/lib/guide/flows";

/**
 * CANVAS GUIDE safety and history. The load-bearing claims: BACK ONE STEP
 * follows the actual visited path and can change nothing but which card is
 * shown; step completion is a property of project state, not of clicks;
 * blockers surface as gates and survive every guide action.
 */

const ctx = (over: Partial<GuideContext> = {}): GuideContext => ({
  partId: "p1",
  hasStock: false,
  hasMachine: true,
  hasMaterial: true,
  featureCount: 5,
  pendingProposals: 0,
  setupCount: 0,
  workholdingAssessed: false,
  toolpathCount: 0,
  simulationRecorded: false,
  approvalExists: false,
  ncProgramExists: false,
  blockingGates: [],
  nextAction: null,
  training: false,
  ...over,
});

test("steps complete from project state, not from clicks", () => {
  const done = ctx({ hasStock: true });
  const s = startSession(MAKE_A_PART, done, "2026-08-12T00:00:00Z");
  // The active step is the first INCOMPLETE one — stock is skipped because
  // the project already has stock, not because anybody pressed next.
  assert.notEqual(s.active, "stock");
  const view = currentStep(MAKE_A_PART, { ...s, active: "stock", history: ["stock"] }, done);
  assert.equal(view!.status, "COMPLETED");
});

test("branching: the proposals step only exists while proposals are pending", () => {
  const withP = ctx({ pendingProposals: 2 });
  const withoutP = ctx();
  const stepsWith = flowProgress(MAKE_A_PART, startSession(MAKE_A_PART, withP, "t"), withP).total;
  const stepsWithout = flowProgress(MAKE_A_PART, startSession(MAKE_A_PART, withoutP, "t"), withoutP).total;
  assert.equal(stepsWith, stepsWithout + 1);
});

test("BACK ONE STEP pops the actual visited history, including through a branch", () => {
  const c = ctx({ pendingProposals: 1, featureCount: 0 });
  let s = startSession(MAKE_A_PART, c, "t");
  assert.equal(s.active, "features");
  assert.equal(canGoBack(s), false); // first step: disabled

  // Project state changes (features appear), user advances — through the
  // proposals branch that only exists in this context.
  const c2 = ctx({ pendingProposals: 1, featureCount: 3 });
  s = advance(MAKE_A_PART, s, c2);
  assert.equal(s.active, "proposals");
  s = advance(MAKE_A_PART, s, ctx({ featureCount: 3 }));
  assert.equal(s.active, "stock");
  assert.deepEqual(s.history, ["features", "proposals", "stock"]);

  // Back follows the path travelled — to proposals, not to order-minus-one
  // in some other context's step list.
  s = back(s);
  assert.equal(s.active, "proposals");
  s = back(s);
  assert.equal(s.active, "features");
  assert.equal(canGoBack(s), false);
  const same = back(s);
  assert.deepEqual(same, s); // disabled at the first step: no-op
});

test("back and skip cannot alter project state — the engine has no write path", () => {
  const c = ctx({ blockingGates: [{ id: "g1", label: "Inspection capability", detail: "±0.0005 needs a bore gauge" }] });
  const frozen = JSON.stringify(c);
  let s = startSession(MAKE_A_PART, c, "t");
  s = advance(MAKE_A_PART, s, c);
  s = skip(MAKE_A_PART, s, c);
  s = back(s);
  s = back(s);
  // The context object is byte-identical after every guide operation.
  assert.equal(JSON.stringify(c), frozen);
});

test("a blocking gate takes priority over the lesson and survives back", () => {
  const blocked = ctx({
    hasStock: true,
    setupCount: 1,
    workholdingAssessed: true,
    toolpathCount: 3,
    simulationRecorded: true,
    blockingGates: [{ id: "insp", label: "Inspection capability", detail: "Calipers cannot verify ±0.0005" }],
  });
  let s = startSession(MAKE_A_PART, blocked, "t");
  // Drive to the gates step along the real path.
  while (s.active !== "gates" && s.active !== null) s = advance(MAKE_A_PART, s, blocked);
  assert.equal(s.active, "gates");
  const view = currentStep(MAKE_A_PART, s, blocked)!;
  assert.equal(view.status, "BLOCKED");
  assert.match(view.blocked!.label, /Inspection capability/);
  // Back changes the card; re-advancing re-encounters the same gate,
  // because the gate lives in project state the guide cannot touch.
  s = back(s);
  s = advance(MAKE_A_PART, s, blocked);
  assert.equal(currentStep(MAKE_A_PART, s, blocked)!.status, "BLOCKED");
});

test("skipping every step finishes the flow without completing anything", () => {
  const c = ctx();
  let s = startSession(MAKE_A_PART, c, "t");
  for (let i = 0; i < 20 && s.active; i++) s = skip(MAKE_A_PART, s, c);
  const p = flowProgress(MAKE_A_PART, s, c);
  assert.equal(p.finished, true);
  // Nothing became COMPLETED by skipping: completion still reads project state.
  assert.equal(p.completed, flowProgress(MAKE_A_PART, startSession(MAKE_A_PART, c, "t"), c).completed);
});

test("guide completion is not readiness: a finished flow leaves blocking gates blocking", () => {
  const c = ctx({
    hasStock: true,
    setupCount: 1,
    workholdingAssessed: true,
    toolpathCount: 3,
    simulationRecorded: true,
    ncProgramExists: true,
    blockingGates: [{ id: "insp", label: "Inspection capability", detail: "unchanged" }],
  });
  let s = startSession(MAKE_A_PART, c, "t");
  for (let i = 0; i < 20 && s.active; i++) s = skip(MAKE_A_PART, s, c);
  assert.equal(flowProgress(MAKE_A_PART, s, c).finished, true);
  assert.equal(c.blockingGates.length, 1); // exactly as it was
});

test("the deliver step does not apply to training projects", () => {
  const train = ctx({ training: true });
  const prod = ctx();
  const t = flowProgress(MAKE_A_PART, startSession(MAKE_A_PART, train, "t"), train).total;
  const pTotal = flowProgress(MAKE_A_PART, startSession(MAKE_A_PART, prod, "t"), prod).total;
  assert.equal(t, pTotal - 1);
});

/* ------------------------------------------------------------------ */
/* TURN_A_SHAFT flow                                                   */
/* ------------------------------------------------------------------ */

import { TURN_A_SHAFT } from "@/lib/guide/flows";

test("TURN_A_SHAFT completes from turning state alone — a done shaft has nothing left to guide", () => {
  const done = ctx({
    hasStock: true, hasMachine: true, featureCount: 8, setupCount: 1,
    workholdingAssessed: true, toolpathCount: 7, ncProgramExists: true, blockingGates: [],
  });
  const s = startSession(TURN_A_SHAFT, done, "2026-08-12T00:00:00Z");
  const p = flowProgress(TURN_A_SHAFT, s, done);
  assert.equal(p.completed, p.total);
});

test("TURN_A_SHAFT hold step surfaces the grip gate as a blocker, and deliver stays gated", () => {
  const gated = ctx({
    hasStock: true, featureCount: 8, setupCount: 1, workholdingAssessed: false, toolpathCount: 7,
    ncProgramExists: true,
    blockingGates: [{ id: "grip", label: "Chuck grip", detail: "Clamp force not recorded — the chuck's actual hydraulic setting." }],
  });
  let s = startSession(TURN_A_SHAFT, gated, "2026-08-12T00:00:00Z");
  // advance to the hold step
  for (let i = 0; i < 6; i++) {
    const v = currentStep(TURN_A_SHAFT, s, gated);
    if (v?.step.id === "hold") break;
    s = advance(TURN_A_SHAFT, s, gated);
  }
  const hold = currentStep(TURN_A_SHAFT, s, gated);
  assert.equal(hold?.step.id, "hold");
  assert.equal(hold?.blocked?.label, "Chuck grip");
  // deliver never reads done while a blocking gate stands
  const deliver = TURN_A_SHAFT.steps.find((x) => x.id === "deliver")!;
  assert.equal(deliver.done(gated), false);
});

test("TURN_A_SHAFT deliver step does not apply to training parts", () => {
  const training = ctx({ training: true });
  const deliver = TURN_A_SHAFT.steps.find((x) => x.id === "deliver")!;
  assert.equal(deliver.applies?.(training), false);
});
