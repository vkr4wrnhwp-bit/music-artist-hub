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

/** Number, letter and fractional drill sizes that actually live in a drill index. */
const DRILL_SIZES = [
  0.0625, 0.0781, 0.0935, 0.096, 0.1015, 0.104, 0.1065, 0.1094, 0.11, 0.113, 0.116, 0.12, 0.125,
  0.1285, 0.136, 0.1405, 0.144, 0.147, 0.1495, 0.1562, 0.159, 0.166, 0.1695, 0.173, 0.177, 0.18,
  0.1875, 0.1935, 0.196, 0.199, 0.201, 0.204, 0.209, 0.213, 0.2188, 0.221, 0.228, 0.234, 0.2344,
  0.238, 0.242, 0.246, 0.25, 0.257, 0.261, 0.266, 0.272, 0.277, 0.281, 0.29, 0.295, 0.302, 0.3125,
  0.316, 0.323, 0.332, 0.339, 0.348, 0.3438, 0.358, 0.368, 0.377, 0.386, 0.397, 0.404, 0.413, 0.42,
  0.4219, 0.428, 0.4375, 0.4531, 0.4688, 0.4844, 0.5,
];

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
    out.push({
      nominalInches,
      label,
      family,
      interpretation,
      deviation: Number(deviation.toFixed(5)),
      confidence: scoreCandidate(measured, nominalInches, uncertainty, metric),
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
    for (const d of DRILL_SIZES) {
      push(
        d,
        `⌀${fmtIn(d)}`,
        "DRILL_SIZE",
        "Standard drill size — likely drilled, not bored",
        "Value matches a size present in a standard drill index.",
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
