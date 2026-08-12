import { test } from "node:test";
import assert from "node:assert/strict";
import { summarizeCalibration, MIN_CALIBRATION_SAMPLES } from "@/lib/engines/calibration";

test("one sample is an anecdote, not a calibration", () => {
  const s = summarizeCalibration([{ estimatedMinutes: 10, actualMinutes: 12 }]);
  assert.equal(s.status, "INSUFFICIENT_DATA");
  assert.equal(s.medianFactor, null);
  assert.ok(s.statement.includes("anecdote"));
});

test("calibration is claimed only at the sample threshold, from the MEDIAN ratio", () => {
  // Five clean cycles ~4% slow, one interrupted outlier at 3x — the median ignores it.
  const samples = [
    { estimatedMinutes: 10, actualMinutes: 10.4 },
    { estimatedMinutes: 20, actualMinutes: 20.8 },
    { estimatedMinutes: 15, actualMinutes: 15.6 },
    { estimatedMinutes: 12, actualMinutes: 12.5 },
    { estimatedMinutes: 8, actualMinutes: 8.3 },
    { estimatedMinutes: 10, actualMinutes: 30 }, // door open, lunch — an outlier
  ];
  const s = summarizeCalibration(samples);
  assert.equal(s.status, "CALIBRATED");
  assert.ok(s.samples >= MIN_CALIBRATION_SAMPLES);
  assert.ok(Math.abs(s.medianFactor! - 1.04) < 0.01, `median ~1.04, got ${s.medianFactor}`);
  assert.ok(s.statement.includes("not yet applied"));
});

test("invalid samples are excluded, never guessed around", () => {
  const s = summarizeCalibration([
    { estimatedMinutes: 0, actualMinutes: 5 },
    { estimatedMinutes: 10, actualMinutes: 0 },
  ]);
  assert.equal(s.samples, 0);
  assert.equal(s.status, "INSUFFICIENT_DATA");
});
