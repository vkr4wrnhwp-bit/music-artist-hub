import { test } from "node:test";
import assert from "node:assert/strict";
import {
  proposeDatums,
  buildTasks,
  buildReconstructionPlan,
  nextTask,
  DATUM_SYSTEMS,
  type ReconstructionInput,
} from "@/lib/engines/reconstruction";
import type { Feature } from "@/lib/domain/features";

/**
 * This engine answers "I have the part, I need another one" — and the whole
 * point of it is that it does NOT derive geometry. It produces a list of
 * things a human must go and measure.
 *
 * So what these tests guard is the boundary: that nothing in the output can
 * be mistaken for a dimension, that nothing claims progress the part has not
 * made, and that the ordering doctrine in the file header — datums first,
 * envelope before features, interfaces before cosmetics — is what the code
 * actually does rather than what its comments say it does.
 */

const feature = (over: Partial<Feature> & { id: string; label: string }): Feature =>
  ({
    kind: "DRILLED_HOLE",
    functionalRole: "CLEARANCE",
    critical: false,
    diameter: 0.25,
    ...over,
  }) as unknown as Feature;

const BORE = feature({
  id: "f-bore", label: "Bearing bore", kind: "BORE", functionalRole: "BEARING_SEAT",
  critical: true, diameter: 1.5748, tolerance: { plus: 0.0005, minus: 0.0005 },
} as Partial<Feature> & { id: string; label: string });

const FACE = feature({
  id: "f-face", label: "Mounting face", kind: "FACE", functionalRole: "DATUM_FACE", critical: false,
} as Partial<Feature> & { id: string; label: string });

const DOWEL = feature({
  id: "f-dowel", label: "Dowel hole", kind: "DRILLED_HOLE", functionalRole: "DOWEL_HOLE", diameter: 0.25,
} as Partial<Feature> & { id: string; label: string });

const CLEARANCE = feature({ id: "f-c1", label: "M6 clearance", kind: "DRILLED_HOLE" });

const ALL_VIEWS = ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"];
const DESIGN_FRAME = [
  { system: "DESIGN", letter: "A" },
  { system: "DESIGN", letter: "B" },
  { system: "DESIGN", letter: "C" },
];

const input = (over: Partial<ReconstructionInput> = {}): ReconstructionInput => ({
  features: [FACE, BORE, DOWEL, CLEARANCE],
  uploadedViews: [],
  establishedDatums: [],
  completedLabels: [],
  inferredAwaitingReview: 0,
  ...over,
});

/* ---------------- The degrees-of-freedom claim ---------------- */

test("an unestablished frame constrains nothing, and says so", () => {
  // This printed "constrains 6 of 6 degrees of freedom" on every part in the
  // app, because it summed the PROPOSED frame — always a plane, an axis and
  // a point, always 3 + 2 + 1. It was a constant wearing the clothes of an
  // analysis result, and on a part with no features and no datums it read as
  // a completeness claim about work nobody had done.
  const plan = buildReconstructionPlan(input({ establishedDatums: [] }));
  assert.match(plan.headline, /constrains 0 of 6 degrees of freedom/);
});

test("the degrees of freedom accumulate as datums are actually established", () => {
  const at = (letters: string[]) =>
    buildReconstructionPlan(input({ establishedDatums: letters.map((letter) => ({ system: "DESIGN", letter })) })).headline;
  assert.match(at(["A"]), /constrains 3 of 6/, "a plane constrains three");
  assert.match(at(["A", "B"]), /constrains 5 of 6/, "an axis adds two");
  assert.match(at(["A", "B", "C"]), /constrains 6 of 6/, "a point adds the last one");
});

test("a manufacturing datum does not constrain the design frame", () => {
  // Establishing MANUFACTURING:A is real progress, but it is not the design
  // reference frame and must not be counted toward it.
  const plan = buildReconstructionPlan(input({ establishedDatums: [{ system: "MANUFACTURING", letter: "A" }] }));
  assert.match(plan.headline, /constrains 0 of 6/);
  assert.equal(plan.datumsEstablished, 1, "it is still counted as an established datum");
});

test("the frame never claims more than six degrees of freedom", () => {
  const plan = buildReconstructionPlan(
    input({ establishedDatums: [...DESIGN_FRAME, ...DESIGN_FRAME] }), // duplicates
  );
  const m = plan.headline.match(/constrains (\d+) of 6/);
  assert.ok(m && Number(m[1]) <= 6, `got ${plan.headline}`);
});

/* ---------------- Nothing here is a dimension ---------------- */

