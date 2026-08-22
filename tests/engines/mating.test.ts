import { test } from "node:test";
import assert from "node:assert/strict";
import { fitFor, findBearing, BEARINGS } from "@/lib/engines/mating";

/**
 * Unlike the cutting-force tests, these DO assert magnitudes — and they must.
 *
 * The force model is a model, and pinning its output would freeze an estimate
 * nobody has validated. ISO 286 is not a model. It is a published table, the
 * numbers are not CANVAS's to choose, and this is the one place in the app
 * where a value is presented to an operator as engineering fact rather than
 * as DEVELOPMENT ANALYSIS. So the table gets checked against the standard,
 * value by value, and a drift is a failure rather than a tuning decision.
 *
 * The values below are ISO 286-2 limit deviations in micrometres. They are
 * transcribed from the standard, not derived here.
 */

const MM = 25.4;
/** Limit deviations back to µm, the units the standard states them in. */
const um = (inches: number) => Math.round(inches * MM * 1000);

function limits(nominalMm: number, fitClass: string): [number, number] {
  const f = fitFor(nominalMm, fitClass, "test");
  assert.ok(f, `${fitClass} must have a band covering ${nominalMm} mm`);
  return [um(f.lowerIn), um(f.upperIn)];
}

/* ---------------- The tables, against the standard ---------------- */

test("H7 matches ISO 286 across every band the app can reach", () => {
  const ISO: [number, number, number][] = [
    // nominal mm, lower µm, upper µm
    [3, 0, 10], [6, 0, 12], [10, 0, 15], [18, 0, 18],
    [30, 0, 21], [50, 0, 25], [80, 0, 30], [120, 0, 35], [180, 0, 40],
  ];
  for (const [n, lo, hi] of ISO) assert.deepEqual(limits(n, "H7"), [lo, hi], `H7 at ${n} mm`);
});

test("k6 matches ISO 286 across every band the app can reach", () => {
  const ISO: [number, number, number][] = [
    [3, 0, 6], [6, 1, 9], [10, 1, 10], [18, 1, 12],
    [30, 2, 15], [50, 2, 18], [80, 2, 21], [120, 3, 25], [180, 3, 28],
  ];
  for (const [n, lo, hi] of ISO) assert.deepEqual(limits(n, "k6"), [lo, hi], `k6 at ${n} mm`);
});

test("h6 matches ISO 286 across every band the app can reach", () => {
  const ISO: [number, number, number][] = [
    [3, -6, 0], [6, -8, 0], [10, -9, 0], [18, -11, 0],
    [30, -13, 0], [50, -16, 0], [80, -19, 0], [120, -22, 0], [180, -25, 0],
  ];
  for (const [n, lo, hi] of ISO) assert.deepEqual(limits(n, "h6"), [lo, hi], `h6 at ${n} mm`);
});

test("N7 matches ISO 286 across every band the app can reach", () => {
  const ISO: [number, number, number][] = [
    [3, -14, -4], [6, -16, -4], [10, -19, -4], [18, -23, -5],
    [30, -28, -7], [50, -33, -8], [80, -39, -9], [120, -45, -10], [180, -52, -12],
  ];
  for (const [n, lo, hi] of ISO) assert.deepEqual(limits(n, "N7"), [lo, hi], `N7 at ${n} mm`);
});

/* ---------------- The two defects this file was written for ---------------- */

test("a size on a band boundary takes that band, not the next one up", () => {
  // ISO bands run "over X up to and INCLUDING Y". The selector used `<`, so
  // 30 fell through to the 30–50 row and a 6006's bore got +2/+18 instead of
  // +2/+15 — a wider band, shifted toward more interference.
  assert.deepEqual(limits(30, "k6"), [2, 15], "30 mm belongs to 18–30");
  assert.deepEqual(limits(50, "k6"), [2, 18], "50 mm belongs to 30–50");
  assert.deepEqual(limits(80, "k6"), [2, 21], "80 mm belongs to 50–80");
  assert.deepEqual(limits(10, "k6"), [1, 10], "10 mm belongs to 6–10");
  assert.deepEqual(limits(18, "k6"), [1, 12], "18 mm belongs to 10–18");
});

test("small nominals get their own band rather than the 18-30 row", () => {
  // The tables started at 30, so everything under 18 silently took 18–30
  // values. Four bearing bores in the table are 10, 12, 15 and 17 mm.
  assert.deepEqual(limits(12, "k6"), [1, 12]);
  assert.deepEqual(limits(15, "k6"), [1, 12]);
  assert.deepEqual(limits(17, "k6"), [1, 12]);
  assert.notDeepEqual(limits(15, "k6"), limits(20, "k6"), "15 mm and 20 mm are different bands");
});

