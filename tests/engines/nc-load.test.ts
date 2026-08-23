import { test } from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "@/lib/nc/parse";
import { analyzeLoad, type LoadContext } from "@/lib/nc/load";

/**
 * Phase 4D honesty rules: banding from real chipload arithmetic, proposals
 * only where LIGHT and safe, taps and comped regions never touched, preset
 * caps enforced with LIGHTS_OUT the most conservative, and missing context
 * producing gaps rather than guesses.
 */

const tool = { diameter: 0.5, flutes: 3, chiploadMin: 0.002, chiploadMax: 0.005 };
const ctx = (over: Partial<LoadContext> = {}): LoadContext => ({
  stock: { x: 6, y: 4, z: 0.75 },
  tools: { 0: tool, 2: tool },
  specificEnergy: 0.3,
  machineMaxFeed: 500,
  preset: "BALANCED",
  ...over,
});

// A long light cut: S5000 × 3 flutes × F10 → chipload 0.00067 — far below 0.002.
const LIGHT = "G20 G90\nS5000 M3\nG0 X-2.5 Y0 Z0.2\nG1 Z-0.1 F5\nG1 X2.5 F10";
// The same cut at F45 → chipload 0.003 — inside the window.
const TARGET = "G20 G90\nS5000 M3\nG0 X-2.5 Y0 Z0.2\nG1 Z-0.1 F5\nG1 X2.5 F45";

test("a rubbing cut bands LIGHT and draws a feed proposal with real savings", () => {
  const a = analyzeLoad(parseNC(LIGHT), ctx());
  assert.ok(a.segments.some((s) => s.band === "LIGHT"));
  // The plunge (F5) and the traverse (F10) are separate feed runs — both are
  // rubbing, both get proposals. Assert on the traverse.
  const p = a.proposals.find((x) => x.originalFeed === 10)!;
  assert.ok(p, JSON.stringify(a.proposals));
  assert.ok(p.proposedFeed > p.originalFeed);
  assert.equal(p.geometryChanges, false);
  assert.ok(p.estimatedSecondsSaved > 5, `saved ${p.estimatedSecondsSaved}`);
  assert.ok(p.proposedFeed <= 10 * 1.35 + 1e-9, "BALANCED cap exceeded");
});

test("a cut inside the chipload window gets no proposal", () => {
  const a = analyzeLoad(parseNC(TARGET), ctx());
  assert.ok(a.segments.some((s) => s.band === "TARGET"));
  // The F45 traverse is in the window and must not be proposed; the F5
  // plunge is still light and legitimately may be.
  assert.ok(!a.proposals.some((p) => p.originalFeed === 45));
});

test("LIGHTS_OUT caps tighter than CONSERVATIVE, which caps tighter than AGGRESSIVE", () => {
  const lo = analyzeLoad(parseNC(LIGHT), ctx({ preset: "LIGHTS_OUT" })).proposals[0];
  const co = analyzeLoad(parseNC(LIGHT), ctx({ preset: "CONSERVATIVE" })).proposals[0];
  const ag = analyzeLoad(parseNC(LIGHT), ctx({ preset: "AGGRESSIVE" })).proposals[0];
  assert.ok(lo.proposedFeed <= co.proposedFeed);
  assert.ok(co.proposedFeed <= ag.proposedFeed);
  assert.equal(ag.risk, "REVIEW");
});

test("tapping is never proposed, whatever its chipload says", () => {
  const a = analyzeLoad(parseNC("G20 G90\nS500 M3\nG0 X0 Y0 Z1\nG84 Z-0.5 R0.1 F25\nG80"), ctx());
  assert.equal(a.proposals.length, 0);
});

test("missing tool or material produce gaps, never guessed bands or power", () => {
  const a = analyzeLoad(parseNC("G20 G90\nT9 M6\nS5000 M3\nG0 X0 Y0 Z0.2\nG1 Z-0.1 F5\nG1 X2 F10"), ctx({ tools: {}, specificEnergy: null }));
  assert.ok(a.gaps.some((g) => /T9/.test(g) || /T0/.test(g)));
  assert.ok(a.gaps.some((g) => /specific energy/.test(g)));
  assert.equal(a.proposals.length, 0);
  assert.ok(a.segments.every((s) => s.spindlePowerHp === null));
  assert.equal(a.developmentAnalysis, true);
});

