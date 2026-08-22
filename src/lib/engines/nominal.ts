/**
 * NOMINAL DIMENSION REASONING
 *
 * A measurement is evidence, not intent. 1.5744" off a bore gauge is almost
 * certainly a 40 mm bearing seat that has seen some wear — but CANVAS must
 * never silently rewrite it, because if it is genuinely a 1.574" custom bore
 * a silent "correction" produces a scrap part with a confident-looking model
 * behind it.
 *
 * This engine is entirely deterministic — table lookups against published
 * standards, no model inference. That matters: the suggestion carries a
 * STANDARD provenance and a real, explainable basis, not a hunch.
 */

export const MM_PER_INCH = 25.4;

export type StandardFamily =
  | "METRIC_BEARING"
  | "INCH_BEARING"
  | "METRIC_ROUND"
  | "INCH_FRACTION"
  | "DRILL_SIZE"
  | "THREAD_MAJOR"
  | "DOWEL_PIN"
  | "O_RING_GROOVE"
  | "STOCK_THICKNESS";

export interface NominalCandidate {
  /** Value expressed in the part's working units (inches). */
  nominalInches: number;
  /** Human label, e.g. "40 mm" or "1-1/2 in". */
  label: string;
  family: StandardFamily;
  /** What this standard value normally means functionally. */
  interpretation: string;
  /** Signed deviation, inches: measured - nominal. */
  deviation: number;
  /** 0–1. Derived from deviation relative to instrument uncertainty. */
  confidence: number;
  /** Plain-language explanation shown next to the suggestion. */
  basis: string;
}

/* ------------------------------------------------------------------ */
/* Standards tables                                                    */
/* ------------------------------------------------------------------ */

/** Common metric ball bearing bore/OD sizes, mm. */
const METRIC_BEARING_MM = [
  6, 7, 8, 9, 10, 12, 15, 17, 20, 22, 25, 28, 30, 32, 35, 40, 42, 45, 47, 50, 52, 55, 60, 62, 65,
  68, 70, 72, 75, 80, 85, 90, 95, 100, 110, 120, 125, 130, 140, 150,
];

/** Common inch-series bearing bores. */
const INCH_BEARING = [
  0.25, 0.3125, 0.375, 0.4375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75,
  2.0, 2.25, 2.5,
];

/** Standard metric round bar / shaft diameters, mm. */
const METRIC_ROUND_MM = [
  3, 4, 5, 6, 8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 38, 40, 45, 50, 55, 60, 63, 70, 75,
  80, 90, 100,
];

/** Inch fractions down to 1/64. */
const INCH_FRACTIONS = Array.from({ length: 256 }, (_, i) => (i + 1) / 64).filter((v) => v <= 4);

/**
 * The drill index, as three published series rather than one hand-kept list.
 *
 * This was previously a flat array of decimals with no designations, and it
 * had holes in it: 3/8, 13/64, 11/64, 23/64 and four other fractional drills
 * were absent, and #43 — the tap drill this file's own #4-40 row names — was
 * absent too. A hole drilled 0.3750 therefore matched letter V (0.377) and
 * came back as a 0.003" oversize letter drill instead of the 3/8 it obviously
 * was. It also carried 0.420, which is not a drill size in any series; the
 * neighbouring entries suggest a decimal slip from #58 (0.0420).
 *
 * Keeping the designation alongside the diameter matters at the counter: a
 * machinist reaches for "letter S", not for "0.3480".
 */
interface DrillSize {
  d: number;
  /** The designation stamped on the shank. */
  label: string;
}

/** Number drills #1–#60 (ANSI/ASME B94.11M). */
const NUMBER_DRILLS: DrillSize[] = [
  [1, 0.228], [2, 0.221], [3, 0.213], [4, 0.209], [5, 0.2055], [6, 0.204], [7, 0.201], [8, 0.199],
  [9, 0.196], [10, 0.1935], [11, 0.191], [12, 0.189], [13, 0.185], [14, 0.182], [15, 0.18],
  [16, 0.177], [17, 0.173], [18, 0.1695], [19, 0.166], [20, 0.161], [21, 0.159], [22, 0.157],
  [23, 0.154], [24, 0.152], [25, 0.1495], [26, 0.147], [27, 0.144], [28, 0.1405], [29, 0.136],
  [30, 0.1285], [31, 0.12], [32, 0.116], [33, 0.113], [34, 0.111], [35, 0.11], [36, 0.1065],
  [37, 0.104], [38, 0.1015], [39, 0.0995], [40, 0.098], [41, 0.096], [42, 0.0935], [43, 0.089],
  [44, 0.086], [45, 0.082], [46, 0.081], [47, 0.0785], [48, 0.076], [49, 0.073], [50, 0.07],
  [51, 0.067], [52, 0.0635], [53, 0.0595], [54, 0.055], [55, 0.052], [56, 0.0465], [57, 0.043],
  [58, 0.042], [59, 0.041], [60, 0.04],
].map(([n, d]) => ({ d, label: `#${n}` }));

