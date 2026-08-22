import { test } from "node:test";
import assert from "node:assert/strict";
import { assessCapability, worstCapability, type Instrument, type CapabilityRequest } from "@/lib/engines/inspection-capability";

/**
 * Inspection capability is a property of the instruments the shop owns.
 * These tests pin the gauge-maker arithmetic and the rule with teeth:
 * no result is ever clearable by confirmation.
 */

const inst = (deviceType: string, uncertainty: number, over: Partial<Instrument> = {}): Instrument => ({
  id: deviceType, deviceType, description: deviceType, resolution: uncertainty / 2,
  uncertainty, rangeMin: 0, rangeMax: 12, calibrated: true, ...over,
});

const req = (band: number | null, over: Partial<CapabilityRequest> = {}): CapabilityRequest => ({
  featureId: "f", featureLabel: "bore", geometry: "INTERNAL_ROUND", nominal: 1.5,
  toleranceBand: band, critical: true, ...over,
});

test("a generous band with a capable instrument is CAPABLE", () => {
  const r = assessCapability(req(0.02), [inst("BORE_GAUGE", 0.0002)]);
  assert.equal(r.verdict, "CAPABLE");
});

test("a tenth-tolerance bore is beyond a two-tenths gauge", () => {
  // Band 0.0005", instrument ±0.0002" — the instrument consumes most of it.
  const r = assessCapability(req(0.0005), [inst("BORE_GAUGE", 0.0002)]);
  assert.notEqual(r.verdict, "CAPABLE");
  assert.ok(r.requiredUncertainty === null || r.requiredUncertainty < 0.0002);
});

test("no instrument that can reach internal geometry means NO_INSTRUMENT", () => {
  const r = assessCapability(req(0.001), [inst("CALIPERS_EXTERNAL_ONLY", 0.002, { deviceType: "SURFACE_PLATE" })]);
  assert.equal(r.verdict, "NO_INSTRUMENT");
});

test("clearableByConfirmation is false on every result, capable or not", () => {
  for (const r of [
    assessCapability(req(0.02), [inst("BORE_GAUGE", 0.0002)]),
    assessCapability(req(0.0005), [inst("BORE_GAUGE", 0.0002)]),
    assessCapability(req(0.001), []),
  ]) {
    assert.equal(r.clearableByConfirmation, false);
  }
});

test("worstCapability reports the worst verdict, never an average", () => {
  const good = assessCapability(req(0.02), [inst("BORE_GAUGE", 0.0002)]);
  const bad = assessCapability(req(0.001), []);
  assert.equal(worstCapability([good, bad]), bad.verdict);
});

test("a rectangular pocket is flat-internal: bore gauge cannot reach it, calipers can", () => {
  const flat = req(0.02, { geometry: "INTERNAL_FLAT", featureLabel: "relief pocket" });
  const boreOnly = assessCapability(flat, [inst("BORE_GAUGE", 0.0002)]);
  assert.equal(boreOnly.verdict, "NO_INSTRUMENT");
  const calipers = assessCapability(flat, [inst("DIGITAL_CALIPER", 0.002)]);
  assert.notEqual(calipers.verdict, "NO_INSTRUMENT");
});

/* ---------------- The gauge-maker's boundaries ---------------- */

test("the 10% target is where CAPABLE ends and MARGINAL begins", () => {
  // Widening the target so an instrument may consume 90% of the band and
  // still read CAPABLE broke only one test. The boundaries themselves were
  // never pinned.
  const band = 0.01;
  assert.equal(assessCapability(req(band), [inst("BORE_GAUGE", 0.001)]).verdict, "CAPABLE", "exactly 10% is inside the target");
  assert.equal(assessCapability(req(band), [inst("BORE_GAUGE", 0.0011)]).verdict, "MARGINAL", "11% is not");
});

test("the 25% limit is where MARGINAL ends and NOT_CAPABLE begins", () => {
  // Moving this to 99% left every test passing, so an instrument consuming
  // 98% of the tolerance band came back MARGINAL — a verdict that says "still
  // discriminating" about a gauge that cannot discriminate at all.
  const band = 0.01;
  assert.equal(assessCapability(req(band), [inst("BORE_GAUGE", 0.0025)]).verdict, "MARGINAL", "exactly 25% is still marginal");
  assert.equal(assessCapability(req(band), [inst("BORE_GAUGE", 0.0026)]).verdict, "NOT_CAPABLE", "26% is not");
  assert.equal(assessCapability(req(band), [inst("BORE_GAUGE", 0.0098)]).verdict, "NOT_CAPABLE", "and neither is 98%");
});

