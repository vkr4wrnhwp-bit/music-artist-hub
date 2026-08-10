import { test } from "node:test";
import assert from "node:assert/strict";
import { buildFair, assessConformance } from "@/lib/engines/fair";
import { emptyPartIntent } from "@/lib/domain/part-intent";
import type { Feature } from "@/lib/domain/features";

/**
 * The FAIR engine decides conformance only where the arithmetic decides it.
 * These tests pin every refusal path: the 4:1 rule, the near-limit guard
 * band, the reverse-engineering exclusion, and the no-single-nominal case.
 */

const bore = {
  id: "f1", kind: "BORE", label: "Bore", functionalRole: "BEARING_SEAT", critical: true,
  centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.7, through: true, top: 0,
  tolerance: { plus: 0.0005, minus: 0 }, inspectionMethod: "Bore gauge",
} as unknown as Feature;

const pocket = {
  id: "f2", kind: "RECT_POCKET", label: "Pocket", functionalRole: "NONE", critical: false,
  centerX: 0, centerY: 0, width: 3, length: 2, depth: 0.125, cornerRadius: 0.25, top: 0,
  tolerance: { plus: 0.01, minus: 0.01 }, inspectionMethod: "Calipers",
} as unknown as Feature;

const meas = (featureId: string, value: number, uncertainty: number, mode = "INSPECTION") => ({
  featureId, sessionMode: mode, value, uncertainty, instrument: "gauge",
  measuredAt: "2026-08-10T00:00:00Z", repeatCount: 3,
});

const base = {
  organizationName: "Shop", partNumber: "P-1", partName: "Part", revision: "A",
  intent: emptyPartIntent("Part"), drawings: [], generatedAtIso: "2026-08-10T00:00:00Z", preparedBy: "QA",
};

test("mid-band result with a capable instrument conforms", () => {
  const r = buildFair({ ...base, features: [bore], inspectionMeasurements: [meas("f1", 1.575, 0.00005)] });
  assert.equal(r.form3[0].conformance.verdict, "CONFORMS");
  assert.equal(r.summary.conforming, 1);
});

test("over-limit result nonconforms, with an NC record field printed NOT ON FILE", () => {
  const r = buildFair({ ...base, features: [bore], inspectionMeasurements: [meas("f1", 1.576, 0.00005)] });
  const c = r.form3[0].conformance;
  assert.equal(c.verdict, "NONCONFORMS");
  if (c.verdict === "NONCONFORMS") assert.equal(c.nonconformanceDoc.state, "NOT_ON_FILE");
});

test("an instrument failing the 4:1 rule cannot carry a verdict", () => {
  // Band 0.0005", u ±0.0002": 2u exceeds a quarter of the band.
  const v = assessConformance(bore, { value: 1.575, uncertainty: 0.0002 });
  assert.equal(v.verdict, "CANNOT_DETERMINE");
  if (v.verdict === "CANNOT_DETERMINE") assert.match(v.reason, /4:1/);
});

test("inside the limits by less than the uncertainty is not a pass", () => {
  const v = assessConformance(bore, { value: 1.57529, uncertainty: 0.00003 });
  assert.equal(v.verdict, "CANNOT_DETERMINE");
});

test("a feature with no single nominal dimension is assessed manually", () => {
  const v = assessConformance(pocket, { value: 3.001, uncertainty: 0.0005 });
  assert.equal(v.verdict, "CANNOT_DETERMINE");
});

test("reverse-engineering readings never become first-article results", () => {
  const r = buildFair({
    ...base, features: [bore],
    inspectionMeasurements: [meas("f1", 1.575, 0.00005, "REVERSE_ENGINEER")],
  });
  assert.equal(r.form3[0].result.state, "NOT_MEASURED");
});

test("fields the shop has not recorded print NOT ON FILE, never blank", () => {
  const r = buildFair({ ...base, partNumber: null, features: [bore], inspectionMeasurements: [] });
  assert.equal(r.form1.partNumber.state, "NOT_ON_FILE");
  assert.equal(r.form1.serialNumber.state, "NOT_ON_FILE");
  assert.ok(r.summary.fieldsNotOnFile > 0);
});
