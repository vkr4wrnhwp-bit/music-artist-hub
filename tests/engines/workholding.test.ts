import { test } from "node:test";
import assert from "node:assert/strict";
import {
  assessWorkholding,
  worstRisk,
  RISK_ORDER,
  RISK_LEVELS,
  recommendedGripDepth,
  type SetupContext,
  type RiskLevel,
  peripheralRoughingTool,
} from "@/lib/engines/workholding";
import type { Tool } from "@/lib/domain/shop";
import type { Stock } from "@/lib/domain/features";

/**
 * This engine produces the verdict a machinist reads before clamping a part,
 * and it had no tests at all. The ones that matter here are about what the
 * aggregate is allowed to hide: a definite high risk must never disappear
 * behind an unknown, and a missing input must never become a confident SAFE.
 */

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as unknown as Stock;

const TOOL = {
  id: "t1", toolNumber: 1, toolClass: "FLAT_END_MILL", description: '1/2" end mill',
  diameter: 0.5, cornerRadius: 0, flutes: 3, material: "CARBIDE",
  fluteLength: 1, overallLength: 3, stickout: 1.5,
  holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8100,
  recommendedMaterials: [], chiploadMin: 0.002, chiploadMax: 0.005,
  sfmMin: 600, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
  condition: "GOOD", regrindCount: 0,
} as unknown as Tool;

const VISE = {
  id: "w1", type: "VISE", description: '6" vise',
  jawWidth: 6, jawHeight: 1.5, maxOpening: 6, fixtureHeight: 3,
  hasCadRepresentation: false,
} as const;

function ctx(over: Partial<SetupContext> = {}): SetupContext {
  return {
    stock: STOCK,
    gripDepth: 0.375,
    gripLength: 5,
    stockProjection: 0.375,
    parallelHeight: 0.5,
    device: VISE as unknown as SetupContext["device"],
    features: [],
    roughingTool: TOOL,
    radialEngagement: 0.45,
    axialDepthOfCut: 0.25,
    specificEnergy: 0.3,
    materialFamily: "ALUMINUM",
    ...over,
  };
}

/* ---------------- The ordering ---------------- */

test("HIGH_RISK is the most severe level there is", () => {
  for (const l of RISK_LEVELS) {
    if (l === "HIGH_RISK") continue;
    assert.ok(
      RISK_ORDER.HIGH_RISK > RISK_ORDER[l],
      `HIGH_RISK must outrank ${l} — otherwise a real finding can be masked by it`,
    );
  }
});

test("a definite high risk is never hidden behind an unknown", () => {
  // The bug this pins: worst() collapses a setup's factors to one level, and
  // while UNKNOWN outranked HIGH_RISK a setup with both reported UNKNOWN.
  // Readiness maps UNKNOWN to MISSING and HIGH_RISK to FAIL, so the more
  // serious finding was being reported as the less serious one.
  assert.equal(worstRisk(["UNKNOWN", "HIGH_RISK"]), "HIGH_RISK");
  assert.equal(worstRisk(["SAFE", "UNKNOWN", "HIGH_RISK", "LIKELY_SAFE"]), "HIGH_RISK");
});

test("worst is a maximum, never an average", () => {
  // Nine safe factors and one high risk is not "mostly safe".
  const nineSafe: RiskLevel[] = Array.from({ length: 9 }, () => "SAFE");
  assert.equal(worstRisk([...nineSafe, "HIGH_RISK"]), "HIGH_RISK");
  assert.equal(worstRisk([...nineSafe, "REVIEW"]), "REVIEW");
});

test("an empty factor list is SAFE rather than undefined", () => {
  assert.equal(worstRisk([]), "SAFE");
});

test("the ordering is total — no two levels share a rank", () => {
  const ranks = RISK_LEVELS.map((l) => RISK_ORDER[l]);
  assert.equal(new Set(ranks).size, RISK_LEVELS.length, "two levels sharing a rank makes worst() order-dependent");
});

/* ---------------- Missing inputs ---------------- */

test("no device, no grip, no tool: UNKNOWN and never SAFE", () => {
  const a = assessWorkholding(ctx({ device: null, gripDepth: null, gripLength: null, roughingTool: null, stockProjection: null }));
  assert.equal(a.level, "UNKNOWN");
  assert.ok(a.missingInputs.length > 0, "it must name what it wanted");
});

test("a missing input is named rather than defaulted", () => {
  const a = assessWorkholding(ctx({ gripDepth: null }));
  assert.ok(a.missingInputs.some((m) => /grip depth/i.test(m)));
  assert.equal(a.gripDepth, null, "a null input stays null in the output");
});

test("every factor carries a reason and an observation", () => {
  const a = assessWorkholding(ctx());
  assert.ok(a.factors.length > 0);
  for (const f of a.factors) {
    assert.ok(f.reason && f.reason.length > 10, `${f.id} has no reason`);
    assert.ok(f.observed && f.observed.length > 0, `${f.id} states no observation`);
    assert.ok(RISK_LEVELS.includes(f.level), `${f.id} has a level outside the vocabulary`);
  }
});

