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
  chamferToolpath,
  grooveIdToolpath,
  threadIdToolpath,
  tapToolpath,
  reamToolpath,
  REAM_MIN_STOCK,
  REAM_MAX_STOCK,
  radiusBlendToolpath,
  idBoreRoughToolpath,
  idBoreFinishToolpath,
  generateTurnToolpath,
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
    chuckRpmKnown: true, cssUsed: true, inspectionCapable: "CAPABLE" as const, postSelected: true, approval: "APPROVED" as const,
  };
  assert.equal(evaluateTurnReadiness(base).overall, "READY_TO_RUN");
  assert.equal(evaluateTurnReadiness({ ...base, inspectionCapable: "NOT_CAPABLE" as const }).overall, "NOT_READY_TO_RUN");
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

/* ---- lathe NC parser ---- */

import { parseLatheNc, analyzeLatheNc } from "@/lib/manufacturing/turn/nc-parse";

test("SELF-TEST: the parser reads the development post's own output with zero refusals", () => {
  const tp = odFinishToolpath(op({ type: "OD_FINISH" }));
  assert.ok(tp.ok);
  if (!tp.ok) return;
  const emitted = emitLatheProgram(
    [{ toolpath: tp.toolpath, station: "0202", description: "finish journal", cssEnabled: true, surfaceSpeed: 700, rpm: 3200, coolant: true }],
    { programNumber: "2001", partName: "self test", machine: "ref", workOffset: "G54", maxRpmClamp: 3000, generatedAtIso: "2026-08-12" },
  );
  const parsed = parseLatheNc(emitted.code);
  assert.equal(parsed.refusals.length, 0, "the post and the parser must agree on the dialect");
  assert.equal(parsed.cssRegions, 1);
  assert.equal(parsed.sawG50, true);
  const a = analyzeLatheNc(parsed, 4200);
  assert.ok(a.totalMinutes > 0);
  // Two engines, opposite directions: the parser's estimate for the finish
  // pass sits near the engine's own (single pass, same feed and CSS math).
  assert.ok(Math.abs(a.cutMinutes - tp.toolpath.estimatedMinutes) < tp.toolpath.estimatedMinutes * 0.5 + 0.05);
  assert.ok(!a.findings.some((f) => f.kind === "MISSING_MAX_RPM_CLAMP"));
});

test("unclamped G96 is a CONFIDENT finding; G50 above the chuck limit is flagged", () => {
  const prog = "%\nO1\nG18 G20 G99\nG96 S600 M3\nG1 X1.5 Z-2.0 F0.01\nM30\n%";
  const a = analyzeLatheNc(parseLatheNc(prog), null);
  assert.ok(a.findings.some((f) => f.kind === "MISSING_MAX_RPM_CLAMP" && f.verdict === "CONFIDENT"));

  const prog2 = "%\nO1\nG18 G20 G99\nG50 S5000\nG96 S600 M3\nG1 X1.5 Z-2.0 F0.01\nM30\n%";
  const a2 = analyzeLatheNc(parseLatheNc(prog2), 4200);
  assert.ok(a2.findings.some((f) => f.kind === "RPM_LIMIT_REVIEW"));
});

test("canned cycles, macros and TNR comp are refused by line, never assumed safe", () => {
  const prog = "%\nO1\nG18 G20\nG71 U0.08 R0.02\nG41 G1 X1.0 Z0 F0.01\n#100=1\nM98 P100\nM30\n%";
  const parsed = parseLatheNc(prog);
  const codes = parsed.refusals.map((r) => r.code);
  assert.ok(codes.includes("CANNED_CYCLE"));
  assert.ok(codes.includes("TNR_COMP"));
  assert.ok(codes.includes("MACRO"));
  assert.ok(codes.includes("SUBPROGRAM"));
  const a = analyzeLatheNc(parsed, null);
  assert.ok(a.findings.filter((f) => f.kind === "UNSUPPORTED_CONTEXT").length >= 4);
});

test("a cutting move with no spindle context is untimed, not guessed", () => {
  const prog = "%\nO1\nG18 G20 G99\nG1 X1.5 Z-2.0 F0.01\nM30\n%"; // no S, no M3
  const a = analyzeLatheNc(parseLatheNc(prog), null);
  assert.equal(a.unknownSegments, 1);
  assert.ok(a.findings.some((f) => f.kind === "UNKNOWN_SPINDLE_CONTEXT" && f.verdict === "INSUFFICIENT_DATA"));
});

test("fixed RPM across a wide diameter range raises CSS_NOT_USED as REVIEW", () => {
  const prog = ["%", "O1", "G18 G20 G99", "G97 S1200 M3",
    "G1 X3.0 Z-0.5 F0.01", "G1 X2.0 Z-1.0", "G1 X1.0 Z-1.5", "G1 X0.5 Z-2.0", "G1 X0.4 Z-2.5",
    "M30", "%"].join("\n");
  const a = analyzeLatheNc(parseLatheNc(prog), null);
  assert.ok(a.findings.some((f) => f.kind === "CSS_NOT_USED" && f.verdict === "REVIEW"));
});

/* ------------------------------------------------------------------ */
/* Turning cycle optimizer                                             */
/* ------------------------------------------------------------------ */

import { optimizeTurnCycle, type TurnOptContext } from "@/lib/manufacturing/turn/optimize";

const optTools: TurnOptContext["tools"] = {
  "0101": { station: "0101", description: "OD rough", surfaceSpeedMin: 400, surfaceSpeedMax: 900, feedPerRevMin: 0.008, feedPerRevMax: 0.02 },
  "0606": { station: "0606", description: "Threading", surfaceSpeedMin: 200, surfaceSpeedMax: 400, feedPerRevMin: null, feedPerRevMax: null },
};

test("optimizer proposes a feed raise for a rubbing cut, capped by preset", () => {
  // 0.002"/rev on an insert whose window starts at 0.008 — classic rubbing.
  const prog = ["%", "O1", "G18 G20 G99", "T0101", "G97 S1200 M3",
    "G1 X2.0 Z-6.0 F0.002", "G1 Z-12.0", "M30", "%"].join("\n");
  const parsed = parseLatheNc(prog);
  const opt = optimizeTurnCycle(parsed, { tools: optTools, chuckMaxRpm: 4200, preset: "CONSERVATIVE" });
  const feed = opt.proposals.find((p) => p.kind === "FEED");
  assert.ok(feed, "expected a FEED proposal");
  // CONSERVATIVE caps at 1.15× — well below the window midpoint of 0.014.
  assert.equal(feed!.proposed, "F0.0023");
  assert.ok(feed!.assumptions.some((a) => a.includes("Capped at 1.15×")));
  assert.ok(feed!.estimatedSecondsSaved > 0);
  assert.equal(opt.developmentAnalysis, true);
});

test("optimizer never touches a thread pass — the feed is the pitch", () => {
  const prog = ["%", "O1", "G18 G20 G99", "T0606", "G97 S800 M3",
    "G32 X0.74 Z-0.65 F0.0625", "G32 Z-0.65 F0.0625", "M30", "%"].join("\n");
  const opt = optimizeTurnCycle(parseLatheNc(prog), { tools: optTools, chuckMaxRpm: 4200, preset: "AGGRESSIVE" });
  assert.equal(opt.proposals.length, 0);
  assert.ok(opt.segments.every((s) => s.note?.includes("pitch")));
});

