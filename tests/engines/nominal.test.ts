import { test } from "node:test";
import assert from "node:assert/strict";
import {
  findNominalCandidates,
  bestNominalSuggestion,
  MM_PER_INCH,
  type NominalQuery,
} from "@/lib/engines/nominal";

/**
 * This engine reads a measurement off an instrument and proposes what the
 * designer probably intended. That is reverse engineering, and it is the one
 * place in CANVAS where a wrong standards table silently becomes a wrong
 * nominal on a part nobody has a drawing for — the operator then machines to
 * the suggestion.
 *
 * So, as with mating.ts, the tables ARE asserted value by value. They are
 * transcribed standards, not a model, and drift is a failure rather than a
 * tuning decision. What is not asserted is the confidence arithmetic: the
 * scoring curve is a heuristic and pinning its numbers would freeze it.
 * What is pinned about scoring is the behaviour that keeps it honest — that
 * it refuses, that it stays quiet when two candidates are tied, and that the
 * metric boost cannot beat a closer inch value.
 */

const IN = (mm: number) => mm / MM_PER_INCH;

const q = (over: Partial<NominalQuery> & { measured: number }): NominalQuery => ({
  uncertainty: 0.0002, // a decent 0-1" micrometer
  ...over,
});

const labels = (query: NominalQuery) => findNominalCandidates(query).map((c) => c.label);
const hasNominal = (query: NominalQuery, inches: number) =>
  findNominalCandidates(query).some((c) => Math.abs(c.nominalInches - inches) < 1e-6);

/* ---------------- The drill index, against the published series ---------------- */

test("the fractional drill series has no gaps from 1/16 to 1/2", () => {
  // The old flat table was missing 11/64, 13/64, 19/64, 21/64, 23/64, 3/8,
  // 25/64 and 13/32. A hole drilled 0.3750 matched letter V at 0.377 and came
  // back as an oversize letter drill instead of the 3/8 it plainly was.
  for (let n = 4; n <= 32; n++) {
    const d = n / 64;
    assert.ok(
      hasNominal(q({ measured: d, context: "HOLE" }), d),
      `${n}/64 (${d.toFixed(4)}") is a drill in every index and must be a candidate`,
    );
  }
});

test("3/8 is recognised as 3/8 and not as the letter drill two thou away", () => {
  const best = bestNominalSuggestion(q({ measured: 0.3752, context: "HOLE" }));
  assert.ok(best, "0.3752 off a drilled hole is a 3/8 drill");
  assert.equal(best.nominalInches, 0.375);
  assert.match(best.label, /3\/8/);
});

