import { test } from "node:test";
import assert from "node:assert/strict";
import { assessHoldingMargin, type HoldingMarginInput } from "@/lib/engines/holding-margin";
import type { CuttingForceEstimate } from "@/lib/engines/cutting-force";

/**
 * The holding model decides whether a setup keeps the part in the vise.
 * These tests pin its honesty rules — missing inputs return null rather
 * than a default, tipping governs when the lever arm is long, and the
 * DEVELOPMENT ANALYSIS label cannot be dropped.
 */

const force = (peak: number): CuttingForceEstimate =>
  ({
    ok: true, tangential: peak * 0.6, radial: peak * 0.3, axial: peak * 0.2,
    resultant: peak * 0.7, peakTangential: peak, spindlePower: 1, materialRemovalRate: 1,
    feedRate: 20,
  }) as CuttingForceEstimate;

const base: HoldingMarginInput = {
  clampForce: 4000,
  jawSurface: "SMOOTH",
  gripDepth: 0.375,
  gripLength: 4,
  jawHeight: 1,
  hasPositiveStop: false,
  force: force(150),
  cutHeightAboveJaws: 0.375,
};

test("missing clamp force yields null margin and names the missing input", () => {
  const r = assessHoldingMargin({ ...base, clampForce: null });
  assert.equal(r.margin, null);
  assert.ok(r.missingInputs.length > 0);
});

test("a positive stop adds resistance beyond friction alone", () => {
  const frictionOnly = assessHoldingMargin(base);
  const withStop = assessHoldingMargin({
    ...base,
    hasPositiveStop: true,
    stopContactArea: 0.5,
    jawYieldStrength: 40000,
  });
  assert.ok(frictionOnly.resistingForce !== null && withStop.resistingForce !== null);
  assert.ok(withStop.resistingForce! > frictionOnly.resistingForce!);
});

test("shallow grip with the cut high above the jaws is governed by tipping", () => {
  const r = assessHoldingMargin({ ...base, gripDepth: 0.08, cutHeightAboveJaws: 0.7 });
  assert.equal(r.governingMode, "TIPPING");
  assert.ok(r.tippingMargin !== null && r.slidingMargin !== null);
  assert.ok(r.tippingMargin! < r.slidingMargin!, "tipping must be the worse mode here");
  // The governing margin is the worst one — never an average of the two.
  assert.equal(r.margin, r.tippingMargin);
});

test("deep grip on the same cut improves the tipping margin", () => {
  const shallow = assessHoldingMargin({ ...base, gripDepth: 0.08, cutHeightAboveJaws: 0.7 });
  const deep = assessHoldingMargin({ ...base, gripDepth: 0.375, cutHeightAboveJaws: 0.7 });
  assert.ok(shallow.tippingMargin !== null && deep.tippingMargin !== null);
  assert.ok(deep.tippingMargin! > shallow.tippingMargin!);
});

test("developmentAnalysis is always true — the model is not validated on iron", () => {
  const r = assessHoldingMargin(base);
  assert.equal(r.developmentAnalysis, true);
});

/* ---------------- The verdict, which nothing was pinning ---------------- */

test("the verdict tracks the margin rather than being a constant", () => {
  // Replacing the whole verdict expression with the literal "ADEQUATE" broke
  // none of the tests above. The workholding gate maps INSUFFICIENT to FAIL
  // and the pre-flight turns it into a HIGH finding, so a verdict that never
  // moves takes the entire workholding chain quiet.
  const at = (clampForce: number) => assessHoldingMargin({ ...base, clampForce }).verdict;
  const verdicts = [at(50), at(400), at(20000)];
  assert.equal(new Set(verdicts).size > 1, true, `every clamp force gave the same verdict: ${verdicts.join(", ")}`);
});

test("a weak clamp is INSUFFICIENT and a strong one is ADEQUATE", () => {
  assert.equal(assessHoldingMargin({ ...base, clampForce: 20000 }).verdict, "ADEQUATE");
  assert.equal(assessHoldingMargin({ ...base, clampForce: 20 }).verdict, "INSUFFICIENT");
});

test("the verdict never improves as the grip gets worse", () => {
  const rank = { ADEQUATE: 0, MARGINAL: 1, INSUFFICIENT: 2, INDETERMINATE: 3 } as const;
  let previous = -1;
  for (const clampForce of [20000, 8000, 4000, 1500, 600, 200, 50]) {
    const v = assessHoldingMargin({ ...base, clampForce }).verdict;
    assert.ok(rank[v] >= previous, `${clampForce} lbf reported ${v}, better than the clamp before it`);
    previous = rank[v];
  }
});