test("every bearing bore and OD in the table resolves to a real band", () => {
  for (const b of BEARINGS) {
    for (const cls of ["k6", "h6"]) assert.ok(fitFor(b.bore, cls, "t"), `${b.designation} bore ${b.bore} in ${cls}`);
    for (const cls of ["H7", "N7"]) assert.ok(fitFor(b.outer, cls, "t"), `${b.designation} OD ${b.outer} in ${cls}`);
  }
});

/* ---------------- Refusal ---------------- */

test("an unknown fit class returns null rather than a guess", () => {
  assert.equal(fitFor(30, "NOT_A_CLASS", "t"), null);
});

test("a size outside the tabulated range returns null rather than extrapolating", () => {
  assert.equal(fitFor(500, "H7", "t"), null, "beyond 180 mm the table does not go");
  // 0.5 mm is NOT out of range: ISO's first band is "up to and including 3"
  // with no lower bound, so it legitimately collects it. This assertion was
  // wrong when first written, and the code was right.
  assert.ok(fitFor(0.5, "H7", "t"), "the first band has no lower bound");
});

test("a nominal of zero or less is not a size", () => {
  assert.equal(fitFor(0, "H7", "t"), null);
  assert.equal(fitFor(-5, "k6", "t"), null);
  assert.equal(fitFor(Number.NaN, "H7", "t"), null);
});

/* ---------------- Bands are coherent ---------------- */

test("no band is inverted, and every band has width", () => {
  for (const cls of ["H7", "N7", "k6", "h6"]) {
    for (const n of [3, 6, 10, 18, 30, 50, 80, 120, 180]) {
      const [lo, hi] = limits(n, cls);
      assert.ok(hi > lo, `${cls} at ${n} mm has upper ${hi} not above lower ${lo}`);
    }
  }
});

test("tolerance bands never shrink as size grows", () => {
  // IT grades widen with nominal size. A band that narrowed would mean a
  // bigger part was being held tighter for no reason.
  for (const cls of ["H7", "N7", "k6", "h6"]) {
    const sizes = [3, 6, 10, 18, 30, 50, 80, 120, 180];
    let previous = 0;
    for (const n of sizes) {
      const [lo, hi] = limits(n, cls);
      const width = hi - lo;
      assert.ok(width >= previous, `${cls} band narrows from ${previous} to ${width} at ${n} mm`);
      previous = width;
    }
  }
});

test("the interference classes really are interference, and the clearance ones are not", () => {
  for (const n of [10, 30, 80]) {
    // N7 housing: the hole is smaller than nominal, so the ring is squeezed.
    const [nLo, nHi] = limits(n, "N7");
    assert.ok(nHi < 0 && nLo < 0, `N7 at ${n} must be entirely below nominal`);
    // H7 housing: at or above nominal, so the ring drops in.
    const [hLo] = limits(n, "H7");
    assert.equal(hLo, 0, `H7 at ${n} starts at nominal`);
    // k6 shaft: at or above nominal, so the ring is pressed on.
    const [kLo] = limits(n, "k6");
    assert.ok(kLo >= 0, `k6 at ${n} must not go below nominal`);
    // h6 shaft: at or below nominal, so the ring slides on.
    const [, hhHi] = limits(n, "h6");
    assert.equal(hhHi, 0, `h6 at ${n} tops out at nominal`);
  }
});

/* ---------------- Bearing lookup ---------------- */

test("suffixes describe seals and cages, not dimensions", () => {
  const plain = findBearing("6203");
  for (const suffixed of ["6203-2RS", "6203 ZZ", "6203-2rs1", "  6203  "]) {
    assert.deepEqual(findBearing(suffixed), plain, `${suffixed} is dimensionally a 6203`);
  }
});

test("a bearing not in the table returns null rather than the nearest one", () => {
  assert.equal(findBearing("6999"), null);
  assert.equal(findBearing("NOT A BEARING"), null);
  assert.equal(findBearing(""), null);
});

test("the ISO 15 boundary dimensions are internally consistent", () => {
  for (const b of BEARINGS) {
    assert.ok(b.outer > b.bore, `${b.designation}: OD must exceed bore`);
    assert.ok(b.width > 0, `${b.designation}: width must be positive`);
  }
  // Within a series, a higher designation is a bigger bearing.
  for (const series of ["6000", "6200", "6300"]) {
    const inSeries = BEARINGS.filter((b) => b.series === series);
    for (let i = 1; i < inSeries.length; i++) {
      assert.ok(inSeries[i].bore >= inSeries[i - 1].bore, `${series}: bores must not go backwards`);
      assert.ok(inSeries[i].outer >= inSeries[i - 1].outer, `${series}: ODs must not go backwards`);
    }
  }
});