test("no task carries a measured value — only an instruction", () => {
  // The engine must never look like it read geometry off a photograph.
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS }));
  for (const t of plan.tasks) {
    assert.ok(t.instruction.length > 20, `${t.label} has no instruction`);
    assert.ok(t.unlocks.length > 0, `${t.label} does not say what it unlocks`);
    assert.ok(!("value" in t), `${t.label} carries a value`);
    assert.ok(!("measured" in t), `${t.label} carries a measurement`);
  }
});

test("an expected band is carried only when the feature actually has a tolerance", () => {
  const plan = buildReconstructionPlan(input({ features: [BORE, CLEARANCE] }));
  const bore = plan.tasks.find((t) => t.featureId === "f-bore");
  const clearance = plan.tasks.find((t) => t.featureId === "f-c1");
  assert.ok(bore && Math.abs(bore.expectedBand! - 0.001) < 1e-9, "the band is the sum of both limits");
  assert.equal(clearance?.expectedBand, null, "no tolerance means no band, not a default one");
});

test("an untoleranced interface gets no band either", () => {
  // The check above only exercised the ordinary-feature branch, because a
  // clearance hole is not an interface. An interface with no tolerance
  // recorded is precisely the case where inventing a band would be worst:
  // the band decides the instrument, and a fabricated one would send
  // somebody to a caliper for a press fit.
  const untoleranced = feature({
    id: "f-press", label: "Press fit boss", kind: "BORE", functionalRole: "PRESS_FIT", critical: true,
  } as Partial<Feature> & { id: string; label: string });
  const plan = buildReconstructionPlan(input({ features: [untoleranced] }));
  const task = plan.tasks.find((t) => t.featureId === "f-press");
  assert.ok(task, "precondition: a press fit is an interface and gets a task");
  assert.equal(task.expectedBand, null, "no recorded tolerance means no band");
});

test("every functional role that is an interface is treated as one", () => {
  // These roles decide the fit class and therefore the instrument. A role
  // quietly dropped from the interface list stops being measured early, and
  // stops being blocking — the plan then reports itself unblocked while an
  // interface is unmeasured.
  const roles = ["BEARING_SEAT", "PRESS_FIT", "SLIP_FIT", "SEAL_SURFACE"] as const;
  for (const role of roles) {
    const f = feature({
      id: `f-${role}`, label: `${role} feature`, kind: "BORE", functionalRole: role, critical: false,
    } as Partial<Feature> & { id: string; label: string });
    const tasks = buildTasks([CLEARANCE, f], true, []);
    const task = tasks.find((t) => t.featureId === `f-${role}`);
    assert.ok(task, `${role} produced no measurement task`);
    assert.equal(task.blocking, true, `${role} is an interface and must block`);
    assert.equal(task.datumLetter, "B", `${role} must be referenced to the frame`);
    assert.ok(
      task.order < tasks.find((t) => t.featureId === "f-c1")!.order,
      `${role} must be measured before an ordinary clearance hole`,
    );
  }
});

test("a feature marked critical is an interface whatever its role", () => {
  const f = feature({ id: "f-crit", label: "Critical width", kind: "SLOT", critical: true } as Partial<Feature> & { id: string; label: string });
  const task = buildTasks([f], true, []).find((t) => t.featureId === "f-crit");
  assert.ok(task && task.blocking, "a critical dimension blocks regardless of its functional role");
});

test("photographs are counted, never converted into features", () => {
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS, features: [] }));
  assert.equal(plan.photosOnFile, 6);
  assert.deepEqual(plan.missingViews, [], "all six views are on file");
  // Six photographs and no features must not produce feature measurements.
  assert.ok(
    plan.tasks.every((t) => t.featureId === null),
    "six photographs did not create geometry",
  );
});

/* ---------------- Ordering doctrine ---------------- */

test("the envelope comes before any feature", () => {
  const tasks = buildTasks([FACE, BORE, DOWEL, CLEARANCE], true, []);
  const firstFeature = tasks.findIndex((t) => t.featureId !== null);
  const lastEnvelope = tasks.map((t) => t.label).lastIndexOf("Overall Z");
  assert.ok(lastEnvelope < firstFeature, "a feature position is meaningless if the envelope is wrong");
});

test("interfaces come before ordinary features", () => {
  const tasks = buildTasks([CLEARANCE, BORE], true, []);
  const bore = tasks.findIndex((t) => t.featureId === "f-bore");
  const clearance = tasks.findIndex((t) => t.featureId === "f-c1");
  assert.ok(bore >= 0 && clearance >= 0);
  assert.ok(bore < clearance, "the interface decides the tolerance, which decides the instrument");
});

