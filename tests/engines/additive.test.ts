import { test } from "node:test";
import assert from "node:assert/strict";
import { assessAdditive, tightestBand, anisotropyIsPossible, type AdditiveInput, type PrinterRecord, type PrintMaterialRecord } from "@/lib/engines/additive";
import { emptyPartIntent } from "@/lib/domain/part-intent";
import type { Feature } from "@/lib/domain/features";
import type { PartIntent } from "@/lib/domain/part-intent";

/**
 * The method advisor listed additive and reasoned about it from feature count
 * and volume alone — a shop with a hobby FDM machine on the bench and a
 * ±0.0005 bearing bore on the drawing got the same sentence as a shop with a
 * laser powder-bed machine.
 *
 * What these pin is that the answer comes from what the shop actually owns and
 * what the part actually carries, and that the engine refuses where it cannot
 * know. The rule that matters most is anisotropy: a printed part is bonded
 * between layers rather than continuous through them, and assuming otherwise
 * is the assumption that breaks it.
 */

const printer = (over: Partial<PrinterRecord> = {}): PrinterRecord => ({
  id: "p1",
  manufacturer: "Prusa",
  model: "MK4",
  technology: "FDM",
  buildX: 9.8,
  buildY: 8.3,
  buildZ: 8.6,
  achievableTolerance: 0.008,
  achievableRa: 500,
  ...over,
});

const mat = (over: Partial<PrintMaterialRecord> = {}): PrintMaterialRecord => ({
  id: "m1",
  name: "PETG",
  technology: "FDM",
  tensileXY: 7000,
  tensileZ: 3200,
  maxServiceTempF: 160,
  creepDataOnFile: false,
  ...over,
});

const feat = (band: number | null, id = "f1"): Feature =>
  ({
    id,
    kind: "BORE",
    label: "bore",
    functionalRole: "BEARING_FIT",
    critical: true,
    diameter: 1.25,
    depth: 0.5,
    tolerance: band == null ? undefined : { plus: band / 2, minus: band / 2 },
  }) as unknown as Feature;

const intent = (over: Partial<Record<string, unknown>> = {}): PartIntent => {
  const i = emptyPartIntent("Test part");
  const set = (k: string, v: unknown) => {
    (i as unknown as Record<string, { value: unknown }>)[k] = { value: v, source: "USER", confidence: "VERIFIED", confirmedByUser: true } as never;
  };
  set("loadBearing", false);
  for (const [k, v] of Object.entries(over)) set(k, v);
  return i;
};

const input = (over: Partial<AdditiveInput> = {}): AdditiveInput => ({
  intent: intent(),
  features: [feat(0.02)],
  envelope: { x: 4, y: 3, z: 1 },
  printers: [printer()],
  printMaterials: [mat()],
  ...over,
});

const findingFor = (r: ReturnType<typeof assessAdditive>, check: string) =>
  r.assessments[0].findings.find((f) => f.check === check);

/* ---------------- It answers from what the shop owns ---------------- */

test("with no printer on file it declines to answer at all", () => {
  // A generic machine's numbers are not this shop's numbers.
  const r = assessAdditive(input({ printers: [] }));
  assert.equal(r.assessments.length, 0);
  assert.match(r.unavailable!, /No printer is on file/i);
  assert.match(r.unavailable!, /property of that printer/i);
});

test("it assesses every printer the shop owns, separately", () => {
  const r = assessAdditive(
    input({ printers: [printer(), printer({ id: "p2", manufacturer: "Formlabs", model: "Form 4", technology: "SLA", achievableTolerance: 0.002 })] }),
  );
  assert.equal(r.assessments.length, 2);
  assert.deepEqual(r.assessments.map((a) => a.printerLabel), ["Prusa MK4", "Formlabs Form 4"]);
});

/* ---------------- Tolerance ---------------- */

