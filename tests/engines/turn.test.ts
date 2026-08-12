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