/** Letter drills A–Z. */
const LETTER_DRILLS: DrillSize[] = [
  ["A", 0.234], ["B", 0.238], ["C", 0.242], ["D", 0.246], ["E", 0.25], ["F", 0.257], ["G", 0.261],
  ["H", 0.266], ["I", 0.272], ["J", 0.277], ["K", 0.281], ["L", 0.29], ["M", 0.295], ["N", 0.302],
  ["O", 0.316], ["P", 0.323], ["Q", 0.332], ["R", 0.339], ["S", 0.348], ["T", 0.358], ["U", 0.368],
  ["V", 0.377], ["W", 0.386], ["X", 0.397], ["Y", 0.404], ["Z", 0.413],
].map(([letter, d]) => ({ d: d as number, label: `letter ${letter}` }));

/** Fractional drills, 1/16 through 1/2 by 64ths — the whole index, no gaps. */
const FRACTIONAL_DRILLS: DrillSize[] = Array.from({ length: 29 }, (_, i) => {
  const sixtyFourths = i + 4; // 4/64 = 1/16 up to 32/64 = 1/2
  return { d: sixtyFourths / 64, label: toFractionLabel(sixtyFourths / 64) };
});

const DRILL_SIZES: DrillSize[] = [...FRACTIONAL_DRILLS, ...NUMBER_DRILLS, ...LETTER_DRILLS].sort(
  (a, b) => a.d - b.d,
);

/** Unified and metric coarse thread major diameters. */
const THREADS: { label: string; major: number; note: string }[] = [
  { label: "#4-40 UNC", major: 0.112, note: "clearance ⌀0.1160, tap drill ⌀0.0890" },
  { label: "#6-32 UNC", major: 0.138, note: "clearance ⌀0.1440, tap drill ⌀0.1065" },
  { label: "#8-32 UNC", major: 0.164, note: "clearance ⌀0.1695, tap drill ⌀0.1360" },
  { label: "#10-24 UNC", major: 0.19, note: "clearance ⌀0.1960, tap drill ⌀0.1495" },
  { label: "#10-32 UNF", major: 0.19, note: "clearance ⌀0.1960, tap drill ⌀0.1590" },
  { label: "1/4-20 UNC", major: 0.25, note: "clearance ⌀0.2660, tap drill ⌀0.2010 (#7)" },
  { label: "1/4-28 UNF", major: 0.25, note: "clearance ⌀0.2660, tap drill ⌀0.2130 (#3)" },
  { label: "5/16-18 UNC", major: 0.3125, note: "clearance ⌀0.3320, tap drill ⌀0.2570 (F)" },
  { label: "3/8-16 UNC", major: 0.375, note: "clearance ⌀0.3970, tap drill ⌀0.3125" },
  { label: "1/2-13 UNC", major: 0.5, note: "clearance ⌀0.5312, tap drill ⌀0.4219" },
  { label: "M3 × 0.5", major: 3 / MM_PER_INCH, note: "clearance ⌀3.4 mm, tap drill ⌀2.5 mm" },
  { label: "M4 × 0.7", major: 4 / MM_PER_INCH, note: "clearance ⌀4.5 mm, tap drill ⌀3.3 mm" },
  { label: "M5 × 0.8", major: 5 / MM_PER_INCH, note: "clearance ⌀5.5 mm, tap drill ⌀4.2 mm" },
  { label: "M6 × 1.0", major: 6 / MM_PER_INCH, note: "clearance ⌀6.6 mm, tap drill ⌀5.0 mm" },
  { label: "M8 × 1.25", major: 8 / MM_PER_INCH, note: "clearance ⌀9.0 mm, tap drill ⌀6.8 mm" },
  { label: "M10 × 1.5", major: 10 / MM_PER_INCH, note: "clearance ⌀11.0 mm, tap drill ⌀8.5 mm" },
];

