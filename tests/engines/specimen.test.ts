import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  SPECIMEN_TABS,
  SPECIMEN_TAB_LABEL,
  deviationIsResolvable,
  specimenDimensions,
  viewsFor,
  type MeasuredValue,
} from "@/lib/engines/specimen";
import { FEATURE_KINDS, type Feature } from "@/lib/domain/features";

/**
 * "When the user selects a feature: isolate it, enlarge it, allow rotation,
 * show dimension lines, show nominal vs measured, show tabs."
 *
 * Nothing rendered a specimen. The only trace was a `specimenMode` boolean and
 * a SPECIMEN action in the interaction reducer with no consumers at all.
 */

const bore = {
  id: "f1", kind: "BORE", label: "40 mm bearing bore", functionalRole: "BEARING_SEAT", critical: true,
  centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.75, bottomRadius: 0, top: 0, through: false,
} as unknown as Feature;

const reading = (field: string, value: number, uncertainty = 0.0005): MeasuredValue => ({
  field, value, uncertainty, at: new Date("2026-01-01T00:00:00Z"),
});

test("the dimensions are the ones this kind of feature actually carries", () => {
  // From the same field spec the entry form and the proposal path validate
  // against, so a specimen cannot show a dimension the feature lacks.
  const rows = specimenDimensions(bore, null, []);
  const labels = rows.map((r) => r.label);
  assert.ok(labels.includes("Diameter"));
  assert.ok(labels.includes("Depth"));
  assert.ok(!labels.includes("Width, X"), "a rectangular pocket's dimension appeared on a bore");
});

test("nothing measured leaves the measured side empty, never the nominal repeated", () => {
  // A comparison with one side missing is not a comparison, and repeating the
  // nominal would read as a part that measured exactly on size.
  const rows = specimenDimensions(bore, { plus: 0.0005, minus: 0.0005 }, []);
  for (const r of rows) {
    assert.equal(r.measured, null, `${r.label} invented a measurement`);
    assert.equal(r.deviation, null);
    assert.equal(r.verdict, "NOT_MEASURED");
  }
});

test("a measurement produces a deviation and a verdict against the feature's own band", () => {
  const rows = specimenDimensions(bore, { plus: 0.0005, minus: 0.0005 }, [reading("diameter", 1.5751)]);
  const dia = rows.find((r) => r.label === "Diameter")!;
  assert.ok(Math.abs(dia.deviation! - 0.0003) < 1e-9, `deviation was ${dia.deviation}`);
  assert.equal(dia.verdict, "IN_TOLERANCE");

  const out = specimenDimensions(bore, { plus: 0.0005, minus: 0.0005 }, [reading("diameter", 1.5760)]);
  assert.equal(out.find((r) => r.label === "Diameter")!.verdict, "OUT_OF_TOLERANCE");
});

test("an asymmetric band is respected in both directions", () => {
  const tol = { plus: 0.0010, minus: 0.0002 };
  const over = specimenDimensions(bore, tol, [reading("diameter", 1.5756)]);
  assert.equal(over.find((r) => r.label === "Diameter")!.verdict, "IN_TOLERANCE", "+0.0008 was rejected against a +0.0010 band");
  const under = specimenDimensions(bore, tol, [reading("diameter", 1.5744)]);
  assert.equal(under.find((r) => r.label === "Diameter")!.verdict, "OUT_OF_TOLERANCE", "-0.0004 was accepted against a -0.0002 band");
});

test("a measurement with no tolerance stated says so rather than passing", () => {
  const rows = specimenDimensions(bore, null, [reading("diameter", 1.5760)]);
  assert.equal(rows.find((r) => r.label === "Diameter")!.verdict, "NO_TOLERANCE_STATED");
});

test("a deviation inside the instrument's own uncertainty is flagged as unresolvable", () => {
  // 0.0002" read with a ±0.0005" caliper is the instrument, not the part.
  // Saying otherwise sends somebody chasing a dimension that was never out.
  assert.equal(deviationIsResolvable(0.0002, 0.0005), false);
  assert.equal(deviationIsResolvable(0.0012, 0.0005), true);
  assert.equal(deviationIsResolvable(-0.0012, 0.0005), true, "a negative deviation was read as smaller than it is");
  assert.equal(deviationIsResolvable(null, 0.0005), null);
  assert.equal(deviationIsResolvable(0.001, null), null);
});

test("a reading of a dimension this feature does not carry is not attached to another", () => {
  const rows = specimenDimensions(bore, null, [reading("width", 2)]);
  assert.ok(rows.every((r) => r.measured === null), "a width reading was attached to a bore's dimensions");
});