test("a band the printer cannot hold is NOT_RECOMMENDED, with the multiple", () => {
  // ±0.008 against a 0.0005 band is 32x. This is the sentence a machinist
  // needs: not "additive is unsuitable", but the number that makes it so.
  const r = assessAdditive(input({ features: [feat(0.0005)] }));
  const f = findingFor(r, "TOLERANCE")!;
  assert.equal(f.verdict, "NOT_RECOMMENDED");
  assert.match(f.detail, /0\.0005/);
  assert.match(f.detail, /±0\.0080/);
  assert.match(f.detail, /32×/);
});

test("a generous band the printer comfortably holds is VIABLE", () => {
  const r = assessAdditive(input({ features: [feat(0.1)] }));
  assert.equal(findingFor(r, "TOLERANCE")!.verdict, "VIABLE");
});

test("an unmeasured printer is INSUFFICIENT_DATA, not assumed accurate", () => {
  // And not assumed inaccurate either — the honest answer is print a coupon.
  const r = assessAdditive(input({ printers: [printer({ achievableTolerance: null })] }));
  const f = findingFor(r, "TOLERANCE")!;
  assert.equal(f.verdict, "INSUFFICIENT_DATA");
  assert.match(f.detail, /marketing number/i);
  assert.match(f.detail, /test coupon/i);
});

test("a part with no tolerances is not constrained on accuracy", () => {
  const r = assessAdditive(input({ features: [feat(null)] }));
  assert.equal(findingFor(r, "TOLERANCE")!.verdict, "VIABLE");
  assert.equal(r.tightestBand, null);
});

test("the tightest band on the part is the one that governs", () => {
  assert.equal(tightestBand([feat(0.02, "a"), feat(0.001, "b"), feat(0.05, "c")]), 0.001);
  assert.equal(tightestBand([feat(null)]), null);
});

/* ---------------- Anisotropy — the one that matters ---------------- */

test("a cyclic load across the layers is called out with both strengths", () => {
  const r = assessAdditive(input({ intent: intent({ loadBearing: true, loadingType: ["CYCLIC"] }) }));
  const f = findingFor(r, "ANISOTROPY")!;
  assert.equal(f.verdict, "NOT_RECOMMENDED");
  assert.match(f.detail, /3200 psi against 7000/);
  assert.match(f.detail, /46%/);
  assert.match(f.detail, /bonded between layers/i);
});

test("a material that keeps most of its strength through Z is REVIEW, not refused", () => {
  // SLS nylon is far more isotropic than FDM. The engine must not treat all
  // printing as equally anisotropic.
  const r = assessAdditive(
    input({
      intent: intent({ loadBearing: true, loadingType: ["BENDING"] }),
      printMaterials: [mat({ name: "PA12", tensileXY: 6800, tensileZ: 6100 })],
    }),
  );
  assert.equal(findingFor(r, "ANISOTROPY")!.verdict, "REVIEW");
});

test("a material recording only in-plane strength is INSUFFICIENT_DATA", () => {
  // Assuming the missing figure equals the recorded one is the assumption that
  // breaks a printed part.
  const r = assessAdditive(
    input({ intent: intent({ loadBearing: true, loadingType: ["SHOCK"] }), printMaterials: [mat({ tensileZ: null })] }),
  );
  const f = findingFor(r, "ANISOTROPY")!;
  assert.equal(f.verdict, "INSUFFICIENT_DATA");
  assert.match(f.detail, /assumption that breaks/i);
});

test("a part that carries no load is not judged on anisotropy at all", () => {
  // The note has to be quiet where it does not apply.
  const r = assessAdditive(input({ intent: intent({ loadBearing: false, loadingType: ["CYCLIC"] }) }));
  assert.equal(findingFor(r, "ANISOTROPY"), undefined);
});

test("static compression alone is not treated as a layer-direction problem", () => {
  // Squashing a printed part down the build axis is the one case that is
  // genuinely fine, and flagging it would make the real warnings noise.
  const r = assessAdditive(input({ intent: intent({ loadBearing: true, loadingType: ["STATIC"] }) }));
  assert.equal(findingFor(r, "ANISOTROPY"), undefined);
});

/* ---------------- What is not known ---------------- */

