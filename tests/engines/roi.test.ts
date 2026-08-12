import { test } from "node:test";
import assert from "node:assert/strict";
import { computeRoi } from "@/lib/nc/roi";

test("ROI arithmetic is deterministic and labelled estimated", () => {
  const r = computeRoi({ currentCycleMinutes: 18.7, proposedCycleMinutes: 16.183, batchQuantity: 500, annualQuantity: 5000, machineRatePerHour: 125 });
  assert.equal(r.savedSecondsPerPart, 151.0);
  assert.equal(r.savedHoursPerBatch, 21.0);
  assert.equal(r.annualMachineHoursRecovered, 209.7);
  assert.equal(r.estimatedAnnualCapacityValue, 26219);
  assert.equal(r.estimated, true);
  assert.ok(r.assumptions.some((a) => a.includes("capacity, not revenue")));
});

test("ROI without a shop rate shows no dollar figure rather than assuming one", () => {
  const r = computeRoi({ currentCycleMinutes: 10, proposedCycleMinutes: 9, batchQuantity: 10, annualQuantity: 100, machineRatePerHour: null });
  assert.equal(r.estimatedAnnualCapacityValue, null);
  assert.ok(r.assumptions.some((a) => a.includes("No shop machine rate")));
});

test("ROI never reports negative savings", () => {
  const r = computeRoi({ currentCycleMinutes: 10, proposedCycleMinutes: 12, batchQuantity: 10, annualQuantity: 100, machineRatePerHour: 100 });
  assert.equal(r.savedSecondsPerPart, 0);
  assert.equal(r.annualMachineHoursRecovered, 0);
});
