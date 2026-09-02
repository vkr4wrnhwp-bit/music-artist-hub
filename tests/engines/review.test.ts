import { test } from "node:test";
import assert from "node:assert/strict";
import { reviewPackage, SEVERITIES, type ReviewInput } from "@/lib/engines/review";
import type { Move } from "@/lib/engines/cam/types";

/**
 * This is the last thing a machinist reads before Cycle Start, so the failure
 * that matters most is not a missing finding — it is a CLEAN result on a
 * program that would crash. A pre-flight that reports nothing is read as
 * permission, and the jaw-clearance check was reporting nothing on exactly
 * the program it exists to catch.
 *
 * Part coordinates throughout: Z=0 is the top of the stock, cuts run
 * negative, clearance and retract planes are positive. The part is seated on
 * parallels, so grip depth plus what stands proud of the jaws is the stock
 * height, and the jaw line therefore sits at -stockProjection.
 */

const rapid = (x: number, y: number, z: number): Move =>
  ({ type: "RAPID", x, y, z, feed: null }) as Move;
const cut = (x: number, y: number, z: number): Move =>
  ({ type: "CUT", x, y, z, feed: 30 }) as Move;

const VISE = { id: "w1", type: "VISE", description: '6" vise', jawWidth: 6, jawHeight: 1.5, maxOpening: 6, fixtureHeight: 3 };

const TOOL = {
  id: "t1", toolNumber: 1, description: '1/2" end mill', toolClass: "FLAT_END_MILL",
  diameter: 0.5, fluteLength: 1.0, overallLength: 3, stickout: 1.5, holderNoseDiameter: 1.5,
  flutes: 3, material: "CARBIDE", maxRPM: 8100,
};

const input = (over: Partial<ReviewInput> = {}): ReviewInput =>
  ({
    setups: [
      {
        id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375,
        operations: [{ id: "o1", label: "Rough pocket", toolId: "t1", finalZ: -0.125, type: "POCKET_2D" }],
      },
    ],
    workholdingBySetup: {},
    device: VISE,
    machine: null,
    tools: [TOOL],
    movesByOperation: {},
    capability: [],
    stockZ: 0.75,
    ...over,
  }) as unknown as ReviewInput;

const jawFinding = (r: ReturnType<typeof reviewPackage>) =>
  r.findings.find((f) => /vise jaw/i.test(f.title));

/* ---------------- The jaw-clearance check, which was inverted ---------------- */

test("a lateral rapid below the top of the jaws is caught", () => {
  // THE case this check exists for. Grip 0.375 of a 0.750 part means the jaw
  // line is 0.375 below the top of the stock. A clearance plane at -0.5 with
  // the tool traversing in XY is a rapid straight through the vise jaw.
  //
  // The old arithmetic — jawTop - (jawTop - grip) — cancelled to the grip
  // depth, a POSITIVE number in the air above the part, and a further
  // `m.z <= 0` guard excluded everything at or below the stock top. The check
  // could only fire in clear air and never at jaw level: it reported this
  // program clean.
  const r = reviewPackage(
    input({ movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] } }),
  );
  const f = jawFinding(r);
  assert.ok(f, `the wreck must be caught; got [${r.findings.map((x) => x.title).join(" | ")}]`);
  assert.equal(f.severity, "HIGH");
  assert.equal(f.location.point?.z, -0.5, "SHOW ME must point at the offending move");
});

test("the jaw line is taken from how the part is seated, not from the grip depth alone", () => {
  const r = reviewPackage(
    input({ movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] } }),
  );
  const jawTop = jawFinding(r)!.evidence.find((e) => /jaw top/i.test(e.label));
  assert.ok(jawTop);
  assert.equal(jawTop.value, '-0.375"', "the jaw line is below the top of the stock, not above it");
});

test("a rapid at a normal clearance plane is not flagged", () => {
  // The schema default clearance plane is +0.25. If this fires, every program
  // in the shop produces a HIGH finding and the whole review gets ignored.
  const r = reviewPackage(
    input({ movesByOperation: { o1: [rapid(0, 0, 0.25), rapid(3, 0, 0.25), rapid(3, 2, 1.0)] } }),
  );
  assert.equal(jawFinding(r), undefined, "a correct program must come back clean");
});

test("a plunge straight down past the jaw line is not flagged", () => {
  // Every drilling operation rapids down to just above the feature. That move
  // is below the jaw top by design and is directly over the hole. Flagging it
  // produces a page of findings a machinist dismisses in ten seconds.
  const r = reviewPackage(
    input({ movesByOperation: { o1: [rapid(1, 1, 0.25), rapid(1, 1, -0.6)] } }),
  );
  assert.equal(jawFinding(r), undefined, "a plunge over a feature is normal");
});