test("CSS conversion proposed only with a recorded chuck limit; refused without one", () => {
  const prog = ["%", "O1", "G18 G20 G99", "T0101", "G97 S800 M3",
    "G1 X3.0 Z-0.5 F0.012", "G1 X1.0 Z-3.0", "G1 X0.6 Z-5.0", "M30", "%"].join("\n");
  const parsed = parseLatheNc(prog);
  const withChuck = optimizeTurnCycle(parsed, { tools: optTools, chuckMaxRpm: 4200, preset: "BALANCED" });
  const css = withChuck.proposals.find((p) => p.kind === "CSS_CONVERSION");
  assert.ok(css, "expected a CSS_CONVERSION proposal");
  assert.equal(css!.risk, "REVIEW");
  assert.ok(css!.proposed.includes("G50 S4200"));
  assert.ok(css!.estimatedSecondsSaved > 0);

  const noChuck = optimizeTurnCycle(parsed, { tools: optTools, chuckMaxRpm: null, preset: "BALANCED" });
  assert.ok(!noChuck.proposals.some((p) => p.kind === "CSS_CONVERSION"));
  assert.ok(noChuck.gaps.some((g) => g.includes("max RPM is not recorded")));
});

test("cuts on an unrecorded tool get no verdict and no proposals", () => {
  const prog = ["%", "O1", "G18 G20 G99", "T0505", "G97 S900 M3",
    "G1 X2.0 Z-6.0 F0.001", "M30", "%"].join("\n");
  const opt = optimizeTurnCycle(parseLatheNc(prog), { tools: optTools, chuckMaxRpm: 4200, preset: "AGGRESSIVE" });
  assert.equal(opt.proposals.length, 0);
  assert.ok(opt.segments.every((s) => s.band === "UNKNOWN"));
  assert.ok(opt.gaps.some((g) => g.includes("T0505")));
});

test("SELF-TEST: the optimizer leaves the engine's own program alone where feeds sit in the window", () => {
  const tp = odRoughToolpath(op({ type: "OD_ROUGH", toolStation: "0101", startDiameter: 2.0, endDiameter: 1.87, startZ: 0, endZ: 4.6, params: { ...op({}).params, feedPerRev: 0.012, surfaceSpeed: 550, cssEnabled: true } }), profile);
  assert.ok(tp.ok);
  if (!tp.ok) return;
  const { code, refusals } = emitLatheProgram(
    [{ toolpath: tp.toolpath, station: "0101", description: "rough", cssEnabled: true, surfaceSpeed: 550, rpm: 3000, coolant: true }],
    { programNumber: "2002", partName: "opt self test", machine: "ref", workOffset: "G54", maxRpmClamp: 3000, generatedAtIso: "2026-08-12" },
  );
  assert.equal(refusals.length, 0);
  const opt = optimizeTurnCycle(parseLatheNc(code), { tools: optTools, chuckMaxRpm: 4200, preset: "BALANCED" });
  // 0.012"/rev is inside the 0.008–0.02 window: no FEED proposal against our own post.
  assert.ok(!opt.proposals.some((p) => p.kind === "FEED"));
});

/* ------------------------------------------------------------------ */
/* Lathe soft jaws                                                     */
/* ------------------------------------------------------------------ */

import { planSoftJawBore, findReusableLatheJaws } from "@/lib/manufacturing/turn/soft-jaws";

const jawChuck = { description: "8in chuck", jawStroke: 0.24, chuckDiameter: 8, maxRPM: 4200 };
const jawBar = { station: "0404", description: "boring bar", barDiameter: 0.625, minBoreDiameter: 0.8, surfaceSpeedMin: 350, surfaceSpeedMax: 800, feedPerRevMin: 0.004, feedPerRevMax: 0.01 };

test("soft jaw recipe bores at the grip diameter under a stroke-sized preload ring", () => {
  const plan = planSoftJawBore({ gripDiameter: 2.0, gripLength: 1.0, chuck: jawChuck, boringTool: jawBar });
  assert.ok(plan.ok);
  if (!plan.ok) return;
  assert.equal(plan.boreDiameter, 2.0);
  assert.equal(plan.boreDepth, 1.05);
  assert.equal(plan.preloadRingDiameter, 2.12); // grip + stroke/2
  // RPM from the bar's 800 SFM ceiling at ⌀2.0, under the chuck cap.
  assert.equal(plan.boringRpm, Math.round((800 * 12) / (Math.PI * 2)));
  assert.equal(plan.developmentAnalysis, true);
  assert.ok(plan.steps.some((s) => /UNDER PRELOAD|under load/i.test(s.text)));
  assert.ok(plan.steps.some((s) => /measurement, not a promise/.test(s.text)));
});

test("soft jaw recipe refuses without a grip, and never invents a preload ring without a stroke", () => {
  const refused = planSoftJawBore({ gripDiameter: null, gripLength: null, chuck: jawChuck, boringTool: jawBar });
  assert.ok(!refused.ok);
  if (refused.ok) return;
  assert.equal(refused.refusals.length, 2);

  const noStroke = planSoftJawBore({ gripDiameter: 2.0, gripLength: 1.0, chuck: { ...jawChuck, jawStroke: null }, boringTool: jawBar });
  assert.ok(noStroke.ok);
  if (!noStroke.ok) return;
  assert.equal(noStroke.preloadRingDiameter, null);
  assert.ok(noStroke.missingInputs.some((m) => m.includes("jaw stroke")));
});

test("soft jaw recipe refuses a bore the boring bar cannot enter", () => {
  const r = planSoftJawBore({ gripDiameter: 0.5, gripLength: 0.4, chuck: jawChuck, boringTool: jawBar });
  assert.ok(!r.ok);
  if (r.ok) return;
  assert.ok(r.refusals.some((x) => x.includes("cannot enter")));
});

test("drawer search: a bored chuck jaw only ever grows", () => {
  const inv = [
    { id: "a", description: "Set A", boredDiameter: 2.0, boredDepth: 1.1 },
    { id: "b", description: "Set B", boredDiameter: 1.75, boredDepth: 1.1 },
    { id: "c", description: "Set C", boredDiameter: 2.5, boredDepth: 1.1 },
    { id: "d", description: "Set D", boredDiameter: null, boredDepth: null },
  ];
  const m = findReusableLatheJaws(2.0, 1.0, inv);
  assert.equal(m[0].kind, "DIRECT");
  assert.equal(m[0].jawSet.id, "a");
  assert.equal(m[1].kind, "REBORE"); // 1.75 grows 0.25 to 2.0
  assert.equal(m[1].jawSet.id, "b");
  assert.equal(m[2].kind, "BLANK");
  const c = m.find((x) => x.jawSet.id === "c")!;
  assert.equal(c.kind, "UNUSABLE"); // 2.5 cannot shrink
  assert.ok(c.reason.includes("cannot shrink"));
});

test("drawer search: a shallow step is a re-bore, a huge growth is a new blank", () => {
  const m = findReusableLatheJaws(2.0, 1.0, [
    { id: "s", description: "Shallow", boredDiameter: 2.0, boredDepth: 0.5 },
    { id: "g", description: "Tiny", boredDiameter: 1.2, boredDepth: 1.1 },
  ]);
  const shallow = m.find((x) => x.jawSet.id === "s")!;
  assert.equal(shallow.kind, "REBORE");
  assert.ok(shallow.reason.includes("deepen"));
  const tiny = m.find((x) => x.jawSet.id === "g")!;
  assert.equal(tiny.kind, "UNUSABLE"); // 0.8" growth > 0.5 max
});