test("the target margin is 2x, and the verdict changes across it", () => {
  // Dropping the target to 0.5 left every test passing, so a setup holding at
  // half the load it sees read as adequate.
  // 900 and 800 are here deliberately: without them the list steps straight
  // from 1200 lbf (2.15x, adequate) to 600 lbf (1.07x, insufficient) and never
  // lands in the marginal band at all, so collapsing MARGINAL into ADEQUATE
  // passed every assertion below.
  const results = [20000, 10000, 5000, 2500, 1200, 900, 800, 600, 300, 150, 75, 40].map((clampForce) => ({
    clampForce,
    ...assessHoldingMargin({ ...base, clampForce }),
  }));
  const computed = results.filter((r) => r.margin !== null);
  assert.ok(computed.length > 3, "precondition: the model runs across this range");

  for (const r of computed) {
    if (r.verdict === "ADEQUATE") assert.ok(r.margin! >= 2, `${r.clampForce} lbf called ADEQUATE at ${r.margin}x`);
    if (r.verdict === "INSUFFICIENT") assert.ok(r.margin! < 1.3, `${r.clampForce} lbf called INSUFFICIENT at ${r.margin}x`);
    if (r.verdict === "MARGINAL") {
      assert.ok(r.margin! >= 1.3 && r.margin! < 2, `${r.clampForce} lbf called MARGINAL at ${r.margin}x`);
    }
  }
});

test("MARGINAL is a state the model actually reaches", () => {
  // A verdict nothing ever returns is not a verdict. Collapsing it into
  // ADEQUATE broke nothing, which is the same as saying no test had ever
  // seen one.
  const marginal = [1100, 1000, 900, 850, 800]
    .map((clampForce) => assessHoldingMargin({ ...base, clampForce }))
    .filter((r) => r.verdict === "MARGINAL");
  assert.ok(marginal.length > 0, "no clamp force in the band produced a MARGINAL verdict");
  for (const r of marginal) {
    assert.ok(r.margin! >= 1.3 && r.margin! < 2, `MARGINAL reported at ${r.margin}x`);
    assert.ok(r.recommendations.length > 0, "a marginal grip still has something to say");
  }
});

test("a margin below one is never anything but INSUFFICIENT", () => {
  // Below 1.0 the cut moves the part. There is no reading of that which is
  // marginal.
  for (const clampForce of [10, 30, 60]) {
    const r = assessHoldingMargin({ ...base, clampForce });
    if (r.margin === null || r.margin >= 1) continue;
    assert.equal(r.verdict, "INSUFFICIENT", `${clampForce} lbf gives ${r.margin}x and reads ${r.verdict}`);
  }
});

test("a verdict short of adequate always says what to do about it", () => {
  for (const clampForce of [50, 400]) {
    const r = assessHoldingMargin({ ...base, clampForce });
    if (r.verdict === "ADEQUATE") continue;
    assert.ok(r.recommendations.length > 0, `${clampForce} lbf: ${r.verdict} with nothing to do about it`);
    assert.ok(r.primaryRisk && r.primaryRisk.length > 20, `${clampForce} lbf names no risk`);
  }
});

test("an adequate setup states the target it was measured against", () => {
  const r = assessHoldingMargin({ ...base, clampForce: 20000 });
  assert.equal(r.verdict, "ADEQUATE");
  assert.ok(r.method.length > 10, "the method has to be openable");
});

test("the margin is a ratio of resisting to applied, not an invented score", () => {
  const r = assessHoldingMargin({ ...base, clampForce: 8000 });
  assert.ok(r.margin !== null && r.resistingForce !== null && r.appliedLoad !== null);
  assert.ok(r.margin > 0);
  // Sliding or tipping — whichever governs, the reported margin must be the
  // smaller of the two, never the flattering one.
  assert.ok(r.governingMode === "SLIDING" || r.governingMode === "TIPPING");
});

test("more clamp force never lowers the margin", () => {
  let previous = 0;
  for (const clampForce of [200, 1000, 4000, 12000]) {
    const r = assessHoldingMargin({ ...base, clampForce });
    if (r.margin === null) continue;
    assert.ok(r.margin >= previous, `${clampForce} lbf gave ${r.margin}x, below the weaker clamp before it`);
    previous = r.margin;
  }
});

test("a heavier cut never raises the margin", () => {
  let previous = Infinity;
  for (const peak of [50, 150, 400, 900]) {
    const r = assessHoldingMargin({ ...base, force: force(peak) });
    if (r.margin === null) continue;
    assert.ok(r.margin <= previous, `${peak} lbf of cut gave ${r.margin}x, above the lighter cut before it`);
    previous = r.margin;
  }
});