test("a small lateral shuffle at depth is not flagged, a real traverse is", () => {
  const shuffle = reviewPackage(input({ movesByOperation: { o1: [rapid(1, 1, -0.6), rapid(1.01, 1, -0.6)] } }));
  assert.equal(jawFinding(shuffle), undefined, "0.010 of drift is not a traverse");
  const traverse = reviewPackage(input({ movesByOperation: { o1: [rapid(1, 1, -0.6), rapid(1.5, 1, -0.6)] } }));
  assert.ok(jawFinding(traverse), "half an inch sideways at jaw depth is");
});

test("a cutting move below the jaw line is not a rapid and is not flagged", () => {
  // Feed moves down there are the operation doing its job.
  const r = reviewPackage(input({ movesByOperation: { o1: [cut(0, 0, -0.6), cut(3, 0, -0.6)] } }));
  assert.equal(jawFinding(r), undefined);
});

test("the first move of an operation cannot be judged and is not flagged", () => {
  const r = reviewPackage(input({ movesByOperation: { o1: [rapid(3, 3, -0.6)] } }));
  assert.equal(jawFinding(r), undefined, "with no previous move there is no lateral distance");
});

test("with no grip depth and no projection the check is skipped, not defaulted", () => {
  // Defaulting to zero puts the jaw line at the top of the stock, which
  // silently passes every program ever written.
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: null, stockProjection: null, operations: [{ id: "o1", label: "Rough pocket", toolId: "t1", finalZ: -0.125, type: "POCKET_2D" }] }],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
    } as unknown as Partial<ReviewInput>),
  );
  assert.equal(jawFinding(r), undefined);
  assert.ok(
    r.checksSkipped.some((c) => /rapid clearance/i.test(c.check) && /grip depth|projection/i.test(c.reason)),
    `the skip must be declared; got [${r.checksSkipped.map((c) => c.check).join(" | ")}]`,
  );
});

test("grip depth alone is enough, because the stock height is known", () => {
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: null, operations: [{ id: "o1", label: "Rough pocket", toolId: "t1", finalZ: -0.125, type: "POCKET_2D" }] }],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
    } as unknown as Partial<ReviewInput>),
  );
  const f = jawFinding(r);
  assert.ok(f, "0.375 grip in 0.750 stock puts the jaw line at -0.375");
  // Asserting only that SOMETHING was flagged is not enough: a rapid at -0.5
  // trips a jaw line at +0.375 just as readily as one at -0.375, so the
  // finding survives the grip depth being used raw with the stock height
  // dropped. The computed line itself is the assertion.
  assert.equal(
    f.evidence.find((e) => /jaw top/i.test(e.label))?.value,
    '-0.375"',
    "grip depth is measured up from the bottom of the part, so the stock height has to come off it",
  );
});

test("no workholding device means the check is declared skipped", () => {
  const r = reviewPackage(input({ device: null, movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] } }));
  assert.equal(jawFinding(r), undefined);
  assert.ok(r.checksSkipped.some((c) => /rapid clearance near the jaws/i.test(c.check)));
  assert.ok(!r.checksRun.some((c) => /jaws/i.test(c)), "a skipped check must not be listed as run");
});

test("the check admits it does not know where the jaws are in XY", () => {
  const r = reviewPackage(input({ movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] } }));
  assert.ok(
    r.checksSkipped.some((c) => /jaw footprint|crosses the jaw/i.test(c.check + c.reason)),
    "a move well clear of the vise is still flagged, and that must be stated",
  );
  assert.match(jawFinding(r)!.method, /no jaw footprint check/i);
});

/* ---------------- Nothing prints as undefined ---------------- */

const margin = (over: Record<string, unknown>) => ({
  verdict: "MARGINAL", margin: 1.4, resistingForce: 300, appliedLoad: 214,
  governingMode: "SLIDING", method: "Coulomb friction, development analysis",
  primaryRisk: null, recommendations: [], developmentAnalysis: true, ...over,
});

