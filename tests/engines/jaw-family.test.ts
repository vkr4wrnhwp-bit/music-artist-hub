import { test } from "node:test";
import assert from "node:assert/strict";
import {
  solveShim,
  findExistingJaws,
  proposeFamily,
  jawEconomics,
  STANDARD_SHIMS,
  type JawSet,
  type JawRequest,
} from "@/lib/engines/jaw-family";

/**
 * Soft jaws are how a second operation gets a repeatable hold, so the failure
 * that matters is offering a jaw that will not actually hold the part — and
 * saying so in the confident register this engine writes in ("this part drops
 * straight in").
 *
 * The other half is arithmetic a shop owner makes a make/buy decision on. A
 * cost figure that is wrong is worse than one that is absent, because it gets
 * used.
 *
 * The shim shelf and the family sizes ARE pinned: they are records of what a
 * shop physically has, not model output, and a silent change to either
 * changes what the engine tells someone to reach for.
 */

const jaw = (o: Partial<JawSet> & { id: string; nominalSize: number }): JawSet => ({
  name: `jaw ${o.id}`, profile: "ROUND", stepDepth: 0.5, jawHeight: 1.5,
  material: "6061", viseDescription: '6" vise', timesUsed: 0, minutesToCut: 35, ...o,
});

const req = (o: Partial<JawRequest> & { size: number }): JawRequest => ({
  profile: "ROUND", requiredStep: 0.3, ...o,
});

/* ---------------- A jaw is never offered that cannot hold the part ---------------- */

test("a rectangular jaw too short for the part is not offered", () => {
  // The second dimension was never checked. A set cut 4.000 across and 2.000
  // long was returned for a 4.000 × 6.000 part with the words "this part
  // drops straight in" — a third of the part hanging out of a jaw that
  // cannot reach it.
  const short = jaw({ id: "j1", profile: "RECTANGULAR", nominalSize: 4.0, nominalLength: 2.0 });
  const matches = findExistingJaws(req({ profile: "RECTANGULAR", size: 4.0, length: 6.0 }), [short]);
  assert.deepEqual(matches, [], "a 2.000 jaw cannot hold a 6.000 part");
});

test("a rectangular jaw long enough is offered", () => {
  const long = jaw({ id: "j1", profile: "RECTANGULAR", nominalSize: 4.0, nominalLength: 6.0 });
  const matches = findExistingJaws(req({ profile: "RECTANGULAR", size: 4.0, length: 6.0 }), [long]);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].lengthUnverified, false);
});

test("a jaw with no recorded length is offered but flagged, not silently trusted", () => {
  // Dropping it would hide a usable jaw; claiming it fits would be the
  // original bug. It is offered with the gap named.
  const unknown = jaw({ id: "j1", profile: "RECTANGULAR", nominalSize: 4.0 });
  const matches = findExistingJaws(req({ profile: "RECTANGULAR", size: 4.0, length: 6.0 }), [unknown]);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].lengthUnverified, true);
  assert.match(matches[0].reason, /no length is recorded/i);
});

test("a jaw smaller than the part is never offered — shims go inward only", () => {
  const small = jaw({ id: "j1", nominalSize: 3.0 });
  assert.deepEqual(findExistingJaws(req({ size: 4.0 }), [small]), []);
});

test("a jaw whose step is too shallow for the grip is not offered", () => {
  const shallow = jaw({ id: "j1", nominalSize: 4.0, stepDepth: 0.1 });
  assert.deepEqual(findExistingJaws(req({ size: 4.0, requiredStep: 0.5 }), [shallow]), []);
});

test("a jaw needing more shim than a stack can hold is not offered", () => {
  // Past 0.750 per side the stack acts like a spring and the repeatability
  // the jaws existed for is gone.
  const huge = jaw({ id: "j1", nominalSize: 6.0 });
  assert.deepEqual(findExistingJaws(req({ size: 1.0 }), [huge]), [], "2.5 per side is not a shim stack");
});

test("profiles are never mixed", () => {
  const round = jaw({ id: "j1", profile: "ROUND", nominalSize: 4.0 });
  assert.deepEqual(findExistingJaws(req({ profile: "RECTANGULAR", size: 4.0 }), [round]), []);
});

test("the least shimming comes first, because a smaller stack is stiffer", () => {
  const jaws = [
    jaw({ id: "far", nominalSize: 4.5 }),
    jaw({ id: "near", nominalSize: 4.05 }),
    jaw({ id: "exact", nominalSize: 4.0 }),
  ];
  const order = findExistingJaws(req({ size: 4.0 }), jaws).map((m) => m.jawSet.id);
  assert.deepEqual(order, ["exact", "near", "far"]);
});

/* ---------------- The shim shelf ---------------- */

test("the shim shelf is what the shop actually stocks", () => {
  assert.deepEqual(STANDARD_SHIMS, [0.015, 0.031, 0.062, 0.125, 0.25, 0.375, 0.5]);
});

