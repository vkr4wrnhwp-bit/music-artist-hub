import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildGuidedPlan, nextStep, validSighting, type PhotoRead, type PhotoSighting } from "@/lib/engines/photo-plan";
import type { MetrologyDevice } from "@/lib/domain/shop";

/**
 * "I HAVE THE PART AND A PHONE. WHERE DO I START?"
 *
 * The measurement plan knew how to order work and could not point. A machinist
 * read a list of labels and had to match each one to a lump of metal, and for a
 * part nobody had modelled there were no labels either — the list is built from
 * features, and there were none.
 *
 * A model looking at a photograph can say "there is a bore here, four holes
 * there". That is pattern recognition, which it is good at. It is not a
 * measurement, and it must never be able to pretend to be one.
 */

const sight = (over: Partial<PhotoSighting> = {}): PhotoSighting => ({
  label: "central bore",
  kind: "BORE",
  x: 0.5,
  y: 0.5,
  whatToMeasure: "inside diameter and depth",
  ...over,
});

const device = (deviceType: string, description: string) =>
  ({ deviceType, description, uncertainty: 0.0005 }) as unknown as MetrologyDevice;

const CRIB = [
  device("CALIPER", '6" digital caliper'),
  device("BORE_GAUGE", '1-2" bore gauge'),
  device("MICROMETER", '0-1" micrometer'),
];

const read = (sightings: PhotoSighting[], over: Partial<PhotoRead> = {}): PhotoRead => ({
  connected: true,
  sightings,
  note: "",
  ...over,
});

/* ---------------- The model points; it does not measure ---------------- */

test("a sighting has nowhere to put a dimension", () => {
  /*
   * The whole safety argument, and it is structural rather than a rule
   * somebody has to remember. A model asked to describe a part will happily
   * volunteer "approximately 40 mm", and a plausible diameter is the most
   * dangerous thing this application could produce because it arrives looking
   * exactly like a measured one.
   */
  const src = readFileSync("src/lib/engines/photo-plan.ts", "utf8");
  const iface = /export interface PhotoSighting \{[\s\S]*?\n\}/.exec(src)![0];
  for (const forbidden of ["diameter", "size", "estimate", "value", "range", "depth:", "width", "length", "approx"]) {
    assert.equal(
      new RegExp(`\\b${forbidden}`, "i").test(iface.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "")),
      false,
      `PhotoSighting has a field a dimension could go in: ${forbidden}`,
    );
  }
});