/* ------------------------------------------------------------------ */
/* Turning reverse engineering                                         */
/* ------------------------------------------------------------------ */

import { assembleMeasuredProfile, nextTurnTask, type TurnReading } from "@/lib/manufacturing/turn/reverse";

test("RE readings assemble front to back with MEASURED provenance and a suggested stock", () => {
  const readings: TurnReading[] = [
    { diameter: 0.7495, length: 0.75, uncertainty: 0.0001, instrument: "mic" },
    { diameter: 1.5744, length: 1.2, uncertainty: 0.0001, instrument: "mic" },
    { diameter: 1.85, length: 2.5, uncertainty: 0.001, instrument: "caliper" },
  ];
  const a = assembleMeasuredProfile(readings);
  assert.ok(a.profile);
  const p = a.profile!;
  assert.equal(p.segments.length, 3);
  assert.equal(p.segments[1].zStart, 0.75);
  assert.equal(p.segments[2].zEnd, 4.45);
  assert.ok(p.segments.every((s) => s.source === "MEASURED" && !s.confirmedByUser));
  // Max ⌀1.85 + 1/16 cleanup → next standard bar is 2.0.
  assert.equal(p.stockDiameter, 2.0);
  assert.ok(a.stockNote!.includes("SUGGESTION"));
});

test("RE never rounds a reading: accepting a nominal is a ruling, recorded as USER", () => {
  const measured: TurnReading[] = [{ diameter: 1.5744, length: 1.0, uncertainty: 0.0001, instrument: "mic" }];
  const before = assembleMeasuredProfile(measured).profile!;
  assert.equal(before.segments[0].diameterStart, 1.5744); // untouched
  const ruled: TurnReading[] = [{ ...measured[0], resolution: "NOMINAL", resolvedDiameter: 1.5748 }];
  const after = assembleMeasuredProfile(ruled).profile!;
  assert.equal(after.segments[0].diameterStart, 1.5748);
  assert.equal(after.segments[0].source, "USER");
  assert.equal(after.segments[0].confirmedByUser, true);
  // Keeping the measurement is also a ruling — confirmed, still MEASURED.
  const kept = assembleMeasuredProfile([{ ...measured[0], resolution: "MEASURED" }]).profile!;
  assert.equal(kept.segments[0].source, "MEASURED");
  assert.equal(kept.segments[0].confirmedByUser, true);
});

test("RE thread readings carry the gauged designation verbatim; unrecorded instruments are flagged", () => {
  const a = assembleMeasuredProfile([
    { diameter: 0.75, length: 0.65, uncertainty: null, instrument: null, thread: "3/4-16 UNF-2A" },
  ]);
  assert.equal(a.profile!.segments[0].kind, "THREAD");
  assert.equal(a.profile!.segments[0].thread, "3/4-16 UNF-2A");
  assert.ok(a.issues.some((x) => x.includes("uncertainty is unknown")));
});

test("RE guidance starts at the datum face and runs front to back", () => {
  const first = nextTurnTask([]);
  assert.equal(first.step, 1);
  assert.ok(/datum face/i.test(first.instruction));
  const later = nextTurnTask([{ diameter: 1, length: 2, uncertainty: 0.001, instrument: "mic" }]);
  assert.equal(later.step, 2);
  assert.ok(later.instruction.includes("Z2.000"));
  assert.ok(/thread gauge/i.test(later.instruction));
});

test("RE with no readings yields no profile, not a fake one", () => {
  const a = assembleMeasuredProfile([]);
  assert.equal(a.profile, null);
  assert.ok(a.issues[0].includes("datum face"));
});

/* ------------------------------------------------------------------ */
/* Turning cost — bar economics                                        */
/* ------------------------------------------------------------------ */

import { computeBarEconomics, deriveTurnCostAssumptions } from "@/lib/manufacturing/turn/cost";

const costProfile: RotationalProfile = { ...profile, stockDiameter: 2.0, stockLength: 6.0 };
const costBase = {
  profile: costProfile, cycleMinutes: 8.5, partOffKerf: 0.125,
  gripLength: 1.0, softJawsNeedBoring: false, tailstock: false,
};

test("bar economics: parts per bar and utilization are computed, not assumed", () => {
  const bar = computeBarEconomics(costBase);
  // Remnant = 1.0 grip + 1.0 margin; (144 - 2) / 6.125 → 23 parts.
  assert.equal(bar.remnant, 2.0);
  assert.equal(bar.partsPerBar, 23);
  // Utilization amortises remnant + drop only: 23 × 6.125 / 144.
  assert.equal(bar.utilization, Number(((23 * 6.125) / 144).toFixed(3)));
  assert.equal(bar.missingInputs.length, 0);
});

test("bar economics refuse to compute without a recorded kerf or grip", () => {
  const noKerf = computeBarEconomics({ ...costBase, partOffKerf: null });
  assert.equal(noKerf.partsPerBar, null);
  assert.equal(noKerf.utilization, null);
  assert.ok(noKerf.missingInputs.some((m) => m.includes("parting tool")));
  const noGrip = computeBarEconomics({ ...costBase, gripLength: null });
  assert.equal(noGrip.partsPerBar, null);
  assert.ok(noGrip.missingInputs.some((m) => m.includes("Grip length")));
});

test("turning assumptions: setup adders are named, cycle passes through from toolpaths", () => {
  const plain = deriveTurnCostAssumptions(costBase);
  assert.equal(plain.assumptions.setupHours, 0.75);
  assert.equal(plain.assumptions.cycleMinutes, 8.5);
  assert.equal(plain.assumptions.materialUtilization, plain.bar.utilization);
  const jaws = deriveTurnCostAssumptions({ ...costBase, softJawsNeedBoring: true, tailstock: true });
  assert.equal(jaws.assumptions.setupHours, 1.5); // 0.75 + 0.6 + 0.15
  assert.ok(jaws.basis.some((b) => b.includes("boring jaws")));
  assert.ok(jaws.basis.some((b) => b.includes("tailstock") || b.includes("tailstock".toUpperCase()) || b.includes("Tailstock")));
});

test("turning assumptions fall back to the visible shop default when bar math is refused", () => {
  const d = deriveTurnCostAssumptions({ ...costBase, partOffKerf: null });
  assert.equal(d.assumptions.materialUtilization, 0.85); // DEFAULT_ASSUMPTIONS, named in basis
  assert.ok(d.basis.some((b) => b.includes("falls back")));
});

/* ------------------------------------------------------------------ */
/* Turning stock simulation                                            */
/* ------------------------------------------------------------------ */

import { buildTurnSim, stateAt, toolAt } from "@/lib/manufacturing/turn/sim";

function simOps() {
  const rough = odRoughToolpath(op({}), profile);
  assert.ok(rough.ok);
  if (!rough.ok) throw new Error("unreachable");
  return [{ op: op({}), moves: rough.toolpath.moves }];
}

