import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { assessCoverage, coverageVerdict, type CoverageOperation } from "@/lib/engines/coverage";
import { evaluateReadiness } from "@/lib/engines/readiness";
import type { Feature } from "@/lib/domain/features";
import { emptyPartIntent } from "@/lib/domain/part-intent";

/**
 * FEATURE COVERAGE
 *
 * The failure this engine exists to catch: a feature no operation is planned
 * against is not refused anywhere. The post writes the program, the program
 * runs start to finish, and the part comes off the machine without its bore.
 * An absence is the one thing no inspection method in this system measures.
 */

const feat = (id: string, label: string, over: Partial<Feature> = {}): Feature =>
  ({
    id,
    kind: "DRILLED_HOLE",
    label,
    functionalRole: "NONE",
    critical: false,
    diameter: 0.25,
    centerX: 0,
    centerY: 0,
    depth: 0.5,
    through: true,
    ...over,
  }) as unknown as Feature;

const op = (id: string, featureId: string | null, label = `op ${id}`): CoverageOperation => ({ id, label, featureId });

/* ---------------- The engine ---------------- */

test("a feature with an operation is cut", () => {
  const r = assessCoverage([feat("f1", "1.000 bore")], [op("o1", "f1", "Bore 1.000")]);
  assert.equal(r.cut.length, 1);
  assert.equal(r.uncut.length, 0);
  assert.deepEqual(r.cut[0].operationLabels, ["Bore 1.000"]);
});

test("a feature with no operation is uncut, and named", () => {
  const r = assessCoverage([feat("f1", "1.000 bore"), feat("f2", "M6 tapped hole")], [op("o1", "f1")]);
  assert.equal(r.uncut.length, 1);
  assert.equal(r.uncut[0].label, "M6 tapped hole");
  const v = coverageVerdict(r);
  assert.equal(v.ok, false);
  assert.match(v.detail, /M6 tapped hole/);
  // The consequence, not just the count. An operator who reads "1 of 2
  // features have no operation" and nothing else does not know what happens.
  assert.match(v.detail, /runs to completion without cutting them/i);
});

test("an operation with no feature covers nothing", () => {
  // Facing the stock top is a real operation against no named feature. It
  // must not be counted as covering the bore that shares its setup.
  const r = assessCoverage([feat("f1", "1.000 bore")], [op("o1", null, "Face top")]);
  assert.equal(r.uncut.length, 1);
  assert.equal(coverageVerdict(r).ok, false);
});

test("a stated reason accounts for a feature, and the verdict repeats it", () => {
  const r = assessCoverage(
    [feat("f1", "1.000 bore"), feat("f2", "0.02 x 45 chamfer", { notMachinedReason: "broken at the bench" })],
    [op("o1", "f1")],
  );
  assert.equal(r.accountedFor.length, 1);
  assert.equal(r.uncut.length, 0);
  const v = coverageVerdict(r);
  assert.equal(v.ok, true);
  // Passing is not the same as going quiet. The sentence has to survive into
  // the gate's detail, because somebody at the bench still has to do it.
  assert.match(v.detail, /0\.02 x 45 chamfer — broken at the bench/);
});

test("a blank reason is not a reason", () => {
  const r = assessCoverage([feat("f1", "bore", { notMachinedReason: "   " })], [op("o1", null)]);
  assert.equal(r.uncut.length, 1, "whitespace accounted for a feature nobody accounted for");
  assert.equal(r.accountedFor.length, 0);
});

test("an operation beats a stated reason", () => {
  // Both recorded: somebody planned it after saying it was hand work. The
  // program cuts it, so CUT is the true statement about this program.
  const r = assessCoverage([feat("f1", "chamfer", { notMachinedReason: "hand deburr" })], [op("o1", "f1")]);
  assert.equal(r.cut.length, 1);
  assert.equal(r.accountedFor.length, 0);
});

test("no operations at all is not a coverage failure, it is an unwritten plan", () => {
  const r = assessCoverage([feat("f1", "bore")], []);
  assert.equal(r.planned, false);
  const v = coverageVerdict(r);
  assert.equal(v.ok, false);
  assert.match(v.detail, /No operations are planned/);
});

test("no features means there is nothing to cut", () => {
  const r = assessCoverage([], [op("o1", null)]);
  assert.equal(r.planned, false);
  assert.match(coverageVerdict(r).detail, /No features are defined/);
});

test("the verdict names at most three and counts the rest", () => {
  const features = ["a", "b", "c", "d", "e"].map((k) => feat(k, `feature ${k}`));
  const v = coverageVerdict(assessCoverage(features, [op("o1", "a")]));
  assert.match(v.detail, /and 1 more/);
  assert.equal(v.detail.includes("feature e"), false, "listed every feature rather than summarising");
});

/* ---------------- The readiness gate ---------------- */

