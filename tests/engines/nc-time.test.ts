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

/* ---------------- The tap is never retimed ---------------- */

/**
 * A tap is synchronised to the spindle: its feed IS the thread lead. Every
 * finding analyzeNC raises about a feed move proposes speeding it up or
 * replacing it with a rapid, and following either on a tapping segment
 * snaps the tap in the hole.
 *
 * The proposal side of this is pinned in nc-load. The analysis side — the
 * `!s.tapping` guard that stops the finding being raised at all — had no
 * test, and removing it broke nothing.
 */

const tapSeg = (x0: number, y0: number, x1: number, y1: number, feed: number, line = 1): NCSegment => ({
  line, kind: "CUT", x0, y0, z0: 1, x1, y1, z1: 1,
  feed, toolNumber: 5, spindleRPM: 500, comped: false, tapping: true,
});

const parsedOf = (segments: NCSegment[]) =>
  ({
    segments, toolChanges: [], workOffsetsSeen: ["G54"], refusals: [], warnings: [],
    lineCount: segments.length, units: "IN",
  }) as unknown as Parameters<typeof analyzeNC>[0];

const CTX = { stock: { x: 6, y: 4, z: 1 }, toolDiameters: { 5: 0.25 }, rapidRate: 600 };

test("a tapping move above the stock is never called a slow linking move", () => {
  // The same geometry as an ordinary feed move that WOULD be flagged: a long
  // feed entirely above Z0, where a rapid does the same job in less time.
  const ordinary = analyzeNC(parsedOf([seg(0, 0, 6, 0, 10, 1)].map((s) => ({ ...s, z0: 1, z1: 1 }))), CTX);
  assert.ok(
    ordinary.findings.some((f) => f.kind === "SLOW_LINKING_MOVE"),
    "precondition: this geometry is flagged when it is not tapping",
  );

  const tapping = analyzeNC(parsedOf([tapSeg(0, 0, 6, 0, 10, 1)]), CTX);
  assert.deepEqual(
    tapping.findings.filter((f) => f.kind === "SLOW_LINKING_MOVE"),
    [],
    "a tapping segment must never be proposed as a rapid",
  );
});

test("no finding at all is raised against a tapping segment", () => {
  // Not just the linking-move finding: nothing that would change its feed or
  // its motion type.
  const tapping = analyzeNC(parsedOf([tapSeg(0, 0, 6, 0, 10, 1), tapSeg(6, 0, 6, 4, 10, 2)]), CTX);
  assert.deepEqual(tapping.findings, [], `got ${JSON.stringify(tapping.findings)}`);
});

test("a tapping segment still counts toward the cycle time", () => {
  // Untouchable is not the same as invisible — the tap takes as long as it
  // takes, and the estimate has to include it.
  const withTap = analyzeNC(parsedOf([tapSeg(0, 0, 6, 0, 10, 1)]), CTX);
  assert.ok(withTap.totalMinutes > 0, "the tap contributes time");
});

test("an ordinary feed move beside a tapping one is still analysed", () => {
  // The guard is per segment, not per program: one tap must not silence the
  // analysis of everything around it.
  const mixed = analyzeNC(
    parsedOf([tapSeg(0, 0, 1, 0, 10, 1), { ...seg(1, 0, 6, 0, 10, 2), z0: 1, z1: 1 }]),
    CTX,
  );
  assert.ok(mixed.findings.some((f) => f.kind === "SLOW_LINKING_MOVE"), "the non-tapping move is still examined");
  assert.ok(mixed.findings.every((f) => f.line !== 1), "and the tapping one is not");
});

test("rapid time counts toward the cycle, and is reported separately", () => {
  // Zeroing rapid time understates the cycle and inflates every saving
  // measured against it. A long traverse is not free.
  const withRapid = analyzeNC(parsedOf([{ ...seg(0, 0, 20, 0, null, 1), z0: 1, z1: 1 }]), CTX);
  assert.ok(withRapid.totalMinutes > 0, "a rapid takes time");
  assert.ok(withRapid.rapidMinutes > 0, "and is attributed to rapid rather than to cutting");
});