test("an unknown responsibility profile stops it recommending printing", () => {
  const i = emptyPartIntent("Unknown part");
  const r = assessAdditive(input({ intent: i, features: [feat(0.1)] }));
  const f = findingFor(r, "RESPONSIBILITY")!;
  assert.equal(f.verdict, "INSUFFICIENT_DATA");
  assert.match(f.detail, /not the same as it carrying nothing/i);
  assert.notEqual(r.assessments[0].verdict, "VIABLE");
});

test("a sustained load with no creep figure on file is named", () => {
  // A press-fit in a polymer is a creep question, and a tensile number does
  // not answer it.
  const r = assessAdditive(input({ intent: intent({ loadBearing: true, loadingType: ["STATIC"] }) }));
  const f = findingFor(r, "CREEP")!;
  assert.equal(f.verdict, "INSUFFICIENT_DATA");
  assert.match(f.detail, /creep/i);
});

test("metal powder-bed is not asked a creep question", () => {
  const r = assessAdditive(
    input({
      intent: intent({ loadBearing: true, loadingType: ["STATIC"] }),
      printers: [printer({ technology: "METAL_PBF" })],
      printMaterials: [mat({ technology: "METAL_PBF", name: "17-4 PH" })],
    }),
  );
  assert.equal(findingFor(r, "CREEP"), undefined);
});

/* ---------------- Service conditions ---------------- */

test("a service temperature above the material's rating refuses", () => {
  const r = assessAdditive(input({ intent: intent({ temperatureRange: { min: 70, max: 220 } }) }));
  const f = findingFor(r, "TEMPERATURE")!;
  assert.equal(f.verdict, "NOT_RECOMMENDED");
  assert.match(f.detail, /220°F/);
  assert.match(f.detail, /160°F/);
  assert.match(f.detail, /not a structural material/i);
});

test("a service temperature inside the rating passes and says by how much", () => {
  const r = assessAdditive(input({ intent: intent({ temperatureRange: { min: 70, max: 120 } }) }));
  const f = findingFor(r, "TEMPERATURE")!;
  assert.equal(f.verdict, "VIABLE");
  assert.match(f.detail, /rated to 160/);
});

/* ---------------- Build volume ---------------- */

test("a part that fits in some orientation fits", () => {
  // The part can be turned on the bed. Comparing axis to axis in the order
  // they happen to be recorded would reject parts that fit perfectly well.
  const r = assessAdditive(input({ envelope: { x: 1, y: 8.5, z: 9 } }));
  assert.equal(findingFor(r, "BUILD_VOLUME")!.verdict, "VIABLE");
});

test("a part too big in every orientation is refused with both envelopes", () => {
  const r = assessAdditive(input({ envelope: { x: 12, y: 3, z: 1 } }));
  const f = findingFor(r, "BUILD_VOLUME")!;
  assert.equal(f.verdict, "NOT_RECOMMENDED");
  assert.match(f.detail, /12\.00/);
  assert.match(f.detail, /Splitting and bonding is a different part/i);
});

test("no envelope recorded is INSUFFICIENT_DATA, not a fit", () => {
  const r = assessAdditive(input({ envelope: null }));
  assert.equal(findingFor(r, "BUILD_VOLUME")!.verdict, "INSUFFICIENT_DATA");
});

/* ---------------- Aggregation and the middle path ---------------- */

test("the worst finding decides the verdict, never an average", () => {
  const r = assessAdditive(input({ features: [feat(0.0005)], intent: intent({ loadBearing: false }) }));
  assert.equal(r.assessments[0].verdict, "NOT_RECOMMENDED");
  assert.ok(r.assessments[0].findings.some((f) => f.verdict === "VIABLE"), "the fixture has no passing findings to average away");
});

test("failing on tolerance alone offers printing near-net and finishing", () => {
  // The reason this engine is worth having: a part that cannot be printed to
  // size is not a part that cannot be printed.
  const r = assessAdditive(input({ features: [feat(0.0005)], intent: intent({ loadBearing: false }) }));
  assert.ok(r.assessments[0].hybridNote);
  assert.match(r.assessments[0].hybridNote!, /near-net/i);
  assert.match(r.assessments[0].hybridNote!, /two processes/i);
});