test("turn sim: raw stock at t=0, target envelope at the end, radius never grows", () => {
  const sim = buildTurnSim(profile, simOps());
  assert.equal(sim.developmentAnalysis, true);
  assert.ok(sim.totalMinutes > 0);
  const start = stateAt(sim, 0);
  assert.ok([...start].every((r) => Math.abs(r - 1.0) < 1e-9), "starts as raw ⌀2.0 stock");
  const end = stateAt(sim, sim.totalMinutes);
  // Rough to ⌀1.6 + 0.01 allowance per side → radius 0.81 over the cut span.
  const cutCells = [...end].filter((r) => r < 1.0 - 1e-6);
  assert.ok(cutCells.length > 0);
  assert.ok(Math.min(...cutCells) >= 0.81 - 1e-6);
  // Monotonic: at every op boundary the envelope only ever shrinks.
  let prev = stateAt(sim, 0);
  for (const o of sim.opEnds) {
    const now = stateAt(sim, o.tEnd);
    for (let i = 0; i < now.length; i++) assert.ok(now[i] <= prev[i] + 1e-9);
    prev = now;
  }
});

test("turn sim: mid-cut state carves only the swept portion", () => {
  const sim = buildTurnSim(profile, simOps());
  const firstCut = sim.moves.find((m) => m.kind === "CUT" && Math.abs(m.z - m.z0) > 0.5)!;
  const mid = stateAt(sim, (firstCut.t0 + firstCut.t1) / 2);
  const cut = [...mid].filter((r) => r < 1.0 - 1e-6).length;
  const full = [...stateAt(sim, firstCut.t1)].filter((r) => r < 1.0 - 1e-6).length;
  assert.ok(cut > 0 && cut < full, "half the pass carves roughly half the span");
});

test("turn sim: internal ops advance the clock but never carve the OD, and the note says so", () => {
  const center = op({ type: "CENTER_DRILL", startZ: 4.6, endZ: 4.35, startDiameter: 0, endDiameter: 0 });
  const moves = [
    { kind: "RAPID" as const, x: 0, z: 4.7, feedPerRev: null },
    { kind: "CUT" as const, x: 0, z: 4.35, feedPerRev: 0.003 },
  ];
  const sim = buildTurnSim(profile, [{ op: center, moves }]);
  assert.ok(sim.totalMinutes > 0, "clock advances");
  const end = stateAt(sim, sim.totalMinutes);
  assert.ok([...end].every((r) => Math.abs(r - 1.0) < 1e-9), "OD untouched");
  assert.ok(sim.notes.some((n) => n.includes("not modelled")));
});

test("turn sim: the tool point follows the clock and reports rapid vs cut", () => {
  const sim = buildTurnSim(profile, simOps());
  const t0 = toolAt(sim, 0)!;
  assert.ok(t0);
  const cutMove = sim.moves.find((m) => m.kind === "CUT")!;
  const mid = toolAt(sim, (cutMove.t0 + cutMove.t1) / 2)!;
  assert.equal(mid.kind, "CUT");
  const endTool = toolAt(sim, sim.totalMinutes + 5)!;
  assert.ok(endTool, "clamps past the end instead of vanishing");
});

/* ------------------------------------------------------------------ */
/* Cinematic turning mappings                                          */
/* ------------------------------------------------------------------ */

import { generateCinematic, type CinematicInput, type CinematicSettings } from "@/lib/cinematic";

const cinInput: CinematicInput = {
  partName: "Demo Shaft",
  partNumber: "CNV-T001",
  material: "Steel 4140",
  process: "TURN",
  stock: null,
  barStock: { diameter: 2.0, length: 6.0 },
  setupName: "Chuck setup",
  workholding: '8" 3-jaw hydraulic chuck',
  hasSoftJaws: false,
  readiness: "NOT_READY",
  operations: [
    { id: "10", label: "Face front", type: "FACE", toolDescription: "CNMG 432", cycleMinutes: 0.06 },
    { id: "30", label: "Finish bearing journal", type: "OD_FINISH", toolDescription: "VNMG 331", cycleMinutes: 0.4 },
    { id: "60", label: "Thread 3/4-16 UNF", type: "THREAD_OD", toolDescription: "60° threading insert", cycleMinutes: 0.3 },
    { id: "70", label: "Part off", type: "PART_OFF", toolDescription: "cutoff blade", cycleMinutes: 0.2 },
  ],
};
const cinSettings: CinematicSettings = {
  durationSeconds: 15,
  style: "TECHNICAL_MINIMAL",
  include: { softJaws: true, stock: true, toolAndHolder: true, toolpathTrace: true, materialRemoval: true, datumLabels: false, measurementOverlays: true, operationLabels: true, coolantChips: false, finalReveal: true },
  customerSafe: false,
};

test("cinematic turning speaks the lathe voice: the bar spins, the tool holds", () => {
  const r = generateCinematic(cinInput, cinSettings);
  assert.ok(r.prompt.includes("⌀2 × 6 in"), "bar stock spoken as diameter × length");
  assert.ok(r.prompt.includes("gripped in the chuck"));
  // FACE maps to the turning verb, not the mill's face-mill sweep.
  assert.ok(r.prompt.includes("Facing insert"));
  assert.ok(!r.prompt.includes("Face mill"));
  assert.ok(r.prompt.includes("spinning journal"));
  assert.ok(r.prompt.includes("deepens visibly each pass"), "threading is passes, never one plunge");
  assert.ok(r.prompt.includes("separates and is caught"));
  assert.ok(r.prompt.toLowerCase().includes("the bar spins, the camera holds"));
  assert.equal(r.disclaimer, "Cinematic preview only. Not NC verification.");
});

test("cinematic customer-safe strips turning identity but keeps process nouns", () => {
  const r = generateCinematic(cinInput, { ...cinSettings, customerSafe: true });
  assert.ok(!r.prompt.includes("CNV-T001"));
  assert.ok(!r.prompt.includes("VNMG"));
  assert.ok(!r.prompt.includes("⌀2 × 6"));
  assert.ok(r.prompt.includes("beginning to spin"));
  assert.ok(r.storyboard.selectedOperations.includes("Finish turning"));
  assert.ok(r.storyboard.selectedOperations.includes("Thread turning"));
  assert.ok(r.storyboard.selectedOperations.includes("Parting off"));
  // Material reduced to family.
  assert.ok(!r.prompt.includes("4140"));
});

test("cinematic mill wording is untouched by the turning additions", () => {
  const mill = generateCinematic(
    { ...cinInput, process: "MILL", barStock: null, stock: { x: 6, y: 4, z: 0.75 }, operations: [{ id: "1", label: "Face top", type: "FACE", toolDescription: "2in face mill", cycleMinutes: 1 }] },
    cinSettings,
  );
  assert.ok(mill.prompt.includes("Face mill"));
  assert.ok(mill.prompt.includes("6 × 4 × 0.75 in"));
});

/* ------------------------------------------------------------------ */
/* ID boring                                                           */
/* ------------------------------------------------------------------ */

const bore = (over: Partial<TurnOperation> = {}) =>
  op({ type: "ID_BORE_ROUGH", label: "bore", startDiameter: 0.75, endDiameter: 1.25, startZ: 0, endZ: 1.5, ...over });

/** Every X in the path, in program order. X is a DIAMETER on a lathe. */
const xs = (r: ReturnType<typeof idBoreRoughToolpath>) => (r.ok ? r.toolpath.moves.map((m) => m.x) : []);

