import { test } from "node:test";
import assert from "node:assert/strict";
import {
  estimateCuttingForce,
  governingLateralLoad,
  materialCuttingData,
  TOOL_CONDITIONS,
  type CuttingForceInput,
} from "@/lib/engines/cutting-force";

/**
 * WHAT THESE TESTS DELIBERATELY DO NOT DO
 *
 * They do not assert magnitudes. This model is DEVELOPMENT ANALYSIS by its
 * own admission — it has not been validated against a dynamometer, and
 * writing `assert.equal(tangential, 93.7)` would pin today's output as though
 * it were a measured truth. The next person to improve the model would then
 * have to break a test to make it more accurate, which is exactly backwards.
 *
 * So what is pinned here is the part that must hold regardless of how the
 * arithmetic is tuned: that it refuses rather than guesses, that its
 * relationships are physically the right way round, and that the number the
 * workholding model divides by is never fabricated.
 *
 * Every consumer of this engine treats a null as "cannot say" and a number as
 * "this is the load". The dangerous failure is not an inaccurate number — it
 * is a confident one where there should be a null.
 */

const base: CuttingForceInput = {
  materialFamily: "ALUMINUM",
  toolDiameter: 0.5,
  flutes: 3,
  axialDepth: 0.25,
  radialWidth: 0.225,
  chipload: 0.0035,
  rpm: 7000,
  toolCondition: "GOOD",
};

const run = (over: Partial<CuttingForceInput> = {}) => estimateCuttingForce({ ...base, ...over });

/* ---------------- Refusal ---------------- */

test("with nothing supplied it refuses and names every input it wanted", () => {
  const e = estimateCuttingForce({
    materialFamily: null, toolDiameter: null, flutes: null, axialDepth: null,
    radialWidth: null, chipload: null, rpm: null, toolCondition: "UNKNOWN",
  });
  assert.equal(e.ok, false);
  assert.equal(e.tangential, null, "null, not 0 — zero force is a claim, and a false one");
  assert.equal(e.peakTangential, null);
  assert.equal(e.spindlePower, null);
  assert.ok(e.missingInputs.length > 0);
});

test("one missing input is enough to refuse, and it names that input specifically", () => {
  // The first version of this fell back to `|| missingInputs.length > 0`,
  // which would have passed on any message at all — including one naming the
  // wrong field. An operator acts on the name, so the name is the assertion.
  const expected: [keyof CuttingForceInput, RegExp][] = [
    ["toolDiameter", /tool diameter/i],
    ["flutes", /flute count/i],
    ["axialDepth", /axial depth/i],
    ["chipload", /chip ?load|feed per tooth/i],
    ["rpm", /spindle speed/i],
    ["materialFamily", /material/i],
  ];
  for (const [k, pattern] of expected) {
    const e = run({ [k]: null } as Partial<CuttingForceInput>);
    assert.equal(e.ok, false, `${k} missing should refuse`);
    assert.equal(e.tangential, null, `${k} missing must not produce a force`);
    assert.ok(
      e.missingInputs.some((m) => pattern.test(m)),
      `${k} missing should be named; got [${e.missingInputs.join(" | ")}]`,
    );
  }
});

test("an unrecognised material is a missing input, not a silent default", () => {
  const e = run({ materialFamily: "UNOBTAINIUM" });
  assert.ok(!e.ok || e.materialData === null, "an unknown material must not resolve to a table row");
  if (!e.ok) assert.ok(e.missingInputs.length > 0);
});

test("materialCuttingData returns null rather than a fallback row", () => {
  assert.equal(materialCuttingData(null), null);
  assert.equal(materialCuttingData("NOT_A_REAL_FAMILY"), null);
});

/* ---------------- The number workholding divides by ---------------- */

test("governingLateralLoad is null whenever the model did not run", () => {
  // holding-margin.ts divides by this. A fabricated number here becomes a
  // fabricated safety margin, which is the worst outcome in the codebase.
  const e = estimateCuttingForce({
    materialFamily: null, toolDiameter: null, flutes: null, axialDepth: null,
    radialWidth: null, chipload: null, rpm: null, toolCondition: "UNKNOWN",
  });
  assert.equal(governingLateralLoad(e), null);
});

test("the governing lateral load is at least the peak tangential", () => {
  // It is the resultant of peak tangential and the radial component scaled to
  // the same instant, so it cannot be smaller than either.
  const e = run();
  const g = governingLateralLoad(e);
  assert.ok(g !== null && e.peakTangential !== null);
  assert.ok(g >= e.peakTangential, "the resultant cannot be below one of its components");
});