test("air segments band AIR from the replay, not from feed words", () => {
  // Second identical pass removes nothing.
  const a = analyzeLoad(parseNC(LIGHT + "\nG0 Z0.2\nG0 X-2.5\nG1 Z-0.1 F5\nG1 X2.5 F10"), ctx());
  const airBands = a.segments.filter((s) => s.band === "AIR");
  assert.ok(airBands.length >= 2, JSON.stringify(a.segments));
});

/* ------------------------------------------------------------------ */
/* Phase 5: finish protection + corner-spike control                   */
/* ------------------------------------------------------------------ */

test("a protected region blocks proposals inside it and reports FINISH PASS PROTECTED", () => {
  // The LIGHT program cuts along Y0 from X-2.5 to X2.5 at Z-0.1. Protect a
  // bore at the middle of that path.
  const a = analyzeLoad(parseNC(LIGHT), ctx({
    protectedRegions: [{ label: "Bearing Bore A", reason: "Tolerance band 0.0010\"", centerX: 0, centerY: 0, radius: 3.0, zTop: 0, zBottom: -0.5 }],
  }));
  assert.equal(a.proposals.length, 0, "no proposal may touch a protected cut");
  assert.equal(a.protectedHits.length, 1);
  assert.equal(a.protectedHits[0].label, "Bearing Bore A");
  assert.ok(a.protectedHits[0].segments > 0);
  // Without the region the same program DOES propose — protection is the difference.
  assert.ok(analyzeLoad(parseNC(LIGHT), ctx()).proposals.length > 0);
});

test("protection outside the cut's Z span does not fire — regions are spatial, not global", () => {
  const a = analyzeLoad(parseNC(LIGHT), ctx({
    protectedRegions: [{ label: "Deep bore", reason: "critical", centerX: 0, centerY: 0, radius: 3.0, zTop: -0.5, zBottom: -0.9 }],
  }));
  assert.equal(a.protectedHits.length, 0);
  assert.ok(a.proposals.length > 0);
});

// An engagement spike: a full-width plunge into fresh stock mid-run. The run
// cuts thin passes at the stock edge (low removal), then drives straight
// through center (high removal), then back out. Same tool, same feed.
// Edge skims barely engage the 0.5" tool (center outside the stock edge);
// the center pass is a full-width slot through virgin stock — the spike.
// Rapids between passes are transparent to run grouping.
const SPIKE = [
  "G20 G90", "S5000 M3",
  "G0 X-3.5 Y-2.05 Z0.2",
  "G1 Z-0.35 F60",
  "G1 X3.5 F60",     // skim: ~0.2 engagement
  "G0 Z0.2", "G0 X-3.5 Y2.05", "G1 Z-0.35 F60",
  "G1 X3.5 F60",     // skim: ~0.2 engagement
  "G0 Z0.2", "G0 X-3.5 Y0.0", "G1 Z-0.35 F60",
  "G1 X3.5 F60",     // full-width slot — the spike
].join("\n");

test("an engagement spike inside a same-feed run draws a REDUCE proposal, floored at minimum chipload", () => {
  const a = analyzeLoad(parseNC(SPIKE), ctx());
  const reduce = a.proposals.find((p) => p.kind === "REDUCE");
  assert.ok(reduce, "expected a REDUCE proposal for the spike");
  assert.ok(reduce!.proposedFeed < reduce!.originalFeed * 0.88, "hysteresis: at least a 12% cut");
  // Floor: proposed feed never thins the chip below the insert minimum.
  const floorFeed = tool.chiploadMin * 5000 * tool.flutes;
  assert.ok(reduce!.proposedFeed >= Math.floor(floorFeed), "never below minimum-chipload feed");
  assert.equal(reduce!.risk, "REVIEW");
  assert.equal(reduce!.estimatedSecondsSaved, 0, "control is not sold as savings");
  assert.ok(reduce!.assumptions.some((x) => x.includes("DEVELOPMENT")));
});