test("a shim solution never lists shims that are not on the shelf", () => {
  for (let g = 0.01; g <= 0.75; g += 0.007) {
    const s = solveShim(Number(g.toFixed(4)));
    if (!s) continue;
    for (const piece of s.stack) {
      assert.ok(STANDARD_SHIMS.includes(piece), `${piece} is not stocked`);
    }
  }
});

test("a gap thinner than the thinnest shim says so instead of listing nothing", () => {
  // The greedy stack came back empty and the note rendered as
  // ` = 0.000" per side` — an empty join with nothing in front of it. It was
  // still returned as a solution, so the caller said "shim it down 0.012 per
  // side" and listed no shims to do it with.
  const s = solveShim(0.012);
  assert.ok(s);
  assert.deepEqual(s.stack, []);
  assert.equal(s.exact, false);
  assert.ok(!s.note.startsWith(" ="), `the note is malformed: "${s.note}"`);
  assert.match(s.note, /nothing on the shelf is that thin/i);
  assert.match(s.note, /0\.015/, "it names the thinnest shim stocked");
});

test("no shim note is ever malformed, whatever the gap", () => {
  for (let g = 0.01; g <= 0.76; g += 0.003) {
    const s = solveShim(Number(g.toFixed(4)));
    if (!s) continue;
    assert.ok(s.note.trim().length > 10, `gap ${g}: "${s.note}"`);
    assert.ok(!/^\s*=/.test(s.note), `gap ${g} has an empty stack rendered into the note: "${s.note}"`);
    assert.ok(!/NaN|undefined/.test(s.note), `gap ${g}: "${s.note}"`);
  }
});

test("a gap too small to matter and one too big to hold are both refused", () => {
  assert.equal(solveShim(0.005), null, "below the useful minimum there is nothing to shim");
  assert.equal(solveShim(0.9), null, "past the maximum the stack is a spring");
  assert.equal(solveShim(0), null);
});

test("a stack never overshoots enough to stop the part fitting", () => {
  for (let g = 0.015; g <= 0.75; g += 0.005) {
    const s = solveShim(Number(g.toFixed(4)));
    if (!s || s.stack.length === 0) continue;
    const total = s.stack.reduce((a, b) => a + b, 0);
    assert.ok(total - g <= 0.001, `gap ${g.toFixed(4)}: stack of ${total.toFixed(4)} is too thick for the part to enter`);
  }
});

test("a stack is built biggest first, the way a machinist assembles one", () => {
  const s = solveShim(0.4);
  assert.ok(s && s.stack.length > 0);
  assert.deepEqual(s.stack, [...s.stack].sort((a, b) => b - a));
});

test("an exact solution reports itself exact and an approximate one does not", () => {
  const exact = solveShim(0.5);
  assert.ok(exact && exact.exact && exact.error === 0, `0.500 is a shim on the shelf: ${JSON.stringify(exact)}`);
  const approx = solveShim(0.2);
  assert.ok(approx);
  if (!approx.exact) assert.ok(Math.abs(approx.error) > 0.002);
});

/* ---------------- Choosing a family size ---------------- */

test("a jaw is never advertised as covering a negative diameter", () => {
  // coversFrom was candidate - 2 * MAX_SHIM_PER_SIDE with no floor, so a
  // ⌀1.000 jaw was described as covering "-0.500–⌀1.000".
  for (const size of [0.4, 0.9, 1.2, 1.4]) {
    const p = proposeFamily(req({ size }), []);
    assert.ok(p.coversFrom >= 0, `⌀${size} proposes coverage from ${p.coversFrom}`);
    assert.ok(!/-\d/.test(p.versusBespoke), `negative range in the prose: ${p.versusBespoke}`);
  }
});

test("coverage never runs backwards", () => {
  for (const size of [0.5, 1, 2, 3.7, 6, 7.5]) {
    const p = proposeFamily(req({ size }), []);
    assert.ok(p.coversTo > p.coversFrom, `⌀${size}: ${p.coversFrom}..${p.coversTo}`);
    assert.ok(p.coversTo >= size - 0.0005, "the family size must cover the part it was proposed for");
  }
});

test("the family size is a round number the next job might want", () => {
  const p = proposeFamily(req({ size: 4.317 }), []);
  assert.equal(p.cutAt, 4.5, "4.317 is not a size to cut a jaw at; 4.5 is");
  assert.equal(p.partSize, 4.317);
  assert.ok(p.shim, "the part then runs on shims");
});

test("a part already at a family size needs no shim", () => {
  const p = proposeFamily(req({ size: 4.0 }), []);
  assert.equal(p.cutAt, 4);
  assert.equal(p.shim, null);
});

test("it does not propose cutting a duplicate of a jaw already in the drawer", () => {
  const existing = [jaw({ id: "j1", nominalSize: 4.5 })];
  const p = proposeFamily(req({ size: 4.317 }), existing);
  assert.notEqual(p.cutAt, 4.5, "that jaw already exists — cutting it again is the waste this engine exists to stop");
  assert.ok(p.cutAt > 4.317);
});