test("the vision prompt forbids stating a dimension at all", () => {
  const src = readFileSync("src/lib/ai/anthropic.ts", "utf8");
  const fn = /async readPartPhoto\([\s\S]*?\n  \}/.exec(src)![0];
  assert.match(fn, /DO NOT state or estimate any dimension/);
  assert.match(fn, /not even approximately, not even as a range/);
  assert.match(fn, /You cannot measure from a photograph/);
  /*
   * And the tool schema offers no PROPERTY a number could go in. The property
   * names are what matter, not the prose: `whatToMeasure`'s own description
   * says "inside diameter and depth", which is the instruction to go and take
   * one rather than an offer to supply it.
   */
  const item = /items: \{\s*type: "object",\s*properties: \{([\s\S]*?)\n {14}\},\s*required: \["label"/.exec(fn);
  assert.ok(item, "could not read the sighting schema");
  const names = [...item![1].matchAll(/^\s{16}(\w+):/gm)].map((m) => m[1]);
  assert.deepEqual(names, ["label", "kind", "x", "y", "whatToMeasure", "note"], `schema properties: ${names.join(", ")}`);
});

test("a provider with no vision model produces no list at all", () => {
  /*
   * The worst version of this feature would be a deterministic fallback
   * inventing "there is probably a bore in the middle". A machinist would
   * measure what it told them to and never learn it was guessed from nothing.
   */
  const plan = buildGuidedPlan({ connected: false, sightings: [], note: "No vision model is connected." }, CRIB, 1);
  assert.deepEqual(plan.steps, []);
  assert.match(plan.headline, /No vision model is connected/);
  const src = readFileSync("src/lib/ai/deterministic.ts", "utf8");
  assert.match(src, /nothing has been read from it, and no list of things to measure has been produced/);
});

/* ---------------- What comes back is checked ---------------- */

test("a sighting outside the image, or naming a kind CANVAS does not know, is dropped", () => {
  // A pin in the wrong place points at the wrong lump of metal, which is worse
  // than one pin fewer.
  assert.equal(validSighting(sight()), true);
  assert.equal(validSighting(sight({ x: 1.4 })), false, "a point off the right edge was accepted");
  assert.equal(validSighting(sight({ x: -0.2 })), false, "a point off the left edge was accepted");
  assert.equal(validSighting(sight({ y: -0.2 })), false);
  assert.equal(validSighting(sight({ y: 1.01 })), false);
  assert.equal(validSighting({ ...sight(), kind: "GEAR_TOOTH" }), false, "an unknown feature kind was accepted");
  assert.equal(validSighting({ ...sight(), label: "  " }), false);
  assert.equal(validSighting({ ...sight(), whatToMeasure: "" }), false, "a sighting with nothing to measure was accepted");
  assert.equal(validSighting({ ...sight(), x: Number.NaN }), false);
  assert.equal(validSighting(null), false);
});

test("dropped readings are counted in the note rather than disappearing", () => {
  const src = readFileSync("src/lib/ai/anthropic.ts", "utf8");
  assert.match(src, /did not name a feature kind CANVAS knows or fell outside the image, and were dropped/);
});

/* ---------------- The order of work ---------------- */

test("the datum comes first and blocks", () => {
  /*
   * A bore is 2.000 FROM SOMETHING. Until that something is named the number
   * is not reproducible — the next person measures from a different edge and
   * gets an answer that is equally defensible and different. So the plan says
   * stop, rather than letting somebody work down the list and find out at the
   * end that half of it has to be taken again.
   */
  const plan = buildGuidedPlan(read([sight(), sight({ kind: "FACE", label: "top face", whatToMeasure: "thickness" })]), CRIB, 1);
  assert.equal(plan.steps[0].kind, "FACE", "the bore was scheduled before the face it is measured from");
  assert.equal(plan.steps[0].blocking, true);
  assert.match(plan.steps[0].why, /what everything else is measured from/);
  assert.equal(plan.steps[1].blocking, false);
});

test("the part's size comes before its details", () => {
  const plan = buildGuidedPlan(
    read([
      sight({ kind: "CHAMFER", label: "edge break" }),
      sight({ kind: "DRILLED_HOLE", label: "corner holes" }),
      sight({ kind: "OUTSIDE_CONTOUR", label: "outline" }),
      sight({ kind: "FACE", label: "top face" }),
    ]),
    CRIB,
    1,
  );
  assert.deepEqual(
    plan.steps.map((s) => s.kind),
    ["FACE", "OUTSIDE_CONTOUR", "DRILLED_HOLE", "CHAMFER"],
    "a feature's position is meaningless if the block it sits in is the wrong size",
  );
  assert.deepEqual(plan.steps.map((s) => s.order), [1, 2, 3, 4]);
});

/* ---------------- The instrument this shop actually owns ---------------- */

test("each step names something in the shop's own library", () => {
  const plan = buildGuidedPlan(read([sight({ kind: "FACE" }), sight({ kind: "BORE" })]), CRIB, 1);
  assert.equal(plan.steps.find((s) => s.kind === "BORE")!.instrument, '1-2" bore gauge');
  assert.equal(plan.steps.find((s) => s.kind === "FACE")!.instrument, '0-1" micrometer');
});

test("a step nothing in the shop can take is listed and said, not dropped", () => {
  /*
   * Silently omitting it would leave a machinist with a list they can finish
   * and a part they have not described.
   */
  const plan = buildGuidedPlan(read([sight({ kind: "TAPPED_HOLE", label: "1/4-20 holes", whatToMeasure: "thread size" })]), [], 1);
  assert.equal(plan.steps[0].instrument, null);
  assert.equal(plan.unmeasurable.length, 1);
  assert.match(plan.unmeasurable[0], /1\/4-20 holes — thread size/);
  assert.match(plan.caveats.join(" "), /no instrument in this shop's metrology library/);
  assert.match(plan.caveats.join(" "), /listed and left unmeasured rather than dropped/);
});

test("the caliper stands in when the right instrument is absent, and it is named", () => {
  const plan = buildGuidedPlan(read([sight({ kind: "BORE" })]), [device("CALIPER", '6" caliper')], 1);
  assert.equal(plan.steps[0].instrument, '6" caliper');
});

/* ---------------- What the plan says about itself ---------------- */

test("the plan says a model looked at a photograph and measured nothing", () => {
  const plan = buildGuidedPlan(read([sight()]), CRIB, 1);
  assert.match(plan.caveats.join(" "), /It did not measure anything, and it cannot/);
  assert.match(plan.caveats.join(" "), /every dimension below is one you go and take/);
  assert.match(plan.caveats.join(" "), /Nothing here becomes geometry until a reading is recorded/);
});

test("one view is one view, and the plan says which faces it has not seen", () => {
  /*
   * A machinist who takes the list as a description of the part measures the
   * five things on it and misses the sixth, on the face nobody photographed.
   */
  const one = buildGuidedPlan(read([sight()]), CRIB, 1);
  assert.match(one.caveats.join(" "), /This is one view of the part/);
  assert.match(one.caveats.join(" "), /a list you can finish is not the same as a part you have described/);
  assert.match(buildGuidedPlan(read([sight()]), CRIB, 4).caveats.join(" "), /This is 4 views/);
});

test("what the model could not see travels with the plan", () => {
  const plan = buildGuidedPlan(read([sight()], { note: "The underside is not visible in this view." }), CRIB, 1);
  assert.match(plan.caveats.join(" "), /The underside is not visible/);
});

test("a caution on a sighting reaches the step it belongs to", () => {
  const plan = buildGuidedPlan(read([sight({ note: "Partly in shadow — this may be a counterbore." })]), CRIB, 1);
  assert.equal(plan.steps[0].caution, "Partly in shadow — this may be a counterbore.");
  assert.equal(buildGuidedPlan(read([sight()]), CRIB, 1).steps[0].caution, null);
});

test("nothing recognisable is said plainly", () => {
  const plan = buildGuidedPlan(read([], { note: "Too dark to make anything out." }), CRIB, 1);
  assert.deepEqual(plan.steps, []);
  assert.match(plan.headline, /Nothing recognisable/);
  assert.match(plan.caveats.join(" "), /Too dark/);
});

/* ---------------- Working through it ---------------- */

test("the next step is the first with no reading against it", () => {
  const plan = buildGuidedPlan(read([sight({ kind: "FACE" }), sight({ kind: "BORE" }), sight({ kind: "CHAMFER" })]), CRIB, 1);
  assert.equal(nextStep(plan, [])!.order, 1);
  assert.equal(nextStep(plan, [1])!.order, 2);
  assert.equal(nextStep(plan, [1, 2, 3]), null);
  // Order of completion is the machinist's business; the plan just tracks it.
  assert.equal(nextStep(plan, [2])!.order, 1);
});

test("the headline names the first thing to do", () => {
  const plan = buildGuidedPlan(read([sight({ kind: "FACE", label: "top face" }), sight()]), CRIB, 1);
  assert.match(plan.headline, /2 things to measure, in order\. Start with top face\./);
});

/* ---------------- What reaches the machinist, and what does not ---------------- */

const strip = (x: string) => x.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the route returns a plan and never a dimension", () => {
  const src = strip(readFileSync("src/app/api/parts/photo-plan/route.ts", "utf8"));
  assert.ok(/readPartPhoto\(/.test(src));
  assert.ok(/buildGuidedPlan\(read, devices, views\)/.test(src), "the plan is not built against this shop's instruments");
  // Typed, not inferred: a model looked at a picture, so the actor is AI.
  assert.ok(/actorType: "AI"/.test(src), "the vision read is not logged as a model's work");
  assert.ok(/No dimension was produced/.test(src));
  // Organisation from the session, part id re-checked against it.
  assert.ok(/where: \{ id: partId, organizationId: user\.organizationId \}/.test(src), "a posted part id is trusted");
});

test("a reading is attributed to the instrument that took it", () => {
  /*
   * A number with no instrument behind it has no uncertainty, and the nominal
   * engine would resolve it as though it were exact. The step recommends an
   * instrument; which one was actually reached for is a different question and
   * it is the one that sets the error bar.
   */
  const guide = strip(readFileSync("src/components/reverse/photo-guide.tsx", "utf8"));
  assert.ok(/Measured with/.test(guide), "the guide does not ask which instrument was used");
  assert.ok(/deviceId === ""/.test(guide), "a reading can be recorded with no instrument named");

  const measure = strip(readFileSync("src/components/reverse/photo-measure.tsx", "utf8"));
  assert.ok(/"\/api\/measurements"/.test(measure), "readings bypass the measurement endpoint");
  assert.ok(/deviceId,/.test(measure));
  assert.ok(/sessionId,/.test(measure), "the reading does not land in the session");
});

test("the guide shows the caveats before the list, not after it", () => {
  // A machinist who reads the list as a description of the part measures the
  // five things on it and misses the sixth.
  const src = readFileSync("src/components/reverse/photo-guide.tsx", "utf8");
  const caveats = src.indexOf("plan.caveats.map");
  const list = src.indexOf("<ol className");
  assert.ok(caveats > 0 && caveats < list, "the caveats sit below the work list");
});

test("the page mounts it against a real session and the shop's own devices", () => {
  const src = strip(readFileSync("src/app/(app)/reverse-engineer/[id]/page.tsx", "utf8"));
  assert.ok(/<PhotoMeasure/.test(src));
  assert.ok(/sessionId=\{session\.id\}/.test(src));
  assert.ok(/devices=\{devices\.map/.test(src), "the guide is not given this shop's instruments");
});