test("boring opens the hole outward, never down from stock", () => {
  const r = idBoreRoughToolpath(bore(), 0.5);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  assert.ok(r.toolpath.passes > 1, "0.25\" on radius at 0.08 doc is more than one pass");
  // The full-length cuts, one per pass, must STRICTLY PROGRESS outward. A
  // pass list that jumps straight to size on every pass is not roughing, it
  // is one cut repeated — and it passes a "did it reach size" assertion.
  // The arriving cut of each pass: a CUT that changed Z at constant X. (The
  // other CUT at depth is the come-off-the-wall move, which changes X.)
  const mv = r.toolpath.moves;
  const atDepth = mv
    .filter((m, i) => i > 0 && m.kind === "CUT" && m.z === 1.5 && m.x === mv[i - 1].x && m.z !== mv[i - 1].z)
    .map((m) => m.x);
  assert.equal(atDepth.length, r.toolpath.passes, "one full-length cut per pass");
  for (let i = 1; i < atDepth.length; i++) {
    assert.ok(atDepth[i] > atDepth[i - 1], `pass ${i + 1} did not open the bore further: ${atDepth.join(" -> ")}`);
  }
  assert.ok(atDepth[0] > 0.75, "the first pass must open out from the drilled hole");
  const atSize = atDepth[atDepth.length - 1];
  assert.ok(atSize <= 1.25 - 2 * 0.01 + 1e-9, `roughing left no finish allowance: ${atSize}`);
});

test("every retract inside a bore goes INWARD — outward is the wall", () => {
  // The mistake this pins: on an OD you retract to a LARGER diameter to come
  // clear. Do that inside a bore and the bar is driven into the wall it just
  // cut. Both bore engines must come off the wall by going smaller.
  for (const [name, r] of [
    ["rough", idBoreRoughToolpath(bore(), 0.5)],
    ["finish", idBoreFinishToolpath(bore({ type: "ID_BORE_FINISH", params: { ...bore().params, springPasses: 1 } }), 0.5)],
  ] as const) {
    assert.equal(r.ok, true, r.ok ? "" : r.reason);
    if (!r.ok) return;
    const moves = r.toolpath.moves;
    for (let i = 1; i < moves.length; i++) {
      const prev = moves[i - 1];
      const m = moves[i];
      // A pure Z move at the far end of a cut is the retract. It must never
      // happen at a diameter larger than the cut that preceded it.
      if (m.z !== prev.z && m.x > prev.x) {
        assert.fail(`${name}: moved to a larger diameter (${prev.x} -> ${m.x}) while changing Z — that is into the wall`);
      }
    }
    // And the maximum X reached is the bore itself, never beyond it.
    assert.ok(Math.max(...moves.map((x) => x.x)) <= 1.25 + 1e-9, `${name} exceeded the finished bore diameter`);
    // Stronger: the tool must LEAVE the wall before Z moves at all. A
    // diagonal away from the wall still starts the Z move at cutting
    // diameter, dragging the tool along the surface it just cut.
    let arrivals = 0;
    for (let i = 1; i < moves.length - 1; i++) {
      const cut = moves[i];
      // A cut that travelled in Z at constant X is a full-length pass. What
      // follows it must be a pure X move off the wall — a diagonal away is
      // still Z motion begun at the cutting diameter, dragging the tool
      // along the surface it just cut.
      if (cut.kind === "CUT" && cut.x === moves[i - 1].x && cut.z !== moves[i - 1].z) {
        arrivals++;
        const next = moves[i + 1];
        assert.equal(next.z, cut.z, `${name}: Z moved while still at the cutting diameter`);
        assert.ok(next.x < cut.x, `${name}: did not come off the wall after the cut`);
      }
    }
    assert.ok(arrivals > 0, `${name}: no full-length cutting pass found`);
  }
});

test("a bar that does not fit the hole is refused, and so is an unrecorded bar", () => {
  // A boring bar cannot enter a hole smaller than itself, so it cannot cut a
  // bore it cannot enter. Reach is a separate question, assessed at plan level.
  const tooBig = idBoreRoughToolpath(bore({ startDiameter: 0.4 }), 0.5);
  assert.equal(tooBig.ok, false);
  assert.ok(!tooBig.ok && /does not fit/i.test(tooBig.reason), tooBig.ok ? "" : tooBig.reason);

  const unrecorded = idBoreRoughToolpath(bore(), null);
  assert.equal(unrecorded.ok, false);
  assert.ok(!unrecorded.ok && /will not assume a bar/i.test(unrecorded.reason), unrecorded.ok ? "" : unrecorded.reason);
});

test("boring from solid is refused — the bar needs a hole to start in", () => {
  const solid = idBoreRoughToolpath(bore({ startDiameter: 0 }), 0.5);
  assert.equal(solid.ok, false);
  assert.ok(!solid.ok && /existing hole/i.test(solid.reason), solid.ok ? "" : solid.reason);

  // Nor is a "bore" that removes nothing a bore.
  const nothing = idBoreRoughToolpath(bore({ endDiameter: 0.75 }), 0.5);
  assert.equal(nothing.ok, false);
  assert.ok(!nothing.ok && /removes nothing/i.test(nothing.reason), nothing.ok ? "" : nothing.reason);
});

test("a finish allowance that swallows the roughing pass is named, not silently skipped", () => {
  const r = idBoreRoughToolpath(
    bore({ endDiameter: 0.8, params: { ...bore().params, finishAllowance: 0.05 } }),
    0.5,
  );
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /nothing to cut/i.test(r.reason), r.ok ? "" : r.reason);
});

test("the bore finish pass runs at size, with its spring passes", () => {
  const r = idBoreFinishToolpath(
    bore({ type: "ID_BORE_FINISH", params: { ...bore().params, springPasses: 2 } }),
    0.5,
  );
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  assert.equal(r.toolpath.passes, 3);
  const cuts = r.toolpath.moves.filter((m) => m.kind === "CUT");
  // Finishing cuts sit at the finished bore, not short of it.
  assert.ok(cuts.some((m) => Math.abs(m.x - 1.25) < 1e-9), "no cut at the finished diameter");
  assert.ok(r.toolpath.assumptions.some((a) => /ESTIMATED/.test(a)));
  assert.ok(r.toolpath.assumptions.some((a) => /off the bore wall/i.test(a)));
});

test("generateTurnToolpath routes the bore types and passes the bar through", () => {
  const profile = {
    units: "IN" as const, zZeroReference: "front face", stockDiameter: 2, stockLength: 4,
    barStock: true, segments: [],
  };
  const withBar = generateTurnToolpath(bore(), profile, { barDiameter: 0.5 });
  assert.equal(withBar.ok, true, withBar.ok ? "" : withBar.reason);
  // The default is "no bar recorded", which refuses rather than assuming one.
  const withoutBar = generateTurnToolpath(bore(), profile, {});
  assert.equal(withoutBar.ok, false);
});

/* ------------------------------------------------------------------ */
/* Chamfers and blends                                                 */
/* ------------------------------------------------------------------ */

const cham = (over: Partial<TurnOperation> = {}) =>
  op({ type: "CHAMFER", label: "chamfer", startZ: 0, endZ: 0.05, startDiameter: 0.9, endDiameter: 1.0, ...over });

const blend = (over: Partial<TurnOperation> = {}) =>
  op({ type: "RADIUS_BLEND", label: "blend", startZ: 0, endZ: 0.25, startDiameter: 1.0, endDiameter: 1.5, ...over });