test("REDUCE proposals never fire without stock replay data — no spike is guessed", () => {
  const a = analyzeLoad(parseNC(SPIKE), ctx({ stock: null }));
  assert.ok(!a.proposals.some((p) => p.kind === "REDUCE"));
});

test("savings total counts RAISE only — reductions are load control, not time", () => {
  const a = analyzeLoad(parseNC(SPIKE), ctx());
  const raiseSum = a.proposals.filter((p) => p.kind === "RAISE").reduce((t, p) => t + p.estimatedSecondsSaved, 0);
  assert.equal(a.totalProposedSecondsSaved, Number(raiseSum.toFixed(1)));
});

test("a pass crossing straight THROUGH a protected bore is protected — endpoints alone are not the test", () => {
  // Cut from X-2.5 to X2.5 at Y0.5: both endpoints are far from the bore at
  // (0,0) r0.94, but the segment passes within 0.5" of center.
  const a = analyzeLoad(parseNC(LIGHT), ctx({
    protectedRegions: [{ label: "40 mm bearing bore", reason: "Tolerance band 0.0005\"", centerX: 0, centerY: 0, radius: 0.94, zTop: 0, zBottom: -0.625 }],
  }));
  assert.ok(a.protectedHits.some((h) => h.label === "40 mm bearing bore"));
});

test("a cut passing THROUGH a protected region's depth is protected, not just one ending inside it", () => {
  // The XY match is a segment-to-centre distance, with a comment saying
  // endpoints alone would let a pass crossing a bore escape. Z was matched on
  // the endpoint only, so the identical argument failed there: a plunge that
  // stopped inside the region was protected, and one that carried on past the
  // bottom of it drew a proposal. A drill continuing through a protected bore
  // escaped by finishing lower than the region it travelled through.
  const region = { label: "Bearing Bore A", reason: "critical", centerX: 0, centerY: 0, radius: 1.0, zTop: 0, zBottom: -0.3 };
  const through = "G20 G90\nS5000 M3\nG0 X0 Y0 Z0.2\nG1 Z-0.5 F10";
  const a = analyzeLoad(parseNC(through), ctx({ protectedRegions: [region] }));
  assert.equal(a.protectedHits.length, 1, "the cut travelled through the protected depth");
  assert.equal(a.proposals.length, 0, "and nothing may be proposed for it");
});

test("a cut entirely below a region is still not protected", () => {
  // The span test must not over-reach: a pass under the feature has not
  // touched it.
  const region = { label: "Shallow bore", reason: "critical", centerX: 0, centerY: 0, radius: 1.0, zTop: 0, zBottom: -0.1 };
  const below = "G20 G90\nS5000 M3\nG0 X-2.5 Y0 Z0.2\nG1 Z-0.5 F5\nG1 X2.5 F10";
  const a = analyzeLoad(parseNC(below), ctx({ protectedRegions: [region] }));
  const lateral = a.protectedHits.reduce((n, h) => n + h.segments, 0);
  // The plunge crosses the region on its way down and is rightly caught; the
  // lateral pass at Z-0.5 is wholly below it and is not.
  assert.ok(lateral <= 1, `a pass under the feature was protected: ${lateral} segments`);
});

test("no machine bound means no raise is proposed — a raise is a number the operator runs", () => {
  // The feed ceiling is what stops a proposal exceeding what the machine can
  // make. Against a fabricated ceiling the optimizer could hand the operator
  // a feed a slower machine cannot reach, so with no machine record the
  // raise is withheld rather than computed from an assumption.
  const withMachine = analyzeLoad(parseNC(LIGHT), ctx());
  assert.ok(withMachine.proposals.some((p) => p.kind === "RAISE"));
  const without = analyzeLoad(parseNC(LIGHT), ctx({ machineMaxFeed: null }));
  assert.equal(without.proposals.filter((p) => p.kind === "RAISE").length, 0);
  // The banding still works: the analysis is not withheld, only the proposal.
  assert.deepEqual(
    without.segments.map((s) => s.band),
    withMachine.segments.map((s) => s.band),
  );
});
