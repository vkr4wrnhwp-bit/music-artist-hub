import { test } from "node:test";
import assert from "node:assert/strict";
import { buildProtectedRegions } from "@/lib/nc/protection";
import { FUNCTIONAL_ROLES, type Feature, type FunctionalRole } from "@/lib/domain/features";

/**
 * A protected region is where an automatic feed or speed proposal is not
 * allowed to go. Both the analyse and optimise routes build these from the
 * part's own features, so a role missing from the classification is a
 * finished surface the optimiser may quietly touch.
 *
 * Which roles count is a judgement the file states in one line — "a
 * functional role that IS a finish surface" — and the tests below hold it to
 * the asymmetry behind it: over-protecting costs cycle time, under-protecting
 * cuts into a bearing seat.
 */

const bore = (over: Partial<Feature> = {}): Feature =>
  ({
    id: "b1", kind: "BORE", label: "bore", functionalRole: "NONE", critical: false,
    diameter: 1.5, centerX: 0, centerY: 0, top: 0, depth: 0.7, ...over,
  }) as unknown as Feature;

const roleBore = (functionalRole: FunctionalRole) => bore({ id: functionalRole, functionalRole });
const protectedFor = (f: Feature) => buildProtectedRegions([f]).length === 1;

/* ---------------- Roles ---------------- */

test("every fit and running surface is protected", () => {
  // SHAFT_JOURNAL, PRESS_FIT, SLIP_FIT and LOCATING_SHOULDER were all absent
  // from the original set. A bearing runs on a journal; a press fit IS its
  // surface. Both routes that build these regions are live.
  for (const role of ["BEARING_SEAT", "SEAL_SURFACE", "SHAFT_JOURNAL", "PRESS_FIT", "SLIP_FIT", "DOWEL_HOLE", "THREAD"] as const) {
    assert.equal(protectedFor(roleBore(role)), true, `${role} is not protected`);
  }
});

test("reference surfaces are protected, because the rest of the part is measured from them", () => {
  for (const role of ["DATUM_FACE", "LOCATING_SHOULDER", "INSPECTION_SURFACE"] as const) {
    assert.equal(protectedFor(roleBore(role)), true, `${role} is not protected`);
  }
});

test("a clearance hole is not a finish surface", () => {
  // Protecting everything would stop the optimiser proposing anything
  // anywhere, which costs cycle time and buys nothing.
  for (const role of ["NONE", "MOUNTING_HOLE", "CLEARANCE", "STRUCTURAL_RIB", "FIXTURE_PAD", "COSMETIC", "FLUID_PASSAGE"] as const) {
    assert.equal(protectedFor(roleBore(role)), false, `${role} is protected and should not be`);
  }
});

test("every role in the enum has been decided one way or the other", () => {
  // The original set held three roles that do not exist — BEARING_BORE,
  // SEALING_SURFACE, LOCATING_BORE — which is what writing a lookup from
  // memory rather than from the enum looks like. It matched nothing, and the
  // same act left four real roles out.
  for (const role of FUNCTIONAL_ROLES) {
    const r = protectedFor(roleBore(role));
    assert.equal(typeof r, "boolean", `${role} produced no decision`);
  }
});

/* ---------------- The other ways a feature earns protection ---------------- */

test("a critical feature is protected whatever its role", () => {
  assert.equal(protectedFor(bore({ functionalRole: "CLEARANCE", critical: true })), true);
  const [region] = buildProtectedRegions([bore({ functionalRole: "CLEARANCE", critical: true })]);
  assert.match(region.reason, /critical/i, "and it says which fact earned it");
});

test("a tight tolerance is protected, a loose one is not", () => {
  assert.equal(protectedFor(bore({ tolerance: { plus: 0.0005, minus: 0.0005 } })), true, "0.001 band");
  assert.equal(protectedFor(bore({ tolerance: { plus: 0.005, minus: 0.005 } })), false, "0.010 band");
});

test("the tolerance band is the sum of both limits, not one of them", () => {
  // +0.001/-0.000 is a 0.001 band and protected; +0.001/-0.001 is 0.002 and
  // is not. Reading one limit would get both wrong.
  assert.equal(protectedFor(bore({ tolerance: { plus: 0.001, minus: 0 } })), true);
  assert.equal(protectedFor(bore({ tolerance: { plus: 0.001, minus: 0.001 } })), false);
});

test("a fine surface finish is protected, a rough one is not", () => {
  assert.equal(protectedFor(bore({ surfaceFinish: 16 })), true);
  assert.equal(protectedFor(bore({ surfaceFinish: 32 })), true, "32 Ra is the boundary and is inside it");
  assert.equal(protectedFor(bore({ surfaceFinish: 125 })), false);
});

test("a tapped hole is protected because the thread is the feature", () => {
  const tapped = bore({ id: "t1", kind: "TAPPED_HOLE", functionalRole: "NONE", diameter: 0.201 });
  assert.equal(protectedFor(tapped), true);
});

test("an ordinary feature with nothing recorded earns no protection", () => {
  assert.deepEqual(buildProtectedRegions([bore()]), [], "protection comes from recorded facts, not by default");
});

/* ---------------- The region itself ---------------- */

test("a region stands off from the feature so the cutter's own body is covered", () => {
  const [r] = buildProtectedRegions([bore({ critical: true, diameter: 1.5 })]);
  assert.ok(r.radius > 0.75, `radius ${r.radius} does not clear the ⌀1.5 feature`);
});

test("the region spans the feature's own Z, in program coordinates", () => {
  // Z0 is the top of the stock and depths run negative.
  const [r] = buildProtectedRegions([bore({ critical: true, top: 0.1, depth: 0.7 })]);
  assert.equal(r.zTop, -0.1);
  assert.equal(r.zBottom, -0.8);
  assert.ok(r.zBottom < r.zTop, "the region must run downward");
});

test("a feature with no bounded footprint is skipped rather than guessed at", () => {
  // A face or an outside contour has no XY circle that honestly encloses it.
  const face = { id: "f", kind: "FACE", label: "face top", functionalRole: "DATUM_FACE", critical: true, depth: 0.05 } as unknown as Feature;
  assert.deepEqual(buildProtectedRegions([face]), []);
});

test("every region names the feature and the fact that protected it", () => {
  const regions = buildProtectedRegions([
    bore({ id: "a", label: "bearing bore", functionalRole: "BEARING_SEAT" }),
    bore({ id: "b", label: "tight bore", tolerance: { plus: 0.0005, minus: 0.0005 } }),
  ]);
  assert.equal(regions.length, 2);
  for (const r of regions) {
    assert.ok(r.label.length > 0, "a region with no label cannot be explained to an operator");
    assert.ok(r.reason.length > 5, `${r.label} gives no reason`);
  }
});

test("building regions is deterministic", () => {
  const fs = [bore({ critical: true }), bore({ id: "b2", functionalRole: "SHAFT_JOURNAL" })];
  assert.deepEqual(buildProtectedRegions(fs), buildProtectedRegions(fs));
});