const readiness = (features: Feature[], operations?: CoverageOperation[]) =>
  evaluateReadiness({
    intent: emptyPartIntent("Coverage test part"),
    stock: { form: "RECTANGULAR", x: 3, y: 3, z: 1, material: "Aluminum 6061" },
    features,
    machine: null,
    tools: [],
    workholding: null,
    workholdingAssessment: null,
    hasInspectionPlan: false,
    operations,
    simulationRun: false,
    ncGenerated: false,
    operatorApproved: false,
  }).gates.find((g) => g.id === "coverage")!;

test("the coverage gate is blocking", () => {
  assert.equal(readiness([feat("f1", "bore")], [op("o1", "f1")]).blocking, true);
});

test("an uncut feature makes the gate MISSING", () => {
  const g = readiness([feat("f1", "bore"), feat("f2", "slot")], [op("o1", "f1")]);
  assert.equal(g.status, "MISSING");
  assert.match(g.detail, /slot/);
  // Both answers are offered. A gate that only says "add an operation" cannot
  // be cleared on a part with a fillet, and gets routed around.
  assert.ok(g.actions.some((a) => /operation/i.test(a)));
  assert.ok(g.actions.some((a) => /not made by this program/i.test(a)));
});

test("an unwritten plan reads NOT_ATTEMPTED, not MISSING", () => {
  // MISSING says a check ran and found a gap. Nothing has been planned yet,
  // and saying "2 features have no operation" about a part nobody has
  // programmed is a true sentence that misdescribes the situation.
  assert.equal(readiness([feat("f1", "bore")], []).status, "NOT_ATTEMPTED");
});

test("a caller with no plan data gets a gate that says it did not run", () => {
  const g = readiness([feat("f1", "bore")], undefined);
  assert.equal(g.status, "NOT_ATTEMPTED");
  assert.match(g.detail, /not available/i);
  // Still blocking. Coverage nobody checked is not coverage.
  assert.equal(g.blocking, true);
});

test("full coverage passes", () => {
  assert.equal(readiness([feat("f1", "bore")], [op("o1", "f1")]).status, "PASS");
});

/* ---------------- The two gates cannot disagree ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("readiness and the export pre-flight decide coverage in the same place", () => {
  // The lesson this codebase already learned once, in preflight.ts's own
  // header: if the gate logic exists in two places, it does not exist.
  const pre = strip(readFileSync("src/lib/engines/cam/preflight.ts", "utf8"));
  const rdy = strip(readFileSync("src/lib/engines/readiness.ts", "utf8"));
  for (const [file, src] of [["preflight", pre], ["readiness", rdy]] as const) {
    assert.ok(/coverageVerdict\(/.test(src), `${file} decides coverage without the shared verdict`);
    assert.ok(/assessCoverage\(/.test(src), `${file} assesses coverage without the shared engine`);
  }
});

test("the export pre-flight item is required", () => {
  const pre = strip(readFileSync("src/lib/engines/cam/preflight.ts", "utf8"));
  // A false here is an advisory item, and an advisory coverage item lets a
  // program that never cuts the bore out of the building.
  assert.ok(
    /item\("coverage", "Every feature is cut", verdict\.ok, verdict\.detail, true\)/.test(pre),
    "the coverage pre-flight item is not required",
  );
});

/* ---------------- The control that answers the gate ---------------- */

test("recording that a feature is not machined is scoped to the session's organisation", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/not-machined-actions.ts", "utf8"));
  // Principle 13: the organisation comes from the session, never from the
  // request. A server action is a POST endpoint, so the feature id in the form
  // proves nothing about who may write to it.
  assert.ok(/const user = await requireWrite\(\)/.test(src), "the action does not establish a writer");
  assert.ok(
    /partRevision: \{ part: \{ id: partId, organizationId: user\.organizationId \} \}/.test(src),
    "the feature is not re-checked against the session's organisation before the write",
  );
});

test("an empty box clears the reason rather than storing an empty one", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/not-machined-actions.ts", "utf8"));
  // assessCoverage() treats blank as unaccounted-for. If the action stored an
  // empty string instead of clearing, the row and the gate would still agree —
  // but the name and timestamp of a decision nobody made would survive on it.
  assert.ok(/const clearing = reason === ""/.test(src), "blank is not treated as a clear");
  assert.ok(
    /notMachinedReason: null, notMachinedBy: null, notMachinedAt: null/.test(src),
    "clearing leaves the recorder's name on a reason that is gone",
  );
});

test("the decision is recorded as a human act", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/not-machined-actions.ts", "utf8"));
  // Principle 13 again: the actor is typed, never inferred. This one is always
  // HUMAN because nothing else is allowed to make this call.
  assert.ok(/actorType: "HUMAN"/.test(src), "the audit row does not type the actor");
  assert.ok(/notMachinedBy: user\.name/.test(src), "the reason does not carry who stated it");
});