test("a chamfer or a blend refuses without a recorded nose radius", () => {
  // A straight OD gets away with ignoring the insert nose: it touches the
  // work at the programmed X. A taper or an arc does not — the contact
  // point walks around the nose, and the profile error scales with it.
  for (const r of [chamferToolpath(cham(), null), radiusBlendToolpath(blend(), 0.25, null, false)]) {
    assert.equal(r.ok, false);
    assert.ok(!r.ok && /nose radius/i.test(r.reason), r.ok ? "" : r.reason);
  }
});

test("a chamfer is one interpolated cut and says what the uncompensated path costs", () => {
  const r = chamferToolpath(cham(), 0.0312);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  const cuts = r.toolpath.moves.filter((m) => m.kind === "CUT");
  // Onto the start diameter, then one move that changes X and Z together.
  const slant = cuts[cuts.length - 1];
  assert.equal(slant.x, 1.0);
  assert.equal(slant.z, 0.05);
  assert.ok(slant.feedPerRev !== null, "the chamfer must be cut, not rapided");
  // 45 degrees: 0.05 in Z against 0.05 on radius.
  assert.ok(r.toolpath.assumptions.some((a) => /45\.0°/.test(a)), r.toolpath.assumptions.join(" | "));
  // The nose radius is named, with the number, in a warning — not buried.
  assert.ok(r.toolpath.warnings.some((w) => /0\.0312/.test(w) && /compensation/i.test(w)), r.toolpath.warnings.join(" | "));
});

test("a chamfer with no extent is refused rather than emitted as a zero move", () => {
  const r = chamferToolpath(cham({ endZ: 0, endDiameter: 0.9 }), 0.0312);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /nothing to cut/i.test(r.reason), r.ok ? "" : r.reason);
});

test("a blend will not pick a side when the segment does not record which way it curves", () => {
  // `internal` says bore-or-OD. It does NOT say concave-or-convex: an OD
  // shoulder carries a concave fillet every day. Confusing the two puts the
  // arc on the wrong side of its own endpoints.
  const r = radiusBlendToolpath(blend(), 0.25, 0.0156, null);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /which way/i.test(r.reason), r.ok ? "" : r.reason);
});

test("blend points lie on the true arc, to the tolerance the engine claims", () => {
  // The first implementation interpolated the chord and pushed each point
  // out by a parabola. It claimed 0.0005" and delivered 0.0027" — five
  // times worse, stated with a confidence it had not earned.
  const R = 0.25;
  for (const concave of [false, true]) {
    const r = radiusBlendToolpath(blend(), R, 0.0156, concave);
    assert.equal(r.ok, true, r.ok ? "" : r.reason);
    if (!r.ok) return;
    const pts = r.toolpath.moves.filter((m) => m.kind === "CUT").map((m) => [m.z, m.x / 2] as const);
    // Recover the centre from the endpoints and R, on the recorded side.
    const [p0, p1] = [pts[0], pts[pts.length - 1]];
    const c = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
    const h = Math.sqrt(R * R - (c / 2) ** 2);
    const nz = -(p1[1] - p0[1]) / c;
    const nr = (p1[0] - p0[0]) / c;
    const side = concave ? 1 : -1;
    const cz = (p0[0] + p1[0]) / 2 + nz * h * side;
    const cr = (p0[1] + p1[1]) / 2 + nr * h * side;
    let worst = 0;
    for (const [z, rad] of pts) worst = Math.max(worst, Math.abs(Math.hypot(z - cz, rad - cr) - R));
    assert.ok(worst < 0.0005, `${concave ? "concave" : "convex"} blend deviates ${worst.toFixed(6)} from a true R${R} arc`);
    // Endpoints are exact — a blend that misses its own ends leaves a step.
    assert.ok(Math.abs(pts[0][1] * 2 - 1.0) < 1e-6, "start diameter not hit");
    assert.ok(Math.abs(pts[pts.length - 1][1] * 2 - 1.5) < 1e-6, "end diameter not hit");
  }
});

test("concave and convex blends of the same endpoints curve opposite ways", () => {
  const mid = (concave: boolean) => {
    const r = radiusBlendToolpath(blend(), 0.25, 0.0156, concave);
    assert.equal(r.ok, true);
    if (!r.ok) throw new Error();
    const cuts = r.toolpath.moves.filter((m) => m.kind === "CUT");
    const m = cuts[Math.floor(cuts.length / 2)];
    // Radius of the straight chord at the same Z, to compare against.
    const chord = 0.5 + (0.75 - 0.5) * (m.z / 0.25);
    return m.x / 2 - chord;
  };
  // A round ON the material stands proud of the chord; a fillet cut INTO it
  // falls inside. Same endpoints, opposite sides.
  assert.ok(mid(false) > 0, "a convex blend must bulge away from the centreline");
  assert.ok(mid(true) < 0, "a concave blend must cut in toward the centreline");
});

test("a nose bigger than a concave blend cannot produce it", () => {
  // Endpoints an R0.01 arc can actually span — otherwise the refusal comes
  // from the geometry rather than from the insert, and proves nothing about
  // the nose. (It did, on the first try.)
  const small = blend({ startZ: 0, endZ: 0.01, startDiameter: 1.0, endDiameter: 1.02 });
  const r = radiusBlendToolpath(small, 0.01, 0.0312, true);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /cannot produce a concave/i.test(r.reason), r.ok ? "" : r.reason);
  // A convex blend has no such limit — a big nose rolls around the outside.
  const convex = radiusBlendToolpath(small, 0.01, 0.0312, false);
  assert.equal(convex.ok, true, convex.ok ? "" : convex.reason);
});

test("a blend refuses a radius it cannot reach, and one that was never recorded", () => {
  // Endpoints 0.354" apart cannot be spanned by an R0.1 arc.
  const tooSmall = radiusBlendToolpath(blend(), 0.1, 0.0156, false);
  assert.equal(tooSmall.ok, false);
  assert.ok(!tooSmall.ok && /no R0\.1000 arc can span/i.test(tooSmall.reason), tooSmall.ok ? "" : tooSmall.reason);

  const none = radiusBlendToolpath(blend(), null, 0.0156, false);
  assert.equal(none.ok, false);
  assert.ok(!none.ok && /will not choose one/i.test(none.reason), none.ok ? "" : none.reason);
});

test("the chorded blend is declared as chords, not claimed as an arc", () => {
  // The post has no arc output. A move the engine cannot express is not a
  // move it should describe as one.
  const r = radiusBlendToolpath(blend(), 0.25, 0.0156, false);
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.ok(r.toolpath.moves.every((m) => m.kind !== "THREAD_PASS"));
  assert.ok(
    r.toolpath.assumptions.some((a) => /chorded into \d+ linear moves/.test(a) && /0\.0005/.test(a)),
    r.toolpath.assumptions.join(" | "),
  );
});

test("generateTurnToolpath routes chamfers and blends with their context", () => {
  const profile = {
    units: "IN" as const, zZeroReference: "front face", stockDiameter: 2, stockLength: 4,
    barStock: true, segments: [],
  };
  assert.equal(generateTurnToolpath(cham(), profile, { noseRadius: 0.0156 }).ok, true);
  assert.equal(generateTurnToolpath(cham(), profile, {}).ok, false);
  assert.equal(
    generateTurnToolpath(blend(), profile, { noseRadius: 0.0156, blendRadius: 0.25, concave: false }).ok,
    true,
  );
  // Missing concavity is carried through as a refusal, not defaulted.
  assert.equal(generateTurnToolpath(blend(), profile, { noseRadius: 0.0156, blendRadius: 0.25 }).ok, false);
});