test("the envelope and every interface are blocking; cosmetics are not", () => {
  const tasks = buildTasks([FACE, BORE, DOWEL, CLEARANCE], true, []);
  for (const label of ["Overall X", "Overall Y", "Overall Z"]) {
    assert.equal(tasks.find((t) => t.label === label)?.blocking, true, `${label} must block`);
  }
  assert.equal(tasks.find((t) => t.featureId === "f-bore")?.blocking, true);
});

test("order is dense and starts at one", () => {
  const tasks = buildTasks([FACE, BORE, DOWEL, CLEARANCE], true, []);
  tasks.forEach((t, i) => {
    assert.equal(t.order, i + 1, "order must be the position in the list");
    assert.equal(t.id, `task-${i + 1}`);
  });
});

test("nextTask returns a blocking item ahead of a non-blocking one", () => {
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS, establishedDatums: DESIGN_FRAME }));
  const next = nextTask(plan);
  assert.ok(next);
  assert.equal(next.blocking, true, "there are blocking items outstanding");
});

test("nextTask returns null only when nothing is left", () => {
  const plan = buildReconstructionPlan(input({ features: [], uploadedViews: ALL_VIEWS }));
  const labels = plan.tasks.map((t) => t.label);
  const done = buildReconstructionPlan(
    input({ features: [], uploadedViews: ALL_VIEWS, completedLabels: labels }),
  );
  assert.equal(done.measurementsComplete, done.measurementsRequired);
  assert.equal(nextTask(done), null);
});

/* ---------------- Datums are not assumed ---------------- */

test("no dimension is referenced to a datum that has not been established", () => {
  // The hole-pattern task hardcoded datum C, so the plan instructed a
  // measurement from a reference frame nobody had set — the exact error its
  // own instruction text warns about.
  const tasks = buildTasks([BORE, DOWEL, CLEARANCE], false, []);
  for (const t of tasks) {
    if (t.label.startsWith("Overall Z")) continue; // datum A is the seating face by definition
    assert.equal(t.datumLetter, null, `${t.label} references datum ${t.datumLetter} before it exists`);
  }
});

test("once the frame is established the dimensions are referenced to it", () => {
  const tasks = buildTasks([BORE, DOWEL, CLEARANCE], true, []);
  assert.equal(tasks.find((t) => t.featureId === "f-bore")?.datumLetter, "B");
  assert.ok(
    tasks.some((t) => t.context === "HOLE" && t.datumLetter === "C"),
    "the hole pattern is measured from C",
  );
});

test("an unestablished design frame is named in blockedBy", () => {
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS }));
  assert.ok(plan.blockedBy.some((b) => /datum A, B, C not established/i.test(b)), plan.blockedBy.join(" | "));
});

test("a partially established frame names only what is outstanding", () => {
  const plan = buildReconstructionPlan(
    input({ uploadedViews: ALL_VIEWS, establishedDatums: [{ system: "DESIGN", letter: "A" }] }),
  );
  const datum = plan.blockedBy.find((b) => /datum/i.test(b));
  assert.ok(datum, "the frame is still incomplete");
  assert.match(datum, /B, C/);
  assert.ok(!/A,/.test(datum), "A is established and must not be listed");
});

/* ---------------- The datum proposal ---------------- */

test("the design frame is a plane, then an axis, then a point", () => {
  const design = proposeDatums([FACE, BORE, DOWEL]).filter((d) => d.system === "DESIGN");
  assert.deepEqual(design.map((d) => d.letter), ["A", "B", "C"]);
  assert.deepEqual(design.map((d) => d.geometryType), ["PLANE", "AXIS", "POINT"]);
});

test("with no features the datums are proposed without a feature behind them", () => {
  // The proposal is still useful — it says what KIND of thing to pick — but
  // it must not invent a feature id it does not have.
  const proposals = proposeDatums([]);
  assert.ok(proposals.length > 0);
  for (const p of proposals) {
    assert.equal(p.featureId, null, `${p.system}:${p.letter} invented a feature`);
    assert.ok(p.reason.length > 40, `${p.system}:${p.letter} proposes without reasoning`);
  }
});

test("every proposal carries a reason a machinist can disagree with", () => {
  for (const p of proposeDatums([FACE, BORE, DOWEL])) {
    assert.ok(p.reason.length > 40, `${p.system}:${p.letter}`);
    assert.ok(DATUM_SYSTEMS.includes(p.system));
  }
});

test("all three datum systems are proposed, because they are not the same thing", () => {
  const systems = new Set(proposeDatums([FACE, BORE, DOWEL]).map((p) => p.system));
  for (const s of DATUM_SYSTEMS) assert.ok(systems.has(s), `${s} datum is never proposed`);
});

/* ---------------- Completion ---------------- */

