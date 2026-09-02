import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildFixture, cutterHitsJaw, type FixtureInput, type FixtureModel } from "@/lib/sim/fixture";
import { StockRemovalSimulator, type SimOperation } from "@/lib/sim/stock-removal";
import type { Move } from "@/lib/engines/cam/types";

/**
 * The CUT view simulated stock removal and holder contact, modelled no
 * fixture at all, and wrote `collisionChecked: true` on every run — a column
 * whose own schema comment says it exists so no consumer can mistake a
 * visualisation for a verification.
 *
 * Two things are being held here: that the jaws are actually checked when
 * they can be placed, and that nothing claims they were when they could not.
 */

const STOCK = { x: 4, y: 3, z: 1 };

const OK: FixtureInput = {
  jawAxis: "X",
  jawWidth: 6,
  jawHeight: 1.5,
  stockProjection: 0.4,
  gripDepth: null,
  stock: STOCK,
};

test("a fixture is built from recorded numbers, with the jaw top below the stock top", () => {
  const r = buildFixture(OK);
  assert.ok(r.fixture, "no fixture was built from a complete input");
  const f = r.fixture!;
  assert.equal(f.axis, "X");
  // 0.400" stands proud, so the jaws top out 0.400" below Z=0.
  assert.equal(f.topZ, -0.4);
  assert.equal(f.stockHalf, 2);
  assert.equal(f.halfWidth, 3);
});

test("grip depth gives the same jaw top as projection", () => {
  // The part sits on parallels: gripped plus proud is the stock height.
  const byGrip = buildFixture({ ...OK, stockProjection: null, gripDepth: 0.6 }).fixture!;
  assert.ok(Math.abs(byGrip.topZ - -0.4) < 1e-9, `grip depth gave ${byGrip.topZ}`);
});

test("a missing jaw axis builds nothing and says what is missing", () => {
  // The one that matters: put the jaws on the wrong two faces and the check
  // clears exactly the setup that would crash.
  for (const axis of [null, "", "Z", "x", "diagonal"]) {
    const r = buildFixture({ ...OK, jawAxis: axis });
    assert.equal(r.fixture, null, `"${axis}" was accepted as an axis`);
    assert.match((r as { gap: { missing: string } }).gap.missing, /axis the jaws close on/);
  }
});

test("every other missing datum names itself rather than defaulting", () => {
  const cases: [Partial<FixtureInput>, RegExp][] = [
    [{ stock: null }, /stock size/],
    [{ jawWidth: null }, /jaw width/],
    [{ jawWidth: 0 }, /jaw width/],
    [{ stockProjection: null, gripDepth: null }, /stands proud/],
  ];
  for (const [patch, expected] of cases) {
    const r = buildFixture({ ...OK, ...patch });
    assert.equal(r.fixture, null, `${JSON.stringify(patch)} still built a fixture`);
    assert.match((r as { gap: { missing: string } }).gap.missing, expected);
  }
});

