import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ACROSS_SHARE_THRESHOLD, classifySegment, summariseLoadDirection } from "@/lib/nc/load-direction";
import { analyzeNC } from "@/lib/nc/analyze";
import { parseNC } from "@/lib/nc/parse";

/**
 * This check was declared unbuildable: "the check needs a cutting-force vector
 * and a jaw axis, and CANVAS records neither."
 *
 * Half of that stopped being true when Setup.jawAxis was added for the
 * fixture-collision work. The other half turns out not to be needed: the
 * question a machinist asks is not how many pounds — holding-margin.ts answers
 * that and says DEVELOPMENT ANALYSIS while it does — but WHICH WAY, and the
 * program states that exactly in its own coordinates.
 */

const seg = (x0: number, y0: number, x1: number, y1: number, feed: number | null = 10, line = 1) =>
  ({ x0, y0, x1, y1, z0: -0.1, z1: -0.1, feed, line }) as never;

test("a cut along the jaw axis drives the part into a jaw", () => {
  // The direction a vise is for: the jaw body reacts it.
  const c = classifySegment(seg(0, 0, 2, 0), "X")!;
  assert.equal(c.direction, "ALONG_JAWS");
  assert.equal(c.acrossFraction, 0);
});

test("a cut across the jaw axis slides the part along the jaw faces", () => {
  // Nothing resists that but friction. This is how a part walks out of a vise
  // while every clamping number looks fine.
  const c = classifySegment(seg(0, 0, 0, 2), "X")!;
  assert.equal(c.direction, "ACROSS_JAWS");
  assert.equal(c.acrossFraction, 1);
});

test("the axis decides which is which", () => {
  assert.equal(classifySegment(seg(0, 0, 2, 0), "Y")!.direction, "ACROSS_JAWS");
  assert.equal(classifySegment(seg(0, 0, 0, 2), "Y")!.direction, "ALONG_JAWS");
});

test("a diagonal is weighted, not rounded to one or the other", () => {
  // Rounding a 45° cut overstates whichever way it rounded.
  const c = classifySegment(seg(0, 0, 1, 1), "X")!;
  assert.ok(Math.abs(c.acrossFraction - Math.SQRT1_2) < 1e-9, `45° gave ${c.acrossFraction}`);
});

test("a rapid pushes nothing", () => {
  assert.equal(classifySegment(seg(0, 0, 0, 5, null), "X"), null);
});

test("a plunge has no XY direction and is not counted", () => {
  const c = classifySegment(seg(1, 1, 1, 1), "X")!;
  assert.equal(c.direction, "VERTICAL");
  assert.equal(c.xyLength, 0);
  const s = summariseLoadDirection([seg(1, 1, 1, 1, 10, 5)], "X");
  assert.equal(s.acrossShare, null, "a program of nothing but plunges produced a share");
});

test("the share is by distance, not by segment count", () => {
  // A long slot across the jaws matters more than a short one; counting
  // segments says they matter the same.
  const s = summariseLoadDirection(
    [seg(0, 0, 0.1, 0, 10, 1), seg(0, 0, 0, 10, 10, 2)],
    "X",
  );
  assert.ok(s.acrossShare! > 0.9, `two segments, one 100x longer, gave ${s.acrossShare}`);
});

test("the worst segment is the one with the most across-distance", () => {
  const s = summariseLoadDirection(
    [seg(0, 0, 0, 1, 10, 11), seg(0, 0, 0, 8, 10, 22), seg(0, 0, 3, 0, 10, 33)],
    "X",
  );
  assert.equal(s.worst!.line, 22);
});

test("an all-along program produces no across distance", () => {
  const s = summariseLoadDirection([seg(0, 0, 5, 0, 10, 1), seg(5, 0, 9, 0, 10, 2)], "X");
  assert.equal(s.acrossLength, 0);
  assert.equal(s.acrossShare, 0);
});

/* ---- the finding ---- */