test("number drills carry their number and letter drills their letter", () => {
  // A machinist reaches for "#7", not for "0.2010". The old table held bare
  // decimals, so the suggestion named a size nobody could pick off a rack.
  const seven = findNominalCandidates(q({ measured: 0.201, context: "HOLE" }));
  assert.ok(seven.some((c) => /#7\b/.test(c.label)), `expected #7; got [${seven.map((c) => c.label).join(" | ")}]`);
  const f = findNominalCandidates(q({ measured: 0.257, context: "HOLE" }));
  assert.ok(f.some((c) => /letter F/.test(c.label)), `expected letter F; got [${f.map((c) => c.label).join(" | ")}]`);
});

test("every tap drill this file names in a thread note is actually in the index", () => {
  // #4-40's note says "tap drill 0.0890" — and #43 was absent from the index,
  // so CANVAS recommended a drill it could not then recognise.
  const tapDrills = [0.089, 0.1065, 0.136, 0.1495, 0.159, 0.201, 0.213, 0.257, 0.3125, 0.4219];
  for (const d of tapDrills) {
    // The notes state four-place decimals, and some of them are rounded
    // fractions — 0.4219 is 27/64, which is 0.421875 exactly. Half a thou is
    // the right tolerance for "the index contains this drill".
    const found = findNominalCandidates(q({ measured: d, context: "HOLE" }));
    assert.ok(
      found.some((c) => Math.abs(c.nominalInches - d) < 5e-4),
      `tap drill ${d.toFixed(4)}" must be in the index; got [${found.map((c) => c.label).join(" | ")}]`,
    );
  }
});

test("the letter series matches ANSI B94.11M, diameter by diameter", () => {
  // Written after a mutation moved letter S from 0.3480 to 0.3490 and the
  // whole suite still passed: nothing here checked a drill's actual size,
  // only that a drill of roughly that size existed. A shifted table is
  // exactly the failure this engine cannot have — a hole reverse-engineered
  // to the wrong drill gets machined to the wrong drill.
  const LETTERS: [string, number][] = [
    ["A", 0.234], ["B", 0.238], ["C", 0.242], ["D", 0.246], ["E", 0.25], ["F", 0.257],
    ["G", 0.261], ["H", 0.266], ["I", 0.272], ["J", 0.277], ["K", 0.281], ["L", 0.29],
    ["M", 0.295], ["N", 0.302], ["O", 0.316], ["P", 0.323], ["Q", 0.332], ["R", 0.339],
    ["S", 0.348], ["T", 0.358], ["U", 0.368], ["V", 0.377], ["W", 0.386], ["X", 0.397],
    ["Y", 0.404], ["Z", 0.413],
  ];
  for (const [letter, d] of LETTERS) {
    const found = findNominalCandidates(q({ measured: d, uncertainty: 0.00005, context: "HOLE" }));
    assert.ok(
      found.some((c) => Math.abs(c.nominalInches - d) < 1e-9),
      `letter ${letter} must be exactly ${d.toFixed(4)}"; got [${found.map((c) => c.label).join(" | ")}]`,
    );
  }
});

test("the number series matches ANSI B94.11M, diameter by diameter", () => {
  const NUMBERS: [number, number][] = [
    [1, 0.228], [3, 0.213], [7, 0.201], [10, 0.1935], [16, 0.177], [21, 0.159], [25, 0.1495],
    [29, 0.136], [30, 0.1285], [36, 0.1065], [43, 0.089], [50, 0.07], [56, 0.0465], [60, 0.04],
  ];
  for (const [n, d] of NUMBERS) {
    const found = findNominalCandidates(q({ measured: d, uncertainty: 0.00005, context: "HOLE" }));
    assert.ok(
      found.some((c) => Math.abs(c.nominalInches - d) < 1e-9),
      `#${n} must be exactly ${d.toFixed(4)}"; got [${found.map((c) => c.label).join(" | ")}]`,
    );
  }
});

test("0.420 is not a drill size and is not offered as one", () => {
  // It sat between letter Z (0.413) and 27/64 (0.4219) in the old table, and
  // is in no series. #58 is 0.0420, which is where it most likely came from.
  const near = findNominalCandidates(q({ measured: 0.42, uncertainty: 0.0002, context: "HOLE" }));
  assert.ok(
    !near.some((c) => Math.abs(c.nominalInches - 0.42) < 1e-6),
    `0.4200 must not be a candidate; got [${near.map((c) => c.label).join(" | ")}]`,
  );
});

test("no two drills in the index share a diameter, and the index is sorted", () => {
  // E is 1/4 and #26 is 0.1470 — collisions are real, and the dedupe in the
  // matcher relies on them resolving to one candidate rather than two rows
  // claiming the same number with different confidences.
  const quarter = findNominalCandidates(q({ measured: 0.25, context: "HOLE" }));
  const atQuarter = quarter.filter((c) => Math.abs(c.nominalInches - 0.25) < 1e-9);
  assert.equal(atQuarter.length, 1, "one nominal value, one candidate");
});

/* ---------------- Bearing and thread tables ---------------- */

test("a worn metric bearing seat resolves to the metric size, not a fraction", () => {
  // 40 mm is 1.5748". The whole point of the engine: 1.5744 off a bore gauge
  // is a 40 mm seat, and 1.5750 is not a number a designer picks in inches.
  const best = bestNominalSuggestion(q({ measured: 1.5744, uncertainty: 0.0002, context: "BORE", wearExpected: true }));
  assert.ok(best, "a 40 mm bearing seat must be recognised");
  assert.ok(Math.abs(best.nominalInches - IN(40)) < 1e-9, `expected 40 mm; got ${best.label}`);
  assert.equal(best.family, "METRIC_BEARING");
});

test("common metric bearing bores are all reachable", () => {
  for (const mm of [10, 12, 15, 17, 20, 25, 30, 35, 40, 45, 50, 62, 72, 80]) {
    assert.ok(hasNominal(q({ measured: IN(mm), context: "BORE" }), IN(mm)), `${mm} mm bore`);
  }
});

test("thread major diameters match the standards", () => {
  const majors: [string, number][] = [
    ["#4-40", 0.112], ["#6-32", 0.138], ["#8-32", 0.164], ["#10-24", 0.19],
    ["1/4-20", 0.25], ["5/16-18", 0.3125], ["3/8-16", 0.375], ["1/2-13", 0.5],
    ["M3", IN(3)], ["M6", IN(6)], ["M8", IN(8)], ["M10", IN(10)],
  ];
  for (const [name, major] of majors) {
    const found = findNominalCandidates(q({ measured: major, context: "THREAD" }));
    assert.ok(
      found.some((c) => Math.abs(c.nominalInches - major) < 1e-9),
      `${name} major diameter ${major.toFixed(4)}" must be a candidate`,
    );
  }
});

/* ---------------- Refusal ---------------- */

test("a measurement that does not exist produces no candidates", () => {
  // NaN passed the window filter — `Math.abs(NaN) > window` is false — so
  // every table entry was accepted, scored NaN, and bestNominalSuggestion
  // returned one, because `NaN < 0.7` is also false. An empty measurement
  // field became a confident standard-value suggestion.
  for (const measured of [Number.NaN, Number.POSITIVE_INFINITY, 0, -1.5]) {
    assert.deepEqual(findNominalCandidates(q({ measured })), [], `measured=${measured}`);
    assert.equal(bestNominalSuggestion(q({ measured })), null, `measured=${measured}`);
  }
});

test("an uncertainty that does not exist produces no candidates", () => {
  for (const uncertainty of [Number.NaN, Number.POSITIVE_INFINITY, -0.001]) {
    assert.deepEqual(findNominalCandidates({ measured: 0.5, uncertainty }), []);
  }
});

test("a measurement near nothing standard returns nothing, not the nearest thing", () => {
  // 0.7331" is not near any tabulated value at this uncertainty. The engine
  // must decline rather than reach for whatever is closest — a custom bore is
  // a legitimate answer.
  assert.deepEqual(findNominalCandidates(q({ measured: 0.7331, uncertainty: 0.0001 })), []);
  assert.equal(bestNominalSuggestion(q({ measured: 0.7331, uncertainty: 0.0001 })), null);
});

test("a coarse instrument widens the window rather than pretending to precision", () => {
  // A 0.001" resolution caliper cannot distinguish 0.2010 from 0.2040, and
  // must not be allowed to pick one confidently.
  const coarse = findNominalCandidates(q({ measured: 0.2025, uncertainty: 0.0015, context: "HOLE" }));
  assert.ok(coarse.length > 1, "a coarse reading admits more than one nominal");
  assert.equal(
    bestNominalSuggestion(q({ measured: 0.2025, uncertainty: 0.0015, context: "HOLE" })),
    null,
    "with several near-equal candidates there is no single suggestion to make",
  );
});

test("two effectively tied candidates produce no suggestion at all", () => {
  const best = bestNominalSuggestion(q({ measured: 0.2, uncertainty: 0.002, context: "HOLE" }));
  assert.equal(best, null, "0.199, 0.201 and 0.204 are all in reach — that is not a signal");
});

/* ---------------- The metric boost ---------------- */

test("the metric boost cannot beat a materially closer inch value", () => {
  // The boost exists so 1.5748 reads as 40 mm rather than as an odd inch
  // number. It must not become a thumb on the scale: 0.5000" measured dead on
  // is a half inch, not 12.7 mm dressed up.
  const best = bestNominalSuggestion(q({ measured: 0.5, uncertainty: 0.0001, context: "BORE" }));
  if (best) assert.ok(Math.abs(best.nominalInches - 0.5) < 1e-9, `got ${best.label}`);
});

test("the boost is a tiebreaker, not an override", () => {
  // The 0.5000" case above cannot catch an oversized boost, because 12.7 mm
  // IS 0.5000" and the two dedupe to one candidate. This one is a real
  // contest: 0.2350" sits between 15/64 (0.2344, 0.6 thou away) and 6 mm
  // (0.2362, 1.2 thou away). The inch value is twice as close, and a boost
  // large enough to overturn that has stopped being a tiebreaker.
  const best = bestNominalSuggestion(q({ measured: 0.235, uncertainty: 0.0006 }));
  assert.ok(best, "0.2350 is a clear enough reading to suggest something");
  assert.ok(
    Math.abs(best.nominalInches - 15 / 64) < 1e-9,
    `the closer inch value must win; got ${best.label}`,
  );
});

test("the boost does not apply to a metric value that is a round inch anyway", () => {
  // 12.7 mm IS 0.5000". Boosting it would let the metric table win a tie it
  // has no claim to.
  const cands = findNominalCandidates(q({ measured: 0.5, uncertainty: 0.0002 }));
  const half = cands.filter((c) => Math.abs(c.nominalInches - 0.5) < 1e-9);
  assert.ok(half.length <= 1, "one value, one candidate, whichever family named it");
});

/* ---------------- Output shape ---------------- */

test("every candidate explains itself", () => {
  const cands = findNominalCandidates(q({ measured: IN(40), context: "BORE", wearExpected: true }));
  assert.ok(cands.length > 0);
  for (const c of cands) {
    assert.ok(c.basis.length > 20, `${c.label} has no basis`);
    assert.ok(c.interpretation.length > 0, `${c.label} says nothing about what it means`);
    assert.ok(c.confidence > 0 && c.confidence <= 1, `${c.label} confidence ${c.confidence} out of range`);
    assert.ok(Number.isFinite(c.deviation), `${c.label} deviation is not a number`);
  }
});

test("candidates come back worst-last and never more than five", () => {
  const cands = findNominalCandidates(q({ measured: 0.25, uncertainty: 0.004 }));
  assert.ok(cands.length <= 5);
  for (let i = 1; i < cands.length; i++) {
    assert.ok(cands[i - 1].confidence >= cands[i].confidence, "the list must be ordered by confidence");
  }
});

test("the deviation is signed and points the right way", () => {
  const over = findNominalCandidates(q({ measured: 0.3755, context: "HOLE" }))
    .find((c) => Math.abs(c.nominalInches - 0.375) < 1e-9);
  assert.ok(over && over.deviation > 0, "a measurement above nominal deviates positive");
  const under = findNominalCandidates(q({ measured: 0.3745, context: "HOLE" }))
    .find((c) => Math.abs(c.nominalInches - 0.375) < 1e-9);
  assert.ok(under && under.deviation < 0, "a measurement below nominal deviates negative");
});

test("context narrows the search rather than being decorative", () => {
  // A value asked about as a THREAD must not come back as a plate thickness.
  const thread = findNominalCandidates(q({ measured: 0.25, context: "THREAD" }));
  assert.ok(thread.every((c) => c.family === "THREAD_MAJOR"), `got [${thread.map((c) => c.family).join(", ")}]`);
  const hole = findNominalCandidates(q({ measured: 0.25, context: "HOLE" }));
  assert.ok(hole.every((c) => c.family === "DRILL_SIZE" || c.family === "DOWEL_PIN"));
});

test("the wear window only ever opens outward", () => {
  const tight = labels(q({ measured: IN(40), context: "BORE" }));
  const worn = labels(q({ measured: IN(40), context: "BORE", wearExpected: true }));
  for (const l of tight) assert.ok(worn.includes(l), `${l} disappeared when wear was expected`);
});

test("the same query gives the same answer", () => {
  const query = q({ measured: 0.3752, context: "HOLE" });
  assert.deepEqual(findNominalCandidates(query), findNominalCandidates(query));
});