/* ------------------------------------------------------------------ */
/* Tap and ream                                                        */
/* ------------------------------------------------------------------ */

const tapOp = (over: Partial<TurnOperation> = {}) =>
  op({
    type: "TAP", label: "tap 1/4-20", startZ: 0, endZ: -0.5, startDiameter: 0.201, endDiameter: 0.25,
    params: { ...op({}).params, cssEnabled: false, rpm: 400, feedPerRev: 0.05 },
    ...over,
  });

test("a tap's feed IS its pitch — programmed feed is overridden and the override stated", () => {
  const pitch = 1 / 20;
  const r = tapToolpath(tapOp(), pitch);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  const cuts = r.toolpath.moves.filter((m) => m.kind === "CUT");
  assert.equal(cuts.length, 2, "in and back out");
  for (const c of cuts) assert.equal(c.feedPerRev, pitch);
  // 0.05 != 0.05? The programmed feed HERE equals the pitch, so no override
  // warning — change the programmed feed and the override is named.
  const off = tapToolpath(tapOp({ params: { ...tapOp().params, feedPerRev: 0.01 } }), pitch);
  assert.ok(off.ok && off.toolpath.warnings.some((w) => /overridden to the 0\.0500" pitch/.test(w)));
  // And the MOVES carry the pitch, not the programmed feed — the fixture
  // above has feed == pitch, so it cannot see this on its own. (A mutation
  // feeding the tap at params.feedPerRev survived exactly there.)
  if (off.ok) for (const c of off.toolpath.moves.filter((m) => m.kind === "CUT")) assert.equal(c.feedPerRev, pitch);
  assert.ok(r.ok && r.toolpath.rigidTapCycle === true);
});

test("a tap refuses without a pitch, without a hole, and under CSS", () => {
  const noPitch = tapToolpath(tapOp(), null);
  assert.equal(noPitch.ok, false);
  assert.ok(!noPitch.ok && /will not invent one/i.test(noPitch.reason));

  const noHole = tapToolpath(tapOp({ startDiameter: 0 }), 0.05);
  assert.equal(noHole.ok, false);
  assert.ok(!noHole.ok && /drilled hole/i.test(noHole.reason));

  // The cycle owns the spindle; CSS mid-tap breaks the synchronisation.
  const css = tapToolpath(tapOp({ params: { ...tapOp().params, cssEnabled: true } }), 0.05);
  assert.equal(css.ok, false);
  assert.ok(!css.ok && /CSS/i.test(css.reason));
});

test("the tap's spindle cap survives into the toolpath the post reads", () => {
  // The engine capping rpm means nothing if the post reads params.rpm — the
  // override must travel with the toolpath to the one place it matters.
  const fast = tapToolpath(tapOp({ params: { ...tapOp().params, rpm: 3000 } }), 0.05);
  assert.equal(fast.ok, true);
  if (!fast.ok) return;
  assert.equal(fast.toolpath.spindleRpmOverride, 600);
  assert.ok(fast.toolpath.warnings.some((w) => /capped at 600 RPM/i.test(w)));
});

test("the lathe post emits the tap as a canned cycle that owns the spindle", () => {
  const r = tapToolpath(tapOp(), 0.05);
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const { code, refusals } = emitLatheProgram(
    [{ toolpath: r.toolpath, station: "0909", description: "Tap 1/4-20", cssEnabled: false, surfaceSpeed: null, rpm: 400, coolant: true }],
    { programNumber: "2002", partName: "x", machine: "lathe", workOffset: "G54", maxRpmClamp: null, generatedAtIso: "2026-08-23" },
  );
  assert.equal(refusals.length, 0, refusals.join(" | "));
  const lines = code.split("\n");
  const g84 = lines.findIndex((l) => /^G84 /.test(l));
  assert.ok(g84 > 0, "no G84 emitted");
  assert.match(lines[g84], /F0\.0500/, "the cycle's feed word must be the pitch");
  assert.match(lines[g84 - 1], /^M29 S400$/, "M29 arms rigid mode with the tap rpm");
  assert.equal(lines[g84 + 1], "G80", "the cycle must be closed");
  // G84 owns the spindle: no M3 before it, and no G1 stand-in moves leak out.
  const opBlock = lines.slice(lines.findIndex((l) => l.includes("TAP 1/4-20")), g84 + 2);
  assert.ok(!opBlock.some((l) => /M3\b/.test(l)), `M3 in the tap block: ${opBlock.join(" / ")}`);
  assert.ok(!opBlock.some((l) => /^G1 /.test(l)), "stand-in feed moves leaked into the program");
});

test("the post prefers the engine's capped rpm over the plan's", () => {
  const fast = tapToolpath(tapOp({ params: { ...tapOp().params, rpm: 3000 } }), 0.05);
  assert.equal(fast.ok, true);
  if (!fast.ok) return;
  const { code } = emitLatheProgram(
    [{ toolpath: fast.toolpath, station: "0909", description: "Tap", cssEnabled: false, surfaceSpeed: null, rpm: 3000, coolant: false }],
    { programNumber: "2002", partName: "x", machine: "lathe", workOffset: "G54", maxRpmClamp: null, generatedAtIso: "2026-08-23" },
  );
  assert.match(code, /M29 S600\b/, "the post must carry the tapping cap, not the plan's 3000");
});

const reamOp = (over: Partial<TurnOperation> = {}) =>
  op({
    type: "REAM", label: "ream", startZ: 0, endZ: -0.75, startDiameter: 0.4925, endDiameter: 0.5,
    params: { ...op({}).params, cssEnabled: false, rpm: 300, feedPerRev: 0.006 },
    ...over,
  });

test("a reamer follows a hole and comes out at feed, never at rapid", () => {
  const r = reamToolpath(reamOp(), null);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  const moves = r.toolpath.moves;
  // The move back out of the hole is a CUT at feed: a rapid out of a reamed
  // hole drags a spiral scratch down the finish the reamer exists to make.
  const out = moves[moves.length - 1];
  assert.equal(out.kind, "CUT");
  assert.equal(out.feedPerRev, 0.006);
  assert.ok(out.z > moves[moves.length - 2].z, "the last move must come back out");
});

test("reaming stock is bounded on both sides, by name", () => {
  // Too little: the reamer burnishes and the hole comes out glassy/undersize.
  const skim = reamToolpath(reamOp({ startDiameter: 0.499 }), null);
  assert.equal(skim.ok, false);
  assert.ok(!skim.ok && /burnish/i.test(skim.reason), skim.ok ? "" : skim.reason);
  // Too much: that is a drilling cut, and the hole comes out oversize.
  const hog = reamToolpath(reamOp({ startDiameter: 0.46 }), null);
  assert.equal(hog.ok, false);
  assert.ok(!hog.ok && /drilling cut/i.test(hog.reason), hog.ok ? "" : hog.reason);
  // No hole at all, or a "ream" that removes nothing.
  assert.equal(reamToolpath(reamOp({ startDiameter: 0 }), null).ok, false);
  assert.equal(reamToolpath(reamOp({ startDiameter: 0.5 }), null).ok, false);
  // The window itself is sane.
  assert.ok(REAM_MIN_STOCK > 0 && REAM_MAX_STOCK > REAM_MIN_STOCK);
});

test("generateTurnToolpath routes tap and ream, with the pitch from context", () => {
  const profile = {
    units: "IN" as const, zZeroReference: "front face", stockDiameter: 2, stockLength: 4,
    barStock: true, segments: [],
  };
  assert.equal(generateTurnToolpath(tapOp(), profile, { pitchIn: 0.05 }).ok, true);
  assert.equal(generateTurnToolpath(tapOp(), profile, {}).ok, false);
  assert.equal(generateTurnToolpath(reamOp(), profile, {}).ok, true);
});

/* ------------------------------------------------------------------ */
/* ID grooving and threading                                           */
/* ------------------------------------------------------------------ */

const idGroove = (over: Partial<TurnOperation> = {}) =>
  op({
    type: "GROOVE_ID", label: "o-ring groove", startZ: 0.4, endZ: 0.55, startDiameter: 1.0, endDiameter: 1.12,
    params: { ...op({}).params, cssEnabled: false, rpm: 800, feedPerRev: 0.003 },
    ...over,
  });

const idThread = (over: Partial<TurnOperation> = {}) =>
  op({
    type: "THREAD_ID", label: "thread 1-1/4-12 int", startZ: 0, endZ: 0.6, startDiameter: 1.16, endDiameter: 1.25,
    params: { ...op({}).params, cssEnabled: false, rpm: 500, feedPerRev: 0.0833 },
    ...over,
  });

test("every ID operation asks whether the tool fits the hole before anything else", () => {
  // minBoreDiameter is the tool record's own answer, and an unrecorded one
  // is a refusal — "does it fit" is not a question CANVAS guesses at.
  for (const [name, r] of [
    ["groove unrecorded", grooveIdToolpath(idGroove(), 0.15, 0.125, null)],
    ["groove too small", grooveIdToolpath(idGroove(), 0.15, 0.125, 1.1)],
    ["thread unrecorded", threadIdToolpath(idThread(), 1 / 12, null)],
    ["thread too small", threadIdToolpath(idThread(), 1 / 12, 1.5)],
    ["groove no bore", grooveIdToolpath(idGroove({ startDiameter: 0 }), 0.15, 0.125, 0.9)],
  ] as const) {
    assert.equal(r.ok, false, name);
    assert.ok(!r.ok && /(fits? the hole|needs a ⌀|no bore recorded)/i.test(r.reason), `${name}: ${r.ok ? "" : r.reason}`);
  }
});

test("an ID groove plunges OUTWARD and every retract is inward — outward is the groove it just cut", () => {
  const r = grooveIdToolpath(idGroove(), 0.15, 0.125, 0.9);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  const moves = r.toolpath.moves;
  // The groove root is reached, and nothing exceeds it.
  assert.ok(moves.some((m) => m.kind === "CUT" && Math.abs(m.x - 1.12) < 1e-9), "groove root never reached");
  assert.ok(Math.max(...moves.map((m) => m.x)) <= 1.12 + 1e-9);
  // Boring's law: any move that changes Z happens at or below the clear
  // diameter, which sits INSIDE the bore surface.
  const clear = 1.0 - 2 * 0.06;
  for (let i = 1; i < moves.length; i++) {
    if (moves[i].z !== moves[i - 1].z) {
      // BOTH ends of any Z-changing move must sit at or inside the clear
      // diameter. Checking only the destination lets a diagonal rapid from
      // the groove root pass — it ends clear, and sweeps through the
      // shoulder on the way. (A mutation survived exactly there.)
      assert.ok(moves[i].x <= clear + 1e-9, `Z moved to ⌀${moves[i].x} — inside a ⌀1.0 bore that is a crash`);
      assert.ok(moves[i - 1].x <= clear + 1e-9, `Z move began at ⌀${moves[i - 1].x} — dragging across the groove`);
    }
  }
});

test("an internal groove that does not open outward removes nothing and says so", () => {
  const r = grooveIdToolpath(idGroove({ endDiameter: 0.95 }), 0.15, 0.125, 0.9);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /opens outward/i.test(r.reason), r.ok ? "" : r.reason);
});

test("an ID groove narrower than the insert is refused, same as the OD case", () => {
  const r = grooveIdToolpath(idGroove(), 0.1, 0.125, 0.9);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /narrower than/i.test(r.reason));
  assert.equal(grooveIdToolpath(idGroove(), 0.15, 0, 0.9).ok, false);
});