test("an indeterminate margin never prints 'undefined' or 'null' at an operator", () => {
  // holding-margin returns INDETERMINATE with margin, appliedLoad and
  // resistingForce all null. These were interpolated raw: the finding read
  // "it comes out at undefined×" and "null lbf".
  const r = reviewPackage(
    input({
      workholdingBySetup: {
        s1: { holdingMargin: margin({ verdict: "INDETERMINATE", margin: null, resistingForce: null, appliedLoad: null, governingMode: null }) },
      } as unknown as ReviewInput["workholdingBySetup"],
    }),
  );
  const f = r.findings.find((x) => /grip margin/i.test(x.title));
  assert.ok(f, "an indeterminate margin is still worth raising");
  const text = JSON.stringify(f);
  for (const bad of ["undefined", "null lbf", "NaN"]) {
    assert.ok(!text.includes(bad), `the finding prints "${bad}": ${text}`);
  }
  assert.match(f.title, /could not be established/i, "it must say it is unknown, not report a grade");
});

test("no finding anywhere prints undefined or NaN", () => {
  const r = reviewPackage(
    input({
      workholdingBySetup: {
        s1: { holdingMargin: margin({ verdict: "INSUFFICIENT", margin: 0.8 }) },
      } as unknown as ReviewInput["workholdingBySetup"],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
      capability: [
        { featureId: "f1", featureLabel: "40 mm bore", verdict: "NO_INSTRUMENT", toleranceBand: null, bestInstrument: null, consumedFraction: null, requiredUncertainty: null, reason: "No instrument on hand reaches this band.", recommendations: [], clearableByConfirmation: false },
      ] as unknown as ReviewInput["capability"],
    }),
  );
  assert.ok(r.findings.length >= 3);
  const text = JSON.stringify(r);
  for (const bad of ["undefined", "NaN", ": null,"]) {
    if (bad === ": null,") continue; // legitimate nulls exist in location
    assert.ok(!text.includes(bad), `output contains "${bad}"`);
  }
});

test("an adequate margin raises nothing", () => {
  const r = reviewPackage(
    input({
      workholdingBySetup: { s1: { holdingMargin: margin({ verdict: "ADEQUATE", margin: 3.1 }) } } as unknown as ReviewInput["workholdingBySetup"],
    }),
  );
  assert.equal(r.findings.filter((f) => /grip margin/i.test(f.title)).length, 0);
});

test("an insufficient margin is HIGH and a marginal one is not", () => {
  const at = (v: string, m: number | null) =>
    reviewPackage(
      input({ workholdingBySetup: { s1: { holdingMargin: margin({ verdict: v, margin: m }) } } as unknown as ReviewInput["workholdingBySetup"] }),
    ).findings.find((f) => /grip margin/i.test(f.title));
  assert.equal(at("INSUFFICIENT", 0.8)?.severity, "HIGH");
  assert.equal(at("MARGINAL", 1.6)?.severity, "MEDIUM");
});

/* ---------------- Tool reach ---------------- */

test("a tool that cannot reach the depth is HIGH", () => {
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375, operations: [{ id: "o1", label: "Deep bore", toolId: "t1", finalZ: -2.5, type: "BORE" }] }],
    } as unknown as Partial<ReviewInput>),
  );
  const f = r.findings.find((x) => /cannot reach/i.test(x.title));
  assert.ok(f, "1.5 of stickout does not reach 2.5 deep");
  assert.equal(f.severity, "HIGH");
});

test("an operation with no tool assigned raises no reach finding rather than a wrong one", () => {
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375, operations: [{ id: "o1", label: "Deep bore", toolId: null, finalZ: -2.5, type: "BORE" }] }],
    } as unknown as Partial<ReviewInput>),
  );
  assert.equal(r.findings.filter((f) => /reach|holder/i.test(f.title)).length, 0);
});

test("a tool that only just reaches is MEDIUM, not silent", () => {
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375, operations: [{ id: "o1", label: "Pocket", toolId: "t1", finalZ: -1.35, type: "POCKET_2D" }] }],
    } as unknown as Partial<ReviewInput>),
  );
  const f = r.findings.find((x) => /holder collision/i.test(x.title));
  assert.ok(f, "0.150 between the holder nose and the cut is worth saying");
  assert.equal(f.severity, "MEDIUM");
});

test("the reach check admits the holder is not modelled", () => {
  const r = reviewPackage(
    input({
      setups: [{ id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375, operations: [{ id: "o1", label: "Pocket", toolId: "t1", finalZ: -1.35, type: "POCKET_2D" }] }],
    } as unknown as Partial<ReviewInput>),
  );
  assert.match(r.findings.find((x) => /holder collision/i.test(x.title))!.method, /not modelled as geometry/i);
});

/* ---------------- Inspection capability ---------------- */