test("the model declares what it is not", () => {
  const f = buildFixture(OK).fixture!;
  const text = f.assumptions.join(" ");
  assert.match(text, /not as the fixture's geometry/);
  assert.match(text, /[Ss]oft jaws/);
  assert.ok(f.assumptions.length >= 3, "the approximations are barely stated");
});

/* ---- the geometry itself ---- */

const F: FixtureModel = buildFixture(OK).fixture!;

test("nothing above the jaw top can hit a jaw, however far out it goes", () => {
  // Z=0 is the top of the stock and the jaws top out below it.
  for (const z of [0, -0.1, -0.399, 1]) {
    assert.equal(cutterHitsJaw(F, 4, 0, z, 0.25), false, `z=${z} reported a hit above the jaws`);
  }
});

test("nothing inside the stock outline can hit a jaw, however deep it goes", () => {
  // The jaw faces are flush with the stock faces, so a cut inside the part
  // is a cut into the part, never into the vise.
  for (const x of [0, 1, 1.7]) {
    assert.equal(cutterHitsJaw(F, x, 0, -0.9, 0.25), false, `x=${x} at depth reported a hit`);
  }
});

test("a cutter reaching past the gripped face below jaw top is a hit", () => {
  // 2.000 is the face; a 0.250 radius at x=1.900 reaches 2.150.
  assert.equal(cutterHitsJaw(F, 1.9, 0, -0.5, 0.25), true);
  // And the same position with a smaller cutter that does not reach is not.
  assert.equal(cutterHitsJaw(F, 1.9, 0, -0.5, 0.05), false);
});

test("it is the cutter's edge that reaches the jaw, not its centre", () => {
  // The defect this guards: testing the centre point lets a big cutter park
  // its edge in the jaw and report clear.
  assert.equal(cutterHitsJaw(F, 1.5, 0, -0.5, 0.6), true, 'a 1.2in cutter at x=1.5 does not reach x=2.0');
  assert.equal(cutterHitsJaw(F, 1.5, 0, -0.5, 0.1), false);
});

test("a move beyond the end of the jaws is clear", () => {
  // The jaws are 6" wide on a 3" part, so ±3" across. Past that there is no
  // jaw to hit even though the tool is out past the gripped face.
  assert.equal(cutterHitsJaw(F, 2.5, 0, -0.5, 0.25), true, "over the jaw was not reported");
  assert.equal(cutterHitsJaw(F, 2.5, 3.5, -0.5, 0.25), false, "past the end of the jaw was reported as a hit");
});

test("the axis decides which pair of faces is gripped", () => {
  const y = buildFixture({ ...OK, jawAxis: "Y" }).fixture!;
  // Out past X on a Y-gripped part is out over open air, not over a jaw.
  assert.equal(cutterHitsJaw(y, 2.5, 0, -0.5, 0.25), false);
  assert.equal(cutterHitsJaw(y, 0, 1.9, -0.5, 0.25), true);
});

/* ---- and the simulator uses it ---- */

const moves = (pts: [number, number, number, number | null][]): Move[] =>
  pts.map(([x, y, z, feed]) => ({ x, y, z, feed }) as Move);

const op = (ms: Move[]): SimOperation => ({
  operationId: "op1", label: "Profile", toolNumber: 1,
  toolDiameter: 0.5, fluteLength: 1.0, rpm: 5000, moves: ms,
});

test("with no fixture the jaw check does not run, and the simulator says so", () => {
  const sim = new StockRemovalSimulator(STOCK, [op(moves([
    [0, 0, 0.1, null], [2.4, 0, 0.1, null], [2.4, 0, -0.5, 10], [2.4, 1, -0.5, 10],
  ]))], 600, 60, null);
  assert.equal(sim.fixtureChecked, false);
  assert.equal(sim.collisions.filter((c) => c.kind === "FIXTURE_CONTACT").length, 0);
});

test("with a fixture, a cut out past the gripped face below jaw top is caught", () => {
  const sim = new StockRemovalSimulator(STOCK, [op(moves([
    [0, 0, 0.1, null], [2.4, 0, 0.1, null], [2.4, 0, -0.5, 10], [2.4, 1, -0.5, 10],
  ]))], 600, 60, F);
  assert.equal(sim.fixtureChecked, true);
  const hits = sim.collisions.filter((c) => c.kind === "FIXTURE_CONTACT");
  assert.ok(hits.length > 0, "the cutter was driven into a jaw and nothing was reported");
  assert.match(hits[0].detail, /below the top of the jaws/);
});

test("the same path above the jaw top is clean", () => {
  const sim = new StockRemovalSimulator(STOCK, [op(moves([
    [0, 0, 0.1, null], [2.4, 0, 0.1, null], [2.4, 0, -0.3, 10], [2.4, 1, -0.3, 10],
  ]))], 600, 60, F);
  assert.equal(sim.collisions.filter((c) => c.kind === "FIXTURE_CONTACT").length, 0);
});

test("a rapid into a jaw is caught, not only a feed", () => {
  // A rapid never cuts, and the old jaw branch would have sat after the
  // rapid early-return. The jaws are there either way.
  const sim = new StockRemovalSimulator(STOCK, [op(moves([
    [0, 0, -0.6, null], [2.4, 0, -0.6, null],
  ]))], 600, 60, F);
  assert.ok(sim.collisions.some((c) => c.kind === "FIXTURE_CONTACT"), "a rapid through a jaw was not reported");
});

test("one report per segment, not one per sample", () => {
  // A move travelling the length of a jaw samples it dozens of times.
  const sim = new StockRemovalSimulator(STOCK, [op(moves([
    [2.4, -1.4, -0.5, null], [2.4, 1.4, -0.5, 10],
  ]))], 600, 60, F);
  assert.equal(sim.collisions.filter((c) => c.kind === "FIXTURE_CONTACT").length, 1);
});

/* ---- the flag that must not lie ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("collisionChecked is written from what actually ran, never a literal true", () => {
  // This is the defect. The column's schema comment says it exists so no
  // consumer can mistake a visualisation for a verification, and it was set
  // true on every run while no fixture was modelled at all.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/page.tsx", "utf8"));
  assert.ok(!/collisionChecked:\s*true/.test(src), "collisionChecked is hardcoded true again");
  assert.match(src, /collisionChecked:\s*payload\.fixtureChecked/);
});

test("the run records which checks did and did not run", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/page.tsx", "utf8"));
  assert.match(src, /checksNotRun/);
  assert.match(src, /checksRun/);
});

test("the transport never says 'no collisions' about a run that skipped the jaws", () => {
  // The sentence an operator acts on.
  const src = strip(readFileSync("src/components/workspace/sim-transport.tsx", "utf8"));
  assert.ok(!/No collisions found/.test(src), "the unqualified all-clear is back");
  assert.match(src, /the jaws were not modelled/);
  assert.match(src, /sim\.fixtureChecked/);
});

test("the simulator never invents a fixture when none was supplied", () => {
  const src = strip(readFileSync("src/lib/sim/stock-removal.ts", "utf8"));
  assert.match(src, /fixture: FixtureModel \| null = null/, "the fixture parameter gained a default vise");
  const store = strip(readFileSync("src/lib/sim/fixture.ts", "utf8"));
  assert.ok(!/\?\?\s*"X"|\?\?\s*"Y"/.test(store), "the jaw axis falls back to a default");
});