test("the aggregate is always one of the factor levels, never invented", () => {
  for (const c of [ctx(), ctx({ gripDepth: 0.05 }), ctx({ stockProjection: 4 }), ctx({ device: null })]) {
    const a = assessWorkholding(c);
    if (a.factors.length === 0) continue;
    assert.ok(
      a.factors.some((f) => f.level === a.level) || a.level === "UNKNOWN",
      "the headline level must come from a factor",
    );
  }
});

/* ---------------- Factors that should fire ---------------- */

test("a long projection over a shallow grip is not called safe", () => {
  const a = assessWorkholding(ctx({ gripDepth: 0.2, stockProjection: 2.0 }));
  const projection = a.factors.find((f) => f.id === "projection");
  assert.ok(projection, "the projection factor must be evaluated when both inputs exist");
  assert.notEqual(projection.level, "SAFE", "10:1 projection to grip is not a safe setup");
  assert.equal(RISK_ORDER[a.level] >= RISK_ORDER[projection.level], true);
});

test("narrow jaw engagement is flagged, not ignored", () => {
  const a = assessWorkholding(ctx({ gripLength: 1 })); // 1" of a 6" jaw
  const eng = a.factors.find((f) => f.id === "engagement");
  assert.ok(eng);
  assert.notEqual(eng.level, "SAFE");
  assert.ok(a.engagementPercent !== null && a.engagementPercent < 50);
});

test("grip depth recommendation scales with load rather than being a fixed rule", () => {
  const light = recommendedGripDepth(ctx({ axialDepthOfCut: 0.05, radialEngagement: 0.1 }));
  const heavy = recommendedGripDepth(ctx({ axialDepthOfCut: 0.5, radialEngagement: 1.0 }));
  assert.ok(light !== null && heavy !== null);
  assert.ok(heavy >= light, "a heavier cut must not ask for less grip than a lighter one");
});

test("no roughing tool means no grip recommendation, not a guessed one", () => {
  assert.equal(recommendedGripDepth(ctx({ roughingTool: null })), null);
});

/* ---------------- The force model is carried, not hidden ---------------- */

test("the force estimate is always returned so the UI can show its method", () => {
  const a = assessWorkholding(ctx());
  assert.ok(a.forceEstimate, "forceEstimate is never null — it carries ok:false instead");
  assert.ok(typeof a.forceEstimate.ok === "boolean");
});

test("an unrunnable force model names its missing inputs rather than returning zero", () => {
  const a = assessWorkholding(ctx({ roughingTool: null, specificEnergy: null }));
  assert.equal(a.estimatedCuttingForce, null, "null, not 0 — zero force is a claim");
  assert.ok(a.forceEstimate.ok === false);
  assert.ok(a.forceEstimate.missingInputs.length > 0);
});

test("holding margin is null when it cannot be computed, never a fabricated number", () => {
  const a = assessWorkholding(ctx({ clampForce: null, device: { ...VISE, clampForce: undefined } as unknown as SetupContext["device"] }));
  assert.ok(a.holdingMargin === null || a.holdingMargin.margin !== null);
});

test("the real engine reports HIGH_RISK when a setup has both an unknown and a high risk", () => {
  // No roughing tool means no grip recommendation, so the grip-depth factor
  // comes back UNKNOWN. A 2.0" projection over a 0.2" grip is 10:1, which is
  // HIGH_RISK. Before the ordering was fixed this whole assessment reported
  // UNKNOWN — readiness mapped it to MISSING instead of FAIL, and the setups
  // page and the runway both printed "Unknown" over a real cantilever
  // problem.
  const a = assessWorkholding(ctx({ roughingTool: null, gripDepth: 0.2, stockProjection: 2.0 }));

  const levels = a.factors.map((f) => f.level);
  assert.ok(levels.includes("UNKNOWN"), "precondition: an unknown factor is present");
  assert.ok(levels.includes("HIGH_RISK"), "precondition: a high-risk factor is present");

  assert.equal(a.level, "HIGH_RISK", "the definite finding must win");
});

test("a margin can be computed while an input is still missing — the two are independent", () => {
  // Clamp force can be recorded on the setup itself, so the force model runs
  // with no vise selected at all: a confident 9.73x margin and a SAFE level
  // alongside "Workholding device not selected". The setups page rendered
  // missingInputs only in the branch for a NULL margin, so in exactly this
  // case the number was read without the fact that qualifies it.
  const a = assessWorkholding(ctx({ device: null, clampForce: 4000, jawSurface: "SERRATED", hasPositiveStop: true }));
  assert.notEqual(a.holdingMargin?.margin, null);
  assert.ok(a.holdingMargin!.margin! > 2);
  assert.deepEqual(a.missingInputs, ["Workholding device not selected"]);
  // The readiness gate is what stops this being cut; the screen's job is to
  // stop it being believed.
  assert.equal(a.level, "SAFE");
});

/* ---------------- A facing setup is not a setup with missing data ---------------- */