/** Standard dowel pin diameters, inch and metric. */
const DOWEL_INCH = [0.0625, 0.09375, 0.125, 0.1875, 0.25, 0.3125, 0.375, 0.5];
const DOWEL_METRIC_MM = [2, 3, 4, 5, 6, 8, 10, 12, 16];

/** Common mill-supplied plate thicknesses, inches. */
const STOCK_THICKNESS = [
  0.125, 0.1875, 0.25, 0.3125, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0,
];

/* ------------------------------------------------------------------ */
/* Matching                                                            */
/* ------------------------------------------------------------------ */

export interface NominalQuery {
  /** Measured value in inches. */
  measured: number;
  /** Instrument uncertainty in inches — from the metrology device used. */
  uncertainty: number;
  /** Narrows the search when the functional role is already known. */
  context?: "BORE" | "SHAFT" | "HOLE" | "THREAD" | "THICKNESS" | "GENERAL";
  /** Whether the surface is expected to be worn (used bearing seats etc.). */
  wearExpected?: boolean;
}

/**
 * Confidence model, deliberately simple and explainable:
 *   - deviation inside the instrument's uncertainty → very strong
 *   - deviation inside ~3× uncertainty → plausible
 *   - beyond that → falls off fast
 * A metric candidate that lands on an ugly inch number gets a small boost,
 * because "1.5748" is a much stronger metric signal than "1.5000".
 */
function scoreCandidate(measured: number, nominal: number, uncertainty: number, metricBoost: boolean): number {
  const dev = Math.abs(measured - nominal);
  const u = Math.max(uncertainty, 0.00005);
  const ratio = dev / u;
  let score = ratio <= 1 ? 0.97 : ratio <= 3 ? 0.9 - (ratio - 1) * 0.08 : Math.max(0, 0.74 - (ratio - 3) * 0.09);
  if (metricBoost && !isRoundInch(nominal)) score = Math.min(0.99, score + 0.04);
  return Number(score.toFixed(3));
}

/** True when a value is a "nice" inch number a designer would plausibly pick. */
function isRoundInch(v: number): boolean {
  const scaled = v * 1000;
  return Math.abs(scaled - Math.round(scaled)) < 1e-6 && Math.round(scaled) % 5 === 0;
}

const fmtIn = (v: number) => v.toFixed(4);
const fmtMm = (v: number) => (Math.abs(v - Math.round(v)) < 0.01 ? String(Math.round(v)) : v.toFixed(2));