const program = ["G20 G90 G54", "T1 M6", "S5000 M3", "G0 X0 Y0 Z0.1", "G1 Z-0.2 F10", "G1 Y3. F20", "G1 Y6. F20", "G0 Z1.", "M30"].join("\n");
const acrossCtx = {
  stock: { x: 8, y: 8, z: 1 },
  toolDiameters: { 1: 0.5 },
  rapidRate: 600,
  axisAccel: null,
};

const run = (workholding: { jawAxis: string | null; hasPositiveStop: boolean } | undefined) =>
  analyzeNC(parseNC(program), {
    ...acrossCtx,
    workholding: workholding ? { ...workholding, deviceDescription: null } : undefined,
  });

test("a program cutting across the jaws with no stop is raised", () => {
  const r = run({ jawAxis: "X", hasPositiveStop: false });
  const f = r.findings.find((x) => x.kind === "WORKHOLDING_LOAD_DIRECTION_REVIEW");
  assert.ok(f, "cutting entirely across the jaws was not raised");
  assert.equal(f!.verdict, "REVIEW");
  assert.equal(f!.seconds, 0, "a holding decision was priced");
  assert.match(f!.detail, /across the jaw faces/);
  assert.match(f!.detail, /no positive stop/);
});

test("a positive stop reacts it, and the report says the check ran", () => {
  // Silence would leave the operator unsure whether it ran at all.
  const r = run({ jawAxis: "X", hasPositiveStop: true });
  assert.equal(r.findings.filter((x) => x.kind === "WORKHOLDING_LOAD_DIRECTION_REVIEW").length, 0);
  const skipped = r.checksSkipped.find((c) => /Cut direction against the jaws/.test(c.check));
  assert.ok(skipped, "the check went silent");
  assert.match(skipped!.reason, /positive stop/);
});

test("the same program along the jaws is not raised", () => {
  const r = run({ jawAxis: "Y", hasPositiveStop: false });
  assert.equal(r.findings.filter((x) => x.kind === "WORKHOLDING_LOAD_DIRECTION_REVIEW").length, 0);
});

test("no recorded jaw axis reports that the check did not run", () => {
  for (const wh of [undefined, { jawAxis: null, hasPositiveStop: false }, { jawAxis: "diagonal", hasPositiveStop: false }]) {
    const r = run(wh);
    assert.equal(r.findings.filter((x) => x.kind === "WORKHOLDING_LOAD_DIRECTION_REVIEW").length, 0);
    const skipped = r.checksSkipped.find((c) => /Cut direction against the jaws/.test(c.check));
    assert.ok(skipped, `no jaw axis (${JSON.stringify(wh)}) went silent instead of reporting`);
    assert.match(skipped!.reason, /does not record which axis the jaws close on/);
  }
});

test("the finding states it is a direction and not a force solve", () => {
  const f = run({ jawAxis: "X", hasPositiveStop: false }).findings.find(
    (x) => x.kind === "WORKHOLDING_LOAD_DIRECTION_REVIEW",
  )!;
  const text = f.assumptions.join(" ");
  assert.match(text, /taken as the feed direction/);
  assert.match(text, /climb and conventional/);
  assert.match(text, /not whether the grip holds/);
});

test("the stale claim that this cannot be checked is gone", () => {
  // It sat in checksSkipped as a fixed block at the bottom of the file and
  // would have kept saying the check was impossible after it was built.
  const src = readFileSync("src/lib/nc/analyze.ts", "utf8");
  assert.ok(
    !/returns a magnitude, not a vector, and a setup does not record/.test(src),
    "the analysis still claims the load-direction check cannot be made",
  );
});

test("the threshold is a share of cutting, not a force", () => {
  assert.ok(ACROSS_SHARE_THRESHOLD > 0 && ACROSS_SHARE_THRESHOLD < 1);
  const src = readFileSync("src/lib/nc/load-direction.ts", "utf8");
  assert.match(src, /Not a safety threshold and not derived from a force/);
});

test("the engine consults no model", () => {
  const src = readFileSync("src/lib/nc/load-direction.ts", "utf8");
  assert.ok(!/from "@\/lib\/ai\//.test(src), "the load-direction engine reaches the AI layer");
});
