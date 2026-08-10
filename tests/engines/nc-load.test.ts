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