test("failing on something a second operation cannot fix offers no such thing", () => {
  // Machining afterwards does not make a part fit the bed, and it does not
  // change which way the layers run.
  const tooBig = assessAdditive(input({ envelope: { x: 12, y: 3, z: 1 }, features: [feat(0.0005)] }));
  assert.equal(tooBig.assessments[0].hybridNote, null);

  const anisotropic = assessAdditive(
    input({ features: [feat(0.0005)], intent: intent({ loadBearing: true, loadingType: ["CYCLIC"] }) }),
  );
  assert.equal(anisotropic.assessments[0].hybridNote, null);
});

test("every finding carries a number or a named gap, never a bare verdict", () => {
  const r = assessAdditive(
    input({ features: [feat(0.0005)], intent: intent({ loadBearing: true, loadingType: ["CYCLIC", "STATIC"], temperatureRange: { min: 70, max: 220 } }) }),
  );
  for (const f of r.assessments[0].findings) {
    assert.ok(f.detail.length > 40, `${f.check} says almost nothing: "${f.detail}"`);
    // Either a number, or a phrase naming what is absent. The creep finding
    // names its gap as "no polymer on file has a recorded creep figure",
    // which an earlier, narrower pattern here missed.
    const namesAGap = /\bno\b[^.]*\b(on file|recorded|records)\b|not recorded|nobody has/i.test(f.detail);
    assert.ok(/\d/.test(f.detail) || namesAGap, `${f.check} carries no number and names no gap: "${f.detail}"`);
  }
});

/* ---------------- A material entered the wrong way round ---------------- */

test("a material cannot be stronger across its layers than within them", () => {
  // Not merely wrong: the anisotropy check would then report the part is fine
  // in the direction it is actually weakest.
  assert.equal(anisotropyIsPossible(7100, 3250), true);
  assert.equal(anisotropyIsPossible(5000, 9000), false);
  // Equal is possible — a genuinely isotropic process exists.
  assert.equal(anisotropyIsPossible(6400, 6400), true);
});

test("an unmeasured figure is not treated as an impossible one", () => {
  // Blank is the honest state for most shops and must stay enterable.
  assert.equal(anisotropyIsPossible(7100, null), true);
  assert.equal(anisotropyIsPossible(null, 3250), true);
  assert.equal(anisotropyIsPossible(null, null), true);
});

test("a partly-recorded envelope is a missing input, not a crash", () => {
  /*
   * `finishedEnvelope.value ?? null` in package.ts catches a NULL envelope
   * and lets {x: 6, y: 4, z: undefined} straight through. Sorting that array
   * puts undefined last, .toFixed(2) throws, and the whole part page 500s —
   * on a part whose only fault is two dimensions recorded out of three. This
   * was live on CANVAS Demo Shaft.
   *
   * The verdict must be the same as no envelope at all: unanswerable, and it
   * names the axis. A build-volume verdict computed from a size nobody
   * supplied would be worse than no verdict.
   */
  const cases: [Record<string, number>, string][] = [
    [{ x: 6, y: 4 }, "z"],
    [{ x: 6, z: 1 }, "y"],
    [{ y: 4, z: 1 }, "x"],
    [{ x: 6 }, "y or z"],
    [{ x: 6, y: 4, z: Number.NaN }, "z"],
  ];
  for (const [envelope, axis] of cases) {
    const r = assessAdditive(input({ envelope: envelope as never }));
    const build = findingFor(r, "BUILD_VOLUME")!;
    assert.equal(build.verdict, "INSUFFICIENT_DATA", `${JSON.stringify(envelope)} produced a verdict`);
    assert.match(build.detail, new RegExp(`no ${axis} dimension`), build.detail);
    assert.ok(!/NaN|undefined/.test(build.detail), build.detail);
  }

  // A complete envelope still answers, so the guard has not swallowed the case.
  assert.equal(findingFor(assessAdditive(input()), "BUILD_VOLUME")!.verdict, "VIABLE");
});
