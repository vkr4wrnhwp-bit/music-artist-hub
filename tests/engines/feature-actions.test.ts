import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { featureActions } from "@/components/workspace/feature-actions";
import type { Feature } from "@/lib/domain/features";
import type { FeatureDetail, RunwayOperation } from "@/components/workspace/panel-data";

/**
 * DETAIL / MEASURE / MAKE / VERIFY on a feature.
 *
 * MAKE is the one that did not exist anywhere. A machinist who selected a
 * bore could not get from it to the operation that cuts it without reading
 * the runway table and matching labels by eye.
 */

const feature = (over: Partial<Feature> = {}): Feature =>
  ({ id: "f1", kind: "BORE", label: "40 mm bearing bore", functionalRole: null, critical: false, ...over }) as Feature;

const op = (over: Partial<RunwayOperation> = {}): RunwayOperation =>
  ({
    id: "o1",
    setupId: "s1",
    sequence: 10,
    label: "Bore",
    type: "BORE",
    toolNumber: 4,
    toolDescription: "Boring bar",
    featureId: "f1",
    featureLabel: "40 mm bearing bore",
    cycleMinutes: 1.25,
    moveCount: 40,
    isPlaceholder: false,
    error: null,
    ...over,
  }) as RunwayOperation;

const base = { detail: undefined, operations: [], inspectionSessionId: null };

test("MAKE names the operation that cuts the feature", () => {
  const a = featureActions({ ...base, feature: feature(), operations: [op()] });
  assert.equal(a.make.available, true);
  assert.match((a.make as { detail: string }).detail, /Op 10/);
  assert.match((a.make as { detail: string }).detail, /T4/);
});

test("a feature nothing cuts says so, rather than showing some other operation", () => {
  // The bug this exists to prevent is "just show the first op in the plan",
  // which would tell a machinist a feature is cut when it is not.
  const a = featureActions({ ...base, feature: feature(), operations: [op({ featureId: "f-other" })] });
  assert.equal(a.make.available, false);
  assert.match((a.make as { reason: string }).reason, /No operation in the plan cuts this feature/);
});

test("the FIRST operation by sequence, whatever order they arrive in", () => {
  const a = featureActions({
    ...base,
    feature: feature(),
    operations: [op({ id: "o3", sequence: 30, toolNumber: 9 }), op({ id: "o2", sequence: 20, toolNumber: 7 })],
  });
  assert.match((a.make as { detail: string }).detail, /Op 20/);
  assert.match((a.make as { detail: string }).detail, /T7/);
});

test("a placeholder operation quotes no cycle time", () => {
  // isPlaceholder means the CAM engine has no implementation for that type.
  // There is no motion, so there is no time — printing one would be quoting a
  // figure for a toolpath that does not exist.
  const a = featureActions({ ...base, feature: feature(), operations: [op({ isPlaceholder: true, cycleMinutes: 3.4 })] });
  const detail = (a.make as { detail: string }).detail;
  assert.match(detail, /no toolpath/);
  assert.ok(!/min/.test(detail), `a cycle time was quoted for an operation with no toolpath: ${detail}`);
});

test("an operation the engine refused carries its reason verbatim", () => {
  const a = featureActions({
    ...base,
    feature: feature(),
    operations: [op({ error: "no tool small enough for the corner radius" })],
  });
  assert.match((a.make as { detail: string }).detail, /no tool small enough for the corner radius/);
});

test("MEASURE is offered only where there is something to measure against", () => {
  // A feature with no tolerance, no critical flag and no stated method is not
  // an inspection characteristic; offering to measure it invents a
  // requirement nobody set.
  const plain = featureActions({ ...base, feature: feature() });
  assert.equal(plain.measure.available, false);
  assert.match((plain.measure as { reason: string }).reason, /Not an inspection characteristic/);

  for (const over of [{ critical: true }, { tolerance: { plus: 0.001, minus: 0 } }, { inspectionMethod: "CMM" }]) {
    const a = featureActions({ ...base, feature: feature(over as Partial<Feature>) });
    assert.equal(a.measure.available, true, `${JSON.stringify(over)} should be measurable`);
  }
});

test("MEASURE says whether a session is already open", () => {
  const closed = featureActions({ ...base, feature: feature({ critical: true }) });
  assert.match((closed.measure as { detail: string }).detail, /Start a session/);
  const open = featureActions({ ...base, feature: feature({ critical: true }), inspectionSessionId: "sess1" });
  assert.match((open.measure as { detail: string }).detail, /Session open/);
});

test("VERIFY reports the measured state in the words the panel uses", () => {
  const detail = { verify: { state: "NONCONFORMS", reason: null, departure: 0.0004 }, capability: null } as FeatureDetail;
  const a = featureActions({ ...base, feature: feature({ critical: true }), detail });
  assert.equal((a.verify as { detail: string }).detail, "Does not conform");
});

test("DETAIL is always there — a feature always has something to say about itself", () => {
  assert.equal(featureActions({ ...base, feature: feature() }).detail.available, true);
});

/* ---- the lens states all four, and stays untouchable ---- */

test("every action reaches the lens", () => {
  // A fifth action could otherwise be declared and silently never rendered.
  const src = readFileSync("src/components/workspace/feature-lens.tsx", "utf8");
  for (const key of ["detail", "measure", "make", "verify"]) {
    assert.ok(new RegExp(`actions\\.${key}`).test(src), `the lens never renders ${key}`);
  }
});

test("the lens is still not a control", () => {
  // It is pointer-events-none and follows the cursor. A form on hover is a
  // trap: the cursor has to travel across the part to reach it, and passing
  // over other geometry changes what the form is about.
  const src = readFileSync("src/components/workspace/feature-lens.tsx", "utf8");
  for (const interactive of ["<button", "onClick=", "href="]) {
    assert.ok(!src.includes(interactive), `the lens gained ${interactive} — a hover surface must not be clickable`);
  }
  assert.ok(/pointer-events-none/.test(src), "the lens can now intercept the pointer");
});

test("the lens states four independent facts, never a tally", () => {
  // Four cells side by side invite a count or a colour ramp. Readiness is not
  // a score anywhere in this product, and neither is this.
  // Comments stripped: a note explaining the rule is not the rule, and this
  // file's own comment says the word "score" while forbidding it.
  const src = readFileSync("src/components/workspace/feature-lens.tsx", "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
  assert.ok(!/\d\s*of\s*4|of 4 ready|score/i.test(src), "the lens aggregates the four actions into a figure");
});