test("peak tangential is strictly above the average on an interrupted cut", () => {
  // `>=` was the first version of this and it is too weak: dropping the peak
  // factor entirely and reporting the average twice would satisfy it, and the
  // workholding model would then be sized against the mean load. The engine's
  // own comment says peak is "what the workholding actually has to survive,
  // not the average", so on a partial-immersion cut the two must differ.
  const e = run({ radialWidth: 0.225 }); // 45% immersion — under one tooth engaged
  assert.ok(e.tangential !== null && e.peakTangential !== null);
  assert.ok(
    e.peakTangential > e.tangential,
    `peak (${e.peakTangential}) must exceed average (${e.tangential}) when the cut is interrupted`,
  );
});

/* ---------------- Physical direction ---------------- */

test("more axial depth means more force", () => {
  const light = run({ axialDepth: 0.05 });
  const heavy = run({ axialDepth: 0.5 });
  assert.ok(light.tangential !== null && heavy.tangential !== null);
  assert.ok(heavy.tangential > light.tangential);
});

test("more radial width means more force", () => {
  const light = run({ radialWidth: 0.05 });
  const heavy = run({ radialWidth: 0.4 });
  assert.ok(light.tangential !== null && heavy.tangential !== null);
  assert.ok(heavy.tangential > light.tangential);
});

test("more feed per tooth means more force", () => {
  const light = run({ chipload: 0.001 });
  const heavy = run({ chipload: 0.006 });
  assert.ok(light.tangential !== null && heavy.tangential !== null);
  assert.ok(heavy.tangential > light.tangential);
});

test("a worn tool pulls harder than a new one, and unknown is not treated as new", () => {
  const asNew = run({ toolCondition: "NEW" });
  const worn = run({ toolCondition: "WORN" });
  const unknown = run({ toolCondition: "UNKNOWN" });
  assert.ok(asNew.tangential !== null && worn.tangential !== null && unknown.tangential !== null);
  assert.ok(worn.tangential > asNew.tangential, "a dull edge ploughs rather than cuts");
  assert.ok(
    unknown.tangential > asNew.tangential,
    "an unrecorded condition must not be optimistically treated as a fresh edge",
  );
});

test("every tool condition runs and none produces a negative force", () => {
  for (const c of TOOL_CONDITIONS) {
    const e = run({ toolCondition: c });
    assert.equal(e.ok, true, `${c} should still compute`);
    for (const v of [e.tangential, e.radial, e.axial, e.resultant, e.peakTangential, e.spindlePower]) {
      if (v !== null) assert.ok(v >= 0, `${c} produced a negative ${v}`);
    }
  }
});

test("removal rate and spindle power move together", () => {
  const light = run({ axialDepth: 0.05, radialWidth: 0.05 });
  const heavy = run({ axialDepth: 0.5, radialWidth: 0.4 });
  assert.ok(light.materialRemovalRate !== null && heavy.materialRemovalRate !== null);
  assert.ok(heavy.materialRemovalRate > light.materialRemovalRate);
  assert.ok(light.spindlePower !== null && heavy.spindlePower !== null);
  assert.ok(heavy.spindlePower > light.spindlePower, "more metal per minute cannot take less power");
});

/* ---------------- What it admits ---------------- */

test("a successful estimate always carries its uncertainty and method", () => {
  const e = run();
  assert.equal(e.ok, true);
  assert.ok(e.uncertaintyPercent !== null && e.uncertaintyPercent > 0, "a band of zero would claim exactness");
  assert.ok(e.method && e.method.length > 0);
  assert.ok(e.inputs.length > 0, "the inputs must be traceable for show-calculation");
});

test("an interrupted cut says peak governs rather than reporting the mean quietly", () => {
  // Light radial engagement means less than one tooth is in the cut at any
  // instant, and the average badly understates what the part feels.
  const e = run({ radialWidth: 0.05 });
  assert.ok(e.cautions.some((c) => /interrupted|peak/i.test(c)));
});

test("a radial width wider than the cutter is cautioned, not silently accepted", () => {
  const e = run({ radialWidth: 0.9 });
  assert.ok(
    e.cautions.some((c) => /exceeds|slot/i.test(c)),
    "a trench wider than the tool is more than one pass and the model must say so",
  );
});

test("the estimate is deterministic — the same inputs give the same answer", () => {
  assert.deepEqual(run(), run());
});
