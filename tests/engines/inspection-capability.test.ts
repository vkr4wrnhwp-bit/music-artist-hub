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
  featureId: "f", featureLabel: "bore", geometry: "INTERNAL", nominal: 1.5,
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