test("a feature that cannot be measured is HIGH and points at the feature", () => {
  const r = reviewPackage(
    input({
      capability: [
        { featureId: "f1", featureLabel: "40 mm bore", verdict: "NOT_CAPABLE", toleranceBand: 0.001, bestInstrument: { description: "Caliper", uncertainty: 0.0015 }, consumedFraction: 1.5, requiredUncertainty: 0.0001, reason: "The caliper consumes the whole band.", recommendations: ["Buy a bore gauge"], clearableByConfirmation: false },
      ] as unknown as ReviewInput["capability"],
    }),
  );
  const f = r.findings.find((x) => /cannot be verified/i.test(x.title));
  assert.ok(f);
  assert.equal(f.severity, "HIGH");
  assert.equal(f.location.featureId, "f1");
  assert.equal(f.location.context, "VERIFY");
});

test("a capable feature raises nothing", () => {
  const r = reviewPackage(
    input({
      capability: [
        { featureId: "f1", featureLabel: "40 mm bore", verdict: "CAPABLE", toleranceBand: 0.001, bestInstrument: null, consumedFraction: 0.08, requiredUncertainty: null, reason: "ok", recommendations: [], clearableByConfirmation: false },
      ] as unknown as ReviewInput["capability"],
    }),
  );
  assert.equal(r.findings.length, 0);
});

/* ---------------- Ranking and honesty ---------------- */

test("findings come back worst first", () => {
  const r = reviewPackage(
    input({
      workholdingBySetup: { s1: { holdingMargin: margin({ verdict: "MARGINAL", margin: 1.6 }) } } as unknown as ReviewInput["workholdingBySetup"],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
    }),
  );
  const ranks = r.findings.map((f) => SEVERITIES.indexOf(f.severity));
  assert.deepEqual([...ranks].sort((a, b) => a - b), ranks, "a MEDIUM must not sit above a HIGH");
});

test("the counts are counts", () => {
  const r = reviewPackage(
    input({
      workholdingBySetup: { s1: { holdingMargin: margin({ verdict: "MARGINAL", margin: 1.6 }) } } as unknown as ReviewInput["workholdingBySetup"],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
    }),
  );
  assert.equal(r.highCount, r.findings.filter((f) => f.severity === "HIGH").length);
  assert.equal(r.mediumCount, r.findings.filter((f) => f.severity === "MEDIUM").length);
  assert.equal(r.lowCount, r.findings.filter((f) => f.severity === "LOW").length);
  assert.equal(r.highCount + r.mediumCount + r.lowCount, r.findings.length);
});

test("every finding carries evidence and a method that can be argued with", () => {
  const r = reviewPackage(
    input({
      workholdingBySetup: { s1: { holdingMargin: margin({ verdict: "INSUFFICIENT", margin: 0.8 }) } } as unknown as ReviewInput["workholdingBySetup"],
      movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] },
    }),
  );
  const ids = new Set<string>();
  for (const f of r.findings) {
    assert.ok(f.evidence.length > 0, `${f.title} carries no evidence`);
    assert.ok(f.method.length > 10, `${f.title} names no method`);
    assert.ok(f.recommendation.length > 10, `${f.title} says nothing to do`);
    assert.ok(!ids.has(f.key), "finding keys must be unique");
    ids.add(f.key);
  }
});

test("a clean review states what it did NOT check rather than implying safety", () => {
  // This is the whole point of the file's WHAT THIS IS NOT section. A clean
  // result that reads as "safe" is the most dangerous string in the app.
  const r = reviewPackage(input());
  assert.equal(r.findings.length, 0);
  assert.ok(!/(is|looks|appears) safe/i.test(r.headline), `the headline claims safety: ${r.headline}`);
  assert.match(r.headline, /not the same as the program being safe/i);
  assert.ok(r.checksSkipped.length > 0, "there is always something it cannot check");
});

test("the things CANVAS structurally cannot do are always declared", () => {
  const r = reviewPackage(input());
  const declared = r.checksSkipped.map((c) => c.check + " " + c.reason).join(" ");
  for (const pattern of [/stock removal|gouge/i, /fixture.*collision/i, /post.*not certified|program syntax/i]) {
    assert.ok(pattern.test(declared), `missing declaration for ${pattern}`);
  }
});

test("the clean headline counts the checks that actually ran", () => {
  const withDevice = reviewPackage(input());
  const without = reviewPackage(input({ device: null }));
  assert.ok(
    withDevice.checksRun.length > without.checksRun.length,
    "a check that could not run must not be counted as run",
  );
  assert.match(withDevice.headline, new RegExp(`${withDevice.checksRun.length} checks`));
});

test("the review is deterministic", () => {
  const i = input({ movesByOperation: { o1: [rapid(0, 0, -0.5), rapid(3, 0, -0.5)] } });
  assert.deepEqual(reviewPackage(i), reviewPackage(i));
});