test("a section is offered only where it is a different drawing", () => {
  // Sectioning a chamfer produces the plan again. Offering the view and
  // drawing nothing new is a control that does nothing.
  assert.deepEqual(viewsFor("BORE"), ["PLAN", "SECTION"]);
  assert.deepEqual(viewsFor("RECT_POCKET"), ["PLAN", "SECTION"]);
  assert.deepEqual(viewsFor("BOSS"), ["PLAN", "SECTION"]);
  assert.deepEqual(viewsFor("CHAMFER"), ["PLAN"]);
  assert.deepEqual(viewsFor("FILLET"), ["PLAN"]);
});

test("every feature kind gets at least one view", () => {
  for (const k of FEATURE_KINDS) {
    assert.ok(viewsFor(k).length >= 1, `${k} has no view at all`);
  }
});

test("all six tabs the brief names exist and are labelled", () => {
  assert.deepEqual([...SPECIMEN_TABS], ["GEOMETRY", "FUNCTION", "MEASURE", "MACHINE", "INSPECT", "HISTORY"]);
  for (const t of SPECIMEN_TABS) assert.ok(SPECIMEN_TAB_LABEL[t], `${t} has no label`);
});

/* ---- the drawing, and the dead flag ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the specimen draws the feature alone, not the part with a dot on it", () => {
  const src = strip(readFileSync("src/components/feature-specimen.tsx", "utf8"));
  // Dimension lines with the value on them are what makes it a drawing.
  assert.match(src, /function Dim\(/);
  assert.match(src, /markerStart="url\(#a\)" markerEnd="url\(#a\)"/, "the dimension line has no arrows");
  // And it does not draw the stock outline the thumbnail draws.
  assert.ok(!/stock/i.test(src), "the specimen draws the stock — it is supposed to be isolated");
});

test("the drawing shows measured beside nominal, and marks an out-of-tolerance one", () => {
  const src = strip(readFileSync("src/components/feature-specimen.tsx", "utf8"));
  assert.match(src, /meas/, "the drawing never shows the measured value");
  assert.match(src, /OUT_OF_TOLERANCE" \? RED : INK/, "an out-of-tolerance dimension is not marked");
});

test("a kind with no specimen drawing says so rather than drawing a box", () => {
  const src = strip(readFileSync("src/components/feature-specimen.tsx", "utf8"));
  assert.match(src, /no specimen drawing for/);
});

test("the drawing never claims a scale it does not have", () => {
  const src = readFileSync("src/components/feature-specimen.tsx", "utf8");
  assert.match(src, /not to scale/);
});

test("the dead specimenMode flag is gone rather than left as a decoy", () => {
  // It was a boolean on the interaction reducer with a SPECIMEN action and a
  // setSpecimen dispatcher, read by nothing — the "inactive UI control" the
  // brief prohibits. The specimen turned out to be a page, not a mode.
  const src = readFileSync("src/components/workspace/interaction.tsx", "utf8");
  const code = strip(src);
  assert.ok(!/specimenMode/.test(code), "specimenMode is still on the reducer with nothing reading it");
  assert.ok(!/"SPECIMEN"/.test(code), "the SPECIMEN action is still dispatchable and does nothing");
  assert.ok(!/setSpecimen/.test(code), "setSpecimen is still exposed");
  // And the comment explaining why it went is kept, so it is not re-added.
  // Normalised first: a comment wraps, and matching a phrase across the wrap
  // is a test that fails on formatting rather than on meaning.
  const prose = src.replace(/\s*\n\s*\*\s*/g, " ").replace(/\s+/g, " ");
  assert.match(prose, /turned out not to be a workspace mode/);
  assert.match(prose, /inactive UI control/);
});

test("the feature panel opens the specimen", () => {
  const src = readFileSync("src/components/workspace/feature-panel.tsx", "utf8");
  assert.match(src, /tab=GEOMETRY/);
  assert.match(src, /Open the specimen/);
});

test("the page renders exactly one tab at a time, and every tab has content", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/features/[fid]/page.tsx", "utf8");
  for (const t of SPECIMEN_TABS) {
    assert.ok(new RegExp(`tab === "${t}"`).test(src), `${t} is a tab with nothing behind it`);
  }
});

test("no tab is ever blank", () => {
  // MEASURE rendered nothing at all when a feature had no nominal analysis —
  // a tab in the strip that opens onto an empty page.
  const src = readFileSync("src/app/(app)/parts/[id]/features/[fid]/page.tsx", "utf8");
  assert.match(src, /tab === "MEASURE" && !analysis && \(/, "MEASURE is blank for a feature with no analysis");
});

test("an unknown tab or view falls back rather than rendering nothing", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/features/[fid]/page.tsx", "utf8");
  assert.match(src, /SPECIMEN_TABS as readonly string\[\]\)\.includes\(tabRaw \?\? ""\)/);
  assert.match(src, /views\.includes\(viewRaw as SpecimenView\) \? \(viewRaw as SpecimenView\) : views\[0\]/);
});
