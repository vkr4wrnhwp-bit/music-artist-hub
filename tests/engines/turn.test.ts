import { test } from "node:test";
import assert from "node:assert/strict";
import { validateProfile, overallLength, maxDiameter, type RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import {
  effectiveRpm,
  odRoughToolpath,
  odFinishToolpath,
  threadToolpath,
  partOffToolpath,
  grooveToolpath,
  type TurnOperation,
} from "@/lib/manufacturing/turn/operations";
import { assessChuckGrip, assessStickout, assessBoringBar, assessPartOff } from "@/lib/manufacturing/turn/analysis";
import { evaluateTurnReadiness } from "@/lib/manufacturing/turn/readiness";
import { emitLatheProgram } from "@/lib/manufacturing/turn/post";

/**
 * Turning engines: the rules that make X/Z motion safe to emit. CSS clamps,
 * refusals stay refusals, thread feed equals pitch, analyses never invent a
 * clamp force, worst-gate stays worst-case, and the post refuses an
 * unclamped G96.
 */

const profile: RotationalProfile = {
  units: "IN",
  zZeroReference: "front face",
  stockDiameter: 2.0,
  stockLength: 6.0,
  barStock: true,
  segments: [
    { id: "a", kind: "CYLINDER", label: "Journal", zStart: 0, zEnd: 2, diameterStart: 1.5744, diameterEnd: 1.5744, internal: false, functionalRole: "BEARING_JOURNAL", critical: true, source: "MEASURED", confirmedByUser: false },
  ],
};

const op = (over: Partial<TurnOperation>): TurnOperation => ({
  operationNumber: 10,
  type: "OD_ROUGH",
  label: "test",
  toolStation: "0101",
  targetSegmentId: "a",
  startZ: 0,
  endZ: 2,
  startDiameter: 2.0,
  endDiameter: 1.6,
  params: { feedPerRev: 0.01, surfaceSpeed: 600, rpm: 3000, cssEnabled: true, doc: 0.08, finishAllowance: 0.01, springPasses: 0, coolant: "FLOOD" },
  ...over,
});

/* ---- geometry ---- */

test("profile validation refuses stock that cannot make the part", () => {
  const bad: RotationalProfile = { ...profile, stockDiameter: 1.5 };
  assert.ok(validateProfile(bad).some((p) => /cannot make this part/.test(p)));
  assert.equal(validateProfile(profile).length, 0);
  // A shoulder is a zero-length diameter transition — legitimate geometry.
  const withShoulder: RotationalProfile = {
    ...profile,
    segments: [...profile.segments, { id: "sh", kind: "SHOULDER", label: "Shoulder", zStart: 2, zEnd: 2, diameterStart: 1.5744, diameterEnd: 1.85, internal: false, functionalRole: "LOCATING_SHOULDER", critical: false, source: "MEASURED", confirmedByUser: false }],
  };
  assert.equal(validateProfile(withShoulder).length, 0);
  assert.equal(overallLength(profile), 2);
  assert.equal(maxDiameter(profile), 1.5744);
});

/* ---- CSS ---- */

test("CSS rpm derives from surface speed at diameter and never exceeds the clamp", () => {
  const p = { feedPerRev: 0.01, surfaceSpeed: 600, rpm: 3000, cssEnabled: true, doc: 0.1, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" as const };
  // 600 SFM at Ø2": rpm = 600×12/(π×2) ≈ 1146 — below the clamp.
  assert.ok(Math.abs(effectiveRpm(p, 2) - (600 * 12) / (Math.PI * 2)) < 0.5);
  // At Ø0.5" CSS wants ~4584 RPM; the 3000 clamp is a ceiling.
  assert.equal(effectiveRpm(p, 0.5), 3000);
  // CSS off: fixed RPM regardless of diameter.
  assert.equal(effectiveRpm({ ...p, cssEnabled: false }, 0.25), 3000);
});

/* ---- toolpaths ---- */

test("OD roughing covers the radial stock in bounded passes and leaves the finish allowance", () => {
  const r = odRoughToolpath(op({}), profile);
  assert.ok(r.ok);
  if (!r.ok) return;
  // (2.0 − 1.62)/2 = 0.19 radial at 0.08 DOC → 3 passes.
  assert.equal(r.toolpath.passes, 3);
  const cutXs = r.toolpath.moves.filter((m) => m.kind === "CUT").map((m) => m.x);
  assert.ok(Math.min(...cutXs) >= 1.62 - 1e-9, "cut below target + allowance");
  assert.ok(r.toolpath.estimatedMinutes > 0);
  assert.ok(r.toolpath.assumptions.some((a) => /ESTIMATED/.test(a)));
});

test("threading feed equals pitch and passes shrink by constant-area infeed", () => {
  const r = threadToolpath(op({ type: "THREAD_OD", startDiameter: 0.75, endDiameter: 0.75, endZ: 0.65 }), 1 / 16);
  assert.ok(r.ok);
  if (!r.ok) return;
  for (const m of r.toolpath.moves.filter((m) => m.kind === "THREAD_PASS")) {
    assert.equal(m.feedPerRev, 1 / 16); // the pitch, exactly, every pass
  }
  const depths = r.toolpath.moves.filter((m) => m.kind === "THREAD_PASS").map((m) => m.x);
  for (let i = 1; i < depths.length; i++) assert.ok(depths[i] < depths[i - 1], "each pass must go deeper");
  assert.ok(r.toolpath.assumptions.some((a) => /G97/.test(a)));
});

test("a groove narrower than the insert is refused, not squeezed", () => {
  const r = grooveToolpath(op({ type: "GROOVE_OD", startZ: 0, endZ: 0.1, startDiameter: 1.6, endDiameter: 1.4 }), 0.1, 0.125);
  assert.ok(!r.ok);
  assert.match((r as { ok: false; reason: string }).reason, /narrower than/);
  const r2 = grooveToolpath(op({ type: "GROOVE_OD", startZ: 0, endZ: 0.118, startDiameter: 1.6, endDiameter: 1.4 }), 0.118, 0.118);
  assert.ok(r2.ok);
});

test("finish pass honours spring passes; part-off warns about the drop", () => {
  const f = odFinishToolpath(op({ type: "OD_FINISH", params: { ...op({}).params, springPasses: 2 } }));
  assert.ok(f.ok && f.toolpath.passes === 3);
  const po = partOffToolpath(op({ type: "PART_OFF", startDiameter: 1.85, endDiameter: 0 }), 0.125);
  assert.ok(po.ok);
  if (po.ok) assert.ok(po.toolpath.warnings.some((w) => /drops the part/.test(w)));
});

/* ---- analyses ---- */

test("chuck grip never invents a clamp force: missing inputs give UNKNOWN, not PASS", () => {
  const a = assessChuckGrip({ gripDiameter: 2, gripLength: 1, jawMaterial: "HARD", serrated: true, clampForceLbf: null, stickout: 3, chuckMaxRpm: 4200, programmedMaxRpm: 3000 });
  assert.equal(a.verdict, "UNKNOWN");
  assert.ok(a.missingInputs.some((m) => /Clamp force/.test(m)));
  assert.equal(a.developmentAnalysis, true);
});

test("programmed RPM above the chuck limit is FAIL, no matter the grip", () => {
  const a = assessChuckGrip({ gripDiameter: 2, gripLength: 1, jawMaterial: "HARD", serrated: true, clampForceLbf: 3000, stickout: 1, chuckMaxRpm: 3000, programmedMaxRpm: 4000 });
  assert.equal(a.verdict, "FAIL");
});

test("stickout L/D: 6:1 unsupported is REVIEW, tailstock rescues it, 9:1 unsupported is FAIL", () => {
  assert.equal(assessStickout({ unsupportedLength: 6, diameter: 1, tailstock: false }).verdict, "REVIEW");
  assert.equal(assessStickout({ unsupportedLength: 6, diameter: 1, tailstock: true }).verdict, "PASS");
  assert.equal(assessStickout({ unsupportedLength: 9, diameter: 1, tailstock: false }).verdict, "FAIL");
});

test("boring bar beyond guideline is REVIEW; bar shorter than the bore is FAIL", () => {
  const r = assessBoringBar({ barDiameter: 0.625, stickout: 3.2, boreDepth: 3.0, barMaterial: "STEEL" });
  assert.equal(r.verdict, "REVIEW");
  assert.ok(r.ldRatio > 4);
  assert.equal(assessBoringBar({ barDiameter: 0.625, stickout: 2, boreDepth: 3, barMaterial: "STEEL" }).verdict, "FAIL");
});

test("part-off with the tailstock engaged is FAIL — the blade gets pinched", () => {
  const a = assessPartOff({ cutoffZ: 4.6, cutoffDiameter: 1.85, distanceFromChuck: 4, toolWidth: 0.125, hasPartsCatcher: false, hasSubSpindle: false, tailstockActive: true });
  assert.equal(a.verdict, "FAIL");
});

/* ---- readiness ---- */

test("turning readiness is worst-gate: one FAIL makes NOT READY; UNKNOWN analyses block", () => {
  const base = {
    profile, materialKnown: true, latheSelected: true, workholdingSelected: true,
    grip: assessChuckGrip({ gripDiameter: 2, gripLength: 1, jawMaterial: "HARD" as const, serrated: true, clampForceLbf: 3000, stickout: 1, chuckMaxRpm: 4200, programmedMaxRpm: 3000 }),
    stickout: assessStickout({ unsupportedLength: 2, diameter: 2, tailstock: false }),
    boringBar: null, partOff: null, toolsAssigned: 5, toolsRequired: 5,
    chuckRpmKnown: true, cssUsed: true, inspectionCapable: true, postSelected: true, humanApproved: true,
  };
  assert.equal(evaluateTurnReadiness(base).overall, "READY_TO_RUN");
  assert.equal(evaluateTurnReadiness({ ...base, inspectionCapable: false }).overall, "NOT_READY_TO_RUN");
  assert.equal(evaluateTurnReadiness({ ...base, chuckRpmKnown: false }).overall, "REVIEW_REQUIRED");
});

/* ---- post ---- */

test("the development post refuses CSS without a G50 clamp, and says DEVELOPMENT in its header", () => {
  const tp = odFinishToolpath(op({ type: "OD_FINISH" }));
  assert.ok(tp.ok);
  if (!tp.ok) return;
  const baseOp = { toolpath: tp.toolpath, station: "0202", description: "finish", cssEnabled: true, surfaceSpeed: 700, rpm: 3200, coolant: true };
  const refused = emitLatheProgram([baseOp], { programNumber: "2001", partName: "x", machine: "test", workOffset: "G54", maxRpmClamp: null, generatedAtIso: "2026-08-12" });
  assert.equal(refused.code, "");
  assert.ok(refused.refusals.some((r) => /G50/.test(r)));

  const ok = emitLatheProgram([baseOp], { programNumber: "2001", partName: "x", machine: "test", workOffset: "G54", maxRpmClamp: 3000, generatedAtIso: "2026-08-12" });
  assert.equal(ok.refusals.length, 0);
  assert.match(ok.code, /NOT FOR PRODUCTION USE/);
  assert.match(ok.code, /G50 S3000/);
  assert.match(ok.code, /G96 S700 M3/);
  assert.match(ok.code, /G18 G20/);
});