test("the verdict never improves as the instrument gets worse", () => {
  const band = 0.01;
  const rank = { CAPABLE: 0, MARGINAL: 1, NOT_CAPABLE: 2, NO_INSTRUMENT: 3, NOT_REQUIRED: 4 } as const;
  let previous = -1;
  for (const u of [0.0001, 0.0005, 0.001, 0.0015, 0.0025, 0.004, 0.009]) {
    const v = assessCapability(req(band), [inst("BORE_GAUGE", u)]).verdict;
    assert.ok(rank[v] >= previous, `±${u} reported ${v}, better than the instrument before it`);
    previous = rank[v];
  }
});

test("the consumed fraction is reported, so the verdict can be argued with", () => {
  const r = assessCapability(req(0.01), [inst("BORE_GAUGE", 0.002)]);
  assert.ok(r.consumedFraction !== null && Math.abs(r.consumedFraction - 0.2) < 1e-9, `got ${r.consumedFraction}`);
  assert.match(r.reason, /20%/);
});

test("a marginal result says how to keep the risk on the shop's side", () => {
  const r = assessCapability(req(0.01), [inst("BORE_GAUGE", 0.002)]);
  assert.equal(r.verdict, "MARGINAL");
  assert.ok(r.recommendations.some((x) => /guard-band/i.test(x)), `got [${r.recommendations.join(" | ")}]`);
});

/* ---------------- Calibration is evidence ---------------- */

test("an uncalibrated instrument is NOT_CAPABLE however good its uncertainty is", () => {
  // Downgrading this branch to MARGINAL broke nothing. An uncalibrated
  // instrument has no traceable uncertainty, so the number on its label is a
  // claim rather than evidence — and principle 2 says a gate is satisfied by
  // evidence, not by a value somebody wrote down.
  const r = assessCapability(req(0.02), [inst("BORE_GAUGE", 0.00005, { calibrated: false })]);
  assert.equal(r.verdict, "NOT_CAPABLE", "a half-tenth gauge with no certificate is still not evidence");
  assert.match(r.reason, /calibrat/i);
  assert.ok(r.recommendations.some((x) => /calibrate/i.test(x)), "and it says what would fix it");
});

test("a calibrated instrument is preferred over an uncalibrated better one", () => {
  const r = assessCapability(req(0.02), [
    inst("BORE_GAUGE", 0.00005, { id: "uncal", calibrated: false }),
    inst("BORE_GAUGE", 0.0005, { id: "cal", calibrated: true }),
  ]);
  assert.equal(r.verdict, "CAPABLE");
  assert.equal(r.bestInstrument?.id, "cal", "the certificate is what makes it usable");
});

test("calibration cannot be argued away any more than capability can", () => {
  const r = assessCapability(req(0.02), [inst("BORE_GAUGE", 0.00005, { calibrated: false })]);
  assert.equal(r.clearableByConfirmation, false);
});

/* ---------------- Refusal ---------------- */

test("no tolerance band means nothing to assess, not a pass", () => {
  const r = assessCapability(req(null), [inst("BORE_GAUGE", 0.0002)]);
  assert.equal(r.verdict, "NOT_REQUIRED");
  assert.equal(r.consumedFraction, null, "null, not zero — no band consumed nothing of nothing");
});

test("an empty instrument list is NO_INSTRUMENT rather than capable by default", () => {
  const r = assessCapability(req(0.01), []);
  assert.equal(r.verdict, "NO_INSTRUMENT");
  assert.equal(r.bestInstrument, null);
});

test("every result names the uncertainty an instrument would need", () => {
  for (const u of [0.0002, 0.002, 0.009]) {
    const r = assessCapability(req(0.01), [inst("BORE_GAUGE", u)]);
    if (r.verdict === "CAPABLE") continue;
    assert.ok(r.requiredUncertainty !== null && r.requiredUncertainty > 0, `±${u} names no target to buy against`);
  }
});
