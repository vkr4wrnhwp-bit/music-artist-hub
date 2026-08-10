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