test("two features sharing a label do not both complete from one measurement", () => {
  // Castings routinely carry two features a shop calls the same thing. A Set
  // marked every one of them complete as soon as any one was measured, which
  // reports an unmeasured feature as measured on a job whose entire purpose
  // is to measure them.
  const a = feature({ id: "b1", label: "Bore", kind: "BORE", functionalRole: "BEARING_SEAT", critical: true });
  const b = feature({ id: "b2", label: "Bore", kind: "BORE", functionalRole: "BEARING_SEAT", critical: true });
  const tasks = buildTasks([a, b], true, ["Bore"]);
  const bores = tasks.filter((t) => t.label === "Bore");
  assert.equal(bores.length, 2, "precondition: two tasks share the label");
  assert.equal(bores.filter((t) => t.complete).length, 1, "one measurement satisfies one task");
});

test("two recorded measurements complete two tasks", () => {
  const a = feature({ id: "b1", label: "Bore", kind: "BORE", functionalRole: "BEARING_SEAT", critical: true });
  const b = feature({ id: "b2", label: "Bore", kind: "BORE", functionalRole: "BEARING_SEAT", critical: true });
  const tasks = buildTasks([a, b], true, ["Bore", "Bore"]);
  assert.equal(tasks.filter((t) => t.label === "Bore" && t.complete).length, 2);
});

test("completion matching ignores case but not identity", () => {
  const tasks = buildTasks([], true, ["overall x"]);
  assert.equal(tasks.find((t) => t.label === "Overall X")?.complete, true);
  assert.equal(tasks.find((t) => t.label === "Overall Y")?.complete, false);
});

test("a measurement recorded for nothing in the plan completes nothing", () => {
  const tasks = buildTasks([], true, ["Some other thing entirely"]);
  assert.equal(tasks.filter((t) => t.complete).length, 0);
});

/* ---------------- Views ---------------- */

test("missing views are named, and no photographs is stated differently from some", () => {
  const none = buildReconstructionPlan(input({ uploadedViews: [] }));
  assert.equal(none.missingViews.length, 6);
  assert.ok(none.blockedBy.some((b) => /has not been photographed/i.test(b)));

  const some = buildReconstructionPlan(input({ uploadedViews: ["TOP", "front"] }));
  assert.equal(some.missingViews.length, 4, "view labels are matched case-insensitively");
  assert.ok(some.blockedBy.some((b) => /4 of the six required views/i.test(b)));
});

test("a fully photographed part is not blocked on views", () => {
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS }));
  assert.ok(!plan.blockedBy.some((b) => /view/i.test(b)));
});

/* ---------------- Inferred readings ---------------- */

test("a reading matched to a standard blocks until a human rules on it", () => {
  // AI or table inference does not satisfy anything on its own.
  const plan = buildReconstructionPlan(
    input({ uploadedViews: ALL_VIEWS, establishedDatums: DESIGN_FRAME, inferredAwaitingReview: 3 }),
  );
  assert.ok(plan.blockedBy.some((b) => /awaiting a human decision/i.test(b)), plan.blockedBy.join(" | "));
  assert.match(plan.headline, /3 inferred features require review/);
});

test("one inferred reading reads as one, not as '1 features'", () => {
  const plan = buildReconstructionPlan(input({ uploadedViews: ALL_VIEWS, inferredAwaitingReview: 1 }));
  assert.match(plan.headline, /1 inferred feature requires review/);
  assert.ok(plan.blockedBy.some((b) => /1 reading matched/.test(b)));
});

test("a fully evidenced plan is blocked by nothing", () => {
  const plan = buildReconstructionPlan(
    input({ uploadedViews: ALL_VIEWS, establishedDatums: DESIGN_FRAME, inferredAwaitingReview: 0 }),
  );
  assert.deepEqual(plan.blockedBy, []);
});

/* ---------------- Counts are counts ---------------- */

test("the plan's counts match its own lists", () => {
  const plan = buildReconstructionPlan(
    input({ uploadedViews: ["TOP"], completedLabels: ["Overall X"], inferredAwaitingReview: 2 }),
  );
  assert.equal(plan.measurementsRequired, plan.tasks.length);
  assert.equal(plan.measurementsComplete, plan.tasks.filter((t) => t.complete).length);
  assert.equal(plan.datumsRequired, plan.datumProposals.length);
  assert.ok(plan.datumsEstablished <= plan.datumsRequired);
  assert.match(plan.headline, new RegExp(`^${plan.tasks.length} measurements required`));
});

test("the plan is deterministic", () => {
  const i = input({ uploadedViews: ["TOP", "LEFT"], establishedDatums: [{ system: "DESIGN", letter: "A" }] });
  assert.deepEqual(buildReconstructionPlan(i), buildReconstructionPlan(i));
});