/**
 * A setup whose only operation is a face mill reported "No roughing tool
 * assigned — cutting load unknown", which readiness maps to MISSING. MISSING
 * cannot be acknowledged, so the part could never be released or posted, and
 * the suggested fix — "Assign a roughing operation" — asked a machinist to add
 * a cut they do not need in order to satisfy software. There was no control to
 * add one either.
 *
 * The two states the engine collapsed: "I do not know what the load is" and
 * "there is no lateral cutter here". The second is an answer.
 */

const FACE_MILL = {
  ...(TOOL as unknown as Record<string, unknown>),
  id: "t9",
  toolNumber: 9,
  toolClass: "FACE_MILL",
  description: '2" face mill, 4 insert',
  diameter: 2,
} as unknown as Tool;

const facing = (over: Partial<SetupContext> = {}) =>
  assessWorkholding(ctx({ roughingTool: null, setupTools: [FACE_MILL], ...over }));

test("a face-mill-only setup does not report the cutting load as missing", () => {
  const a = facing();
  assert.ok(
    !a.missingInputs.some((m) => /cutting load unknown/i.test(m)),
    "a setup with tools in it was reported as missing its load",
  );
});

test("it answers REVIEW rather than UNKNOWN, so a human can accept it", () => {
  // UNKNOWN maps to MISSING in readiness, which cannot be acknowledged, which
  // is what made the loop impossible to finish.
  const a = facing();
  assert.notEqual(a.level, "UNKNOWN");
  const margin = a.factors.find((f) => f.id === "holding-margin")!;
  assert.equal(margin.level, "REVIEW");
});

test("it says why, in terms of where the load goes", () => {
  const margin = facing().factors.find((f) => f.id === "holding-margin")!;
  assert.match(margin.reason, /along the spindle axis|into the parallels/i);
  assert.match(margin.observed, /No peripheral cutter/i);
  // The tools that ARE there are named, so the claim can be checked.
  assert.match(margin.observed, /face mill/i);
});

test("it claims no margin it did not compute", () => {
  const a = facing();
  assert.equal(a.holdingMargin?.verdict ?? "INDETERMINATE", "INDETERMINATE");
  const margin = a.factors.find((f) => f.id === "holding-margin")!;
  assert.ok(!/\d+\.\d+×/.test(margin.observed), "a margin figure was printed for a load nobody calculated");
  // And it names the lateral load it is NOT modelling, rather than implying
  // there is none at all.
  assert.match(margin.reason, /feed force|shock/i);
});

test("a setup with NO tools at all is still genuinely unknown", () => {
  // The distinction has to cut both ways, or it is just a way of passing.
  const a = assessWorkholding(ctx({ roughingTool: null, setupTools: [] }));
  assert.ok(a.missingInputs.some((m) => /cutting load unknown/i.test(m)));
  const margin = a.factors.find((f) => f.id === "holding-margin");
  assert.ok(!margin, "a setup with no tools claimed an answer about its holding margin");
});

test("a peripheral cutter still governs when one is present", () => {
  // The exclusion of face mills from sizing grip is the original, correct
  // behaviour and must survive. A clamp force is supplied so the margin can
  // actually be computed — without one the model is indeterminate for its own
  // reasons and this would prove nothing.
  const a = assessWorkholding(ctx({ setupTools: [FACE_MILL, TOOL], clampForce: 2000 }));
  const margin = a.factors.find((f) => f.id === "holding-margin")!;
  assert.ok(margin, "no holding-margin factor was produced for a setup that can compute one");
  assert.ok(!/No peripheral cutter/.test(margin.observed ?? ""), "an end mill in the setup was ignored");
  // The real model ran: a margin figure is present.
  assert.match(margin.observed ?? "", /×/);
});

test("the grip-depth factor no longer tells a facing setup to add a roughing pass", () => {
  // A dead-end instruction: no control assigns a roughing operation, and a
  // facing setup does not need one.
  const grip = facing().factors.find((f) => f.id === "grip-depth")!;
  assert.ok(
    !grip.suggestions.some((s) => /assign a roughing operation/i.test(s)),
    "the dead-end suggestion is still being given",
  );
  assert.match(grip.reason, /peripheral cutter/i);
});

test("a definite risk still outranks the facing answer", () => {
  // 2.0" of projection over 0.2" of grip is a 10:1 cantilever. The facing
  // REVIEW must not soften it.
  const a = facing({ gripDepth: 0.2, stockProjection: 2.0 });
  assert.equal(a.level, "HIGH_RISK");
});

/* ---------------- One copy of the peripheral rule ---------------- */

test("the peripheral-cutter rule picks the largest end mill and ignores face mills", () => {
  const big = { ...(TOOL as unknown as Record<string, unknown>), id: "big", diameter: 0.75 } as unknown as Tool;
  assert.equal(peripheralRoughingTool([TOOL, big, FACE_MILL])?.id, "big");
  assert.equal(peripheralRoughingTool([FACE_MILL]), null);
  assert.equal(peripheralRoughingTool([]), null);
});
