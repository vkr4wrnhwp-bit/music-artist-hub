import { test } from "node:test";
import assert from "node:assert/strict";
import { timePath } from "@/lib/nc/time";
import { analyzeNC } from "@/lib/nc/analyze";
import type { NCSegment } from "@/lib/nc/parse";

/**
 * Trapezoidal path timing. The closed-form answers below are the model's own
 * math worked by hand — the tests pin that the implementation is the model it
 * claims to be, junction rules included.
 */

const seg = (x0: number, y0: number, x1: number, y1: number, feed: number | null, line = 1): NCSegment => ({
  line, kind: feed === null ? "RAPID" : "CUT", x0, y0, z0: 0, x1, y1, z1: 0,
  feed, toolNumber: 1, spindleRPM: 1000, comped: false, tapping: false,
});

// 10 in at F60 (1 in/s) with a = 4 in/s²: reaches speed, rest to rest:
// t = d/v + v/a = 10 + 0.25 = 10.25 s.
test("long segment: cruise time plus one accel and one decel", () => {
  const r = timePath([seg(0, 0, 10, 0, 60)], 4, 600);
  assert.ok(Math.abs(r.totalSeconds - 10.25) < 1e-9);
  assert.equal(r.accelLimitedSegments, 0);
  assert.equal(r.developmentAnalysis, true);
});

// 0.1 in at F600 (10 in/s) with a = 4: cannot reach speed. Triangular:
// t = 2·√(d/a) = 2·√0.025 ≈ 0.3162 s — where flat timing says 0.01 s.
test("short segment goes triangular and is counted as acceleration-limited", () => {
  const r = timePath([seg(0, 0, 0.1, 0, 600)], 4, 600);
  assert.ok(Math.abs(r.totalSeconds - 2 * Math.sqrt(0.1 / 4)) < 1e-9);
  assert.equal(r.accelLimitedSegments, 1);
});

test("colinear segments blend at speed; a square corner stops", () => {
  const a = 4;
  // Two colinear 5" moves at F60 time exactly like one 10" move.
  const straight = timePath([seg(0, 0, 5, 0, 60), seg(5, 0, 10, 0, 60)], a, 600);
  assert.ok(Math.abs(straight.totalSeconds - 10.25) < 1e-9);
  // The same distance around a square corner pays two extra half-ramps:
  // each 5" leg is rest-to-rest, t = 2 × (5/1 + 1/4) = 10.5 s.
  const corner = timePath([seg(0, 0, 5, 0, 60), seg(5, 0, 5, 5, 60)], a, 600);
  assert.ok(Math.abs(corner.totalSeconds - 10.5) < 1e-9);
  assert.ok(corner.totalSeconds > straight.totalSeconds);
});

test("a dwell breaks velocity continuity and times at face value", () => {
  const dwell: NCSegment = { ...seg(5, 0, 5, 0, 60), kind: "DWELL", dwellSeconds: 2 };
  const r = timePath([seg(0, 0, 5, 0, 60), dwell, seg(5, 0, 10, 0, 60)], 4, 600);
  // Both motions rest-to-rest (5/1 + 0.25 each) plus the dwell.
  assert.ok(Math.abs(r.totalSeconds - (5.25 + 2 + 5.25)) < 1e-9);
});

test("analyzeNC uses the model when accel is recorded and says so; never guesses when it is not", () => {
  const parsed = {
    segments: [seg(0, 0, 0.1, 0, 600, 1), seg(0.1, 0, 0.2, 0, 600, 2)],
    toolChanges: [], workOffsetsSeen: ["G54"], refusals: [], warnings: [], lineCount: 2, units: "IN",
  } as unknown as Parameters<typeof analyzeNC>[0];
  const ctx = { stock: null, toolDiameters: {}, rapidRate: 600 };

  const flat = analyzeNC(parsed, ctx);
  const modeled = analyzeNC(parsed, { ...ctx, axisAccel: 4 });
  assert.ok(modeled.totalMinutes > flat.totalMinutes, "short segments must time longer under acceleration");
  assert.ok(modeled.assumptions.some((a) => /Trapezoidal acceleration model at 4/.test(a)));
  assert.ok(modeled.assumptions.some((a) => /DEVELOPMENT ANALYSIS/.test(a)));
  assert.ok(flat.assumptions.some((a) => /No axis acceleration recorded/.test(a)));
});