test("a part bigger than every family size still gets a proposal", () => {
  const p = proposeFamily(req({ size: 9.3 }), []);
  assert.ok(p.cutAt >= 9.3, `${p.cutAt} does not cover a 9.300 part`);
  assert.ok(Number.isFinite(p.cutAt));
});

test("the proposal argues against the bespoke alternative in concrete terms", () => {
  const p = proposeFamily(req({ size: 4.317 }), []);
  assert.match(p.versusBespoke, /4\.317/, "it names what bespoke would cost you");
  assert.match(p.versusBespoke, /4\.500/);
  assert.ok(p.rationale.length > 40);
});

test("a round proposal speaks in diameters and a rectangular one does not", () => {
  const round = proposeFamily(req({ profile: "ROUND", size: 4.0 }), []);
  assert.match(round.rationale, /⌀/);
  const rect = proposeFamily(req({ profile: "RECTANGULAR", size: 4.0 }), []);
  assert.ok(!rect.rationale.includes("⌀"), `⌀ on a rectangular set reads as a mistake: ${rect.rationale}`);
  assert.match(rect.rationale, /across/);
});

/* ---------------- The economics, which is what gets acted on ---------------- */

test("a missing shop rate produces no cost figure rather than a NaN one", () => {
  // This printed "the jaws add $NaN a part" into a make/buy decision.
  for (const bad of [{ shopRatePerHour: Number.NaN }, { shopRatePerHour: 0 }, { blankCost: Number.NaN }, { minutesToCut: Number.NaN }]) {
    const e = jawEconomics({
      minutesToCut: 35, shopRatePerHour: 95, blankCost: 40, quantity: 10,
      expectedUses: 3, reuseSetupMinutes: null, ...bad,
    });
    assert.equal(e.computable, false, JSON.stringify(bad));
    assert.ok(!/NaN/.test(e.verdict), `verdict prints NaN: ${e.verdict}`);
    assert.match(e.verdict, /cannot be worked out/i);
  }
});

test("a complete set of inputs computes and says so", () => {
  const e = jawEconomics({
    minutesToCut: 35, shopRatePerHour: 60, blankCost: 40, quantity: 10,
    expectedUses: 1, reuseSetupMinutes: null,
  });
  assert.equal(e.computable, true);
  assert.equal(e.cutCost, 75, "35 minutes at $60/hr is $35, plus a $40 blank");
  assert.equal(e.costIfBespoke, 7.5, "over ten parts");
  assert.ok(!/NaN/.test(e.verdict));
});

test("amortising over more jobs lowers the cost per part, and never raises it", () => {
  const at = (uses: number) =>
    jawEconomics({ minutesToCut: 35, shopRatePerHour: 60, blankCost: 40, quantity: 10, expectedUses: uses, reuseSetupMinutes: null });
  assert.ok(at(5).costAmortised < at(1).costAmortised);
  assert.equal(at(1).costAmortised, at(1).costIfBespoke, "one use means the whole cost lands on this job");
});

test("reusing a jaw in the drawer is always cheaper than cutting a new one", () => {
  const e = jawEconomics({
    minutesToCut: 35, shopRatePerHour: 60, blankCost: 40, quantity: 10,
    expectedUses: 1, reuseSetupMinutes: 15,
  });
  assert.ok(e.costIfReused !== null && e.costIfReused < e.costIfBespoke);
  assert.match(e.verdict, /already exist/i, "the recommendation has to be unambiguous");
});

test("no reuse recorded means no reuse figure, rather than a zero", () => {
  const e = jawEconomics({
    minutesToCut: 35, shopRatePerHour: 60, blankCost: 40, quantity: 10,
    expectedUses: 2, reuseSetupMinutes: null,
  });
  assert.equal(e.costIfReused, null, "null, not 0 — a free jaw is a claim");
});

test("a quantity of zero does not divide by zero", () => {
  const e = jawEconomics({
    minutesToCut: 35, shopRatePerHour: 60, blankCost: 40, quantity: 0,
    expectedUses: 0, reuseSetupMinutes: null,
  });
  assert.ok(Number.isFinite(e.costIfBespoke) && Number.isFinite(e.costAmortised));
  assert.equal(e.expectedUses, 1);
});

test("every money figure in a verdict is formatted, never raw", () => {
  const e = jawEconomics({
    minutesToCut: 35, shopRatePerHour: 95, blankCost: 40, quantity: 7,
    expectedUses: 4, reuseSetupMinutes: 12,
  });
  const raw = e.verdict.match(/\$\d+\.\d+/g) ?? [];
  assert.ok(raw.length > 0, "a verdict about cost must contain one");
  for (const m of raw) assert.match(m, /^\$\d+\.\d{2}$/, `${m} is not money`);
});

test("the engine is deterministic", () => {
  const jaws = [jaw({ id: "j1", nominalSize: 4.5 }), jaw({ id: "j2", nominalSize: 5.0 })];
  assert.deepEqual(findExistingJaws(req({ size: 4.0 }), jaws), findExistingJaws(req({ size: 4.0 }), jaws));
  assert.deepEqual(proposeFamily(req({ size: 4.317 }), jaws), proposeFamily(req({ size: 4.317 }), jaws));
});