test("ID thread passes open outward from the bore at pitch feed, shallower than the external form", () => {
  const pitch = 1 / 12;
  const r = threadIdToolpath(idThread(), pitch, 1.0);
  assert.equal(r.ok, true, r.ok ? "" : r.reason);
  if (!r.ok) return;
  const tp = r.toolpath.moves.filter((m) => m.kind === "THREAD_PASS");
  assert.ok(tp.length >= 2);
  for (const m of tp) assert.equal(m.feedPerRev, pitch, "a thread's feed is its pitch");
  // Successive passes sit at LARGER diameters — the mirror of the OD thread.
  for (let i = 1; i < tp.length; i++) assert.ok(tp[i].x > tp[i - 1].x, "passes must open outward");
  // The last pass reaches the internal form depth: minor + 2 × 0.5413 × pitch,
  // NOT the external 0.6134 — the internal crest is truncated (5/8H).
  const finalD = tp[tp.length - 1].x;
  assert.ok(Math.abs(finalD - (1.16 + 2 * 0.5413 * pitch)) < 1e-6, `final pass ⌀${finalD}`);
  assert.ok(finalD < 1.16 + 2 * 0.6134 * pitch, "internal depth must be shallower than the external form");
});

test("between ID thread passes the tool leaves along the clear diameter, never across the thread", () => {
  const r = threadIdToolpath(idThread(), 1 / 12, 1.0);
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const moves = r.toolpath.moves;
  const clear = 1.16 - 2 * 0.06;
  for (let i = 1; i < moves.length; i++) {
    if (moves[i].z !== moves[i - 1].z && moves[i].kind !== "THREAD_PASS") {
      assert.ok(moves[i].x <= clear + 1e-9, `retract crossed the thread at ⌀${moves[i].x}`);
    }
  }
  assert.ok(r.toolpath.assumptions.some((a) => /never retimed/.test(a)));
  assert.ok(r.toolpath.assumptions.some((a) => /G97/.test(a)));
});

test("generateTurnToolpath routes the ID pair with the tool record's own fit answer", () => {
  const profile = {
    units: "IN" as const, zZeroReference: "front face", stockDiameter: 2, stockLength: 4,
    barStock: true, segments: [],
  };
  assert.equal(generateTurnToolpath(idGroove(), profile, { toolWidth: 0.125, minBoreDiameter: 0.9 }).ok, true);
  assert.equal(generateTurnToolpath(idGroove(), profile, { toolWidth: 0.125 }).ok, false);
  assert.equal(generateTurnToolpath(idThread(), profile, { pitchIn: 1 / 12, minBoreDiameter: 1.0 }).ok, true);
  assert.equal(generateTurnToolpath(idThread(), profile, { pitchIn: 1 / 12 }).ok, false);
});

test("a zero-length OD thread is refused, matching the ID rule", () => {
  const r = threadToolpath(op({ type: "THREAD_OD", startZ: 0.5, endZ: 0.5 }), 0.0625);
  assert.equal(r.ok, false);
  assert.ok(!r.ok && /zero-length thread/i.test(r.reason));
});