export function findNominalCandidates(q: NominalQuery): NominalCandidate[] {
  const { measured, uncertainty } = q;
  // A non-finite measurement or uncertainty used to pass straight through the
  // window filter, because `Math.abs(NaN) > window` is false and so is
  // `x > NaN`. Every table entry was then accepted, scored NaN, and
  // bestNominalSuggestion returned one of them — `NaN < 0.7` is false. An
  // empty field became a confident standard-value suggestion. There is no
  // nominal to infer from a measurement that does not exist.
  if (!Number.isFinite(measured) || measured <= 0) return [];
  if (!Number.isFinite(uncertainty) || uncertainty < 0) return [];
  // Wear opens the search window: a worn bearing seat measures over nominal.
  const window = Math.max(uncertainty * 6, q.wearExpected ? 0.004 : 0.0015);
  const out: NominalCandidate[] = [];

  const push = (
    nominalInches: number,
    label: string,
    family: StandardFamily,
    interpretation: string,
    basis: string,
    metric: boolean,
  ) => {
    const deviation = measured - nominalInches;
    if (Math.abs(deviation) > window) return;
    const confidence = scoreCandidate(measured, nominalInches, uncertainty, metric);
    // The window and the scoring curve are two different judgements and they
    // disagree at the edges: a coarse-window match can be far enough out that
    // scoreCandidate floors it at zero, and the candidate was still listed.
    // A row the engine itself scored at no confidence is not a candidate —
    // it is a standard value that happens to be in the neighbourhood, and
    // shown in a list beside real matches it reads as one.
    if (confidence <= 0) return;
    out.push({
      nominalInches,
      label,
      family,
      interpretation,
      deviation: Number(deviation.toFixed(5)),
      confidence,
      basis,
    });
  };

  const ctx = q.context ?? "GENERAL";

  if (ctx === "BORE" || ctx === "GENERAL") {
    for (const mm of METRIC_BEARING_MM) {
      push(
        mm / MM_PER_INCH,
        `${fmtMm(mm)} mm`,
        "METRIC_BEARING",
        `Standard metric bearing outer race seat (${fmtMm(mm)} mm = ${fmtIn(mm / MM_PER_INCH)}")`,
        `${fmtMm(mm)} mm is a stocked metric bearing size; the measured value falls within the expected seat tolerance band.`,
        true,
      );
    }
    for (const inch of INCH_BEARING) {
      push(
        inch,
        `${fmtIn(inch)} in`,
        "INCH_BEARING",
        "Inch-series bearing seat",
        "Matches a standard inch-series bearing bore/OD.",
        false,
      );
    }
  }

  if (ctx === "SHAFT" || ctx === "GENERAL") {
    for (const mm of METRIC_ROUND_MM) {
      push(
        mm / MM_PER_INCH,
        `${fmtMm(mm)} mm`,
        "METRIC_ROUND",
        `Standard metric shaft / round bar diameter (${fmtMm(mm)} mm)`,
        `${fmtMm(mm)} mm is a standard metric bar stock size.`,
        true,
      );
    }
  }

  if (ctx === "HOLE" || ctx === "GENERAL") {
    for (const drill of DRILL_SIZES) {
      push(
        drill.d,
        `${drill.label} (⌀${fmtIn(drill.d)})`,
        "DRILL_SIZE",
        "Standard drill size — likely drilled, not bored",
        `Matches ${drill.label} in a standard drill index.`,
        false,
      );
    }
    for (const d of DOWEL_INCH) {
      push(d, `${fmtIn(d)} dowel`, "DOWEL_PIN", "Inch dowel pin location", "Matches a standard inch dowel pin diameter.", false);
    }
    for (const mm of DOWEL_METRIC_MM) {
      push(
        mm / MM_PER_INCH,
        `${fmtMm(mm)} mm dowel`,
        "DOWEL_PIN",
        "Metric dowel pin location",
        `Matches a standard ${fmtMm(mm)} mm dowel pin.`,
        true,
      );
    }
  }

  if (ctx === "THREAD" || ctx === "GENERAL") {
    for (const t of THREADS) {
      push(t.major, t.label, "THREAD_MAJOR", `Thread major diameter — ${t.note}`, `Matches the major diameter of ${t.label}.`, t.label.startsWith("M"));
    }
  }

  if (ctx === "THICKNESS" || ctx === "GENERAL") {
    for (const t of STOCK_THICKNESS) {
      push(
        t,
        `${fmtIn(t)} plate`,
        "STOCK_THICKNESS",
        "Standard mill plate thickness — part may be un-machined on this axis",
        "Matches a commonly stocked plate thickness.",
        false,
      );
    }
  }

  if (ctx === "GENERAL") {
    for (const f of INCH_FRACTIONS) {
      push(f, `${toFractionLabel(f)} in`, "INCH_FRACTION", "Fractional inch dimension", "Matches a common fractional inch value.", false);
    }
  }

  // Dedupe on nominal value, keep the most specific (highest confidence) family.
  const byValue = new Map<string, NominalCandidate>();
  for (const c of out) {
    const key = c.nominalInches.toFixed(5);
    const existing = byValue.get(key);
    if (!existing || c.confidence > existing.confidence) byValue.set(key, c);
  }

  return [...byValue.values()].sort((a, b) => b.confidence - a.confidence).slice(0, 5);
}

/**
 * Returns a suggestion only when it is strong enough to be worth interrupting
 * the operator over. Everything else stays in the candidate list.
 */
export function bestNominalSuggestion(q: NominalQuery): NominalCandidate | null {
  const candidates = findNominalCandidates(q);
  if (candidates.length === 0) return null;
  const [top, second] = candidates;
  if (top.confidence < 0.7) return null;
  // If two candidates are effectively tied, this is not a clear enough signal
  // to present as "likely engineering intent".
  if (second && top.confidence - second.confidence < 0.03) return null;
  return top;
}

function toFractionLabel(v: number): string {
  const denom = 64;
  let n = Math.round(v * denom);
  let d = denom;
  const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b));
  const g = gcd(n, d);
  n /= g;
  d /= g;
  if (d === 1) return String(n);
  const whole = Math.floor(n / d);
  const rem = n - whole * d;
  return whole > 0 ? `${whole}-${rem}/${d}` : `${n}/${d}`;
}

export const inchesToMm = (v: number) => v * MM_PER_INCH;
export const mmToInches = (v: number) => v / MM_PER_INCH;
