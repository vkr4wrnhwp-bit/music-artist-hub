/**
 * FUNCTION BEFORE DIMENSION
 *
 * A measured 1.5744" is not information. It is a number that happens to have
 * come off a part.
 *
 * What makes it information is knowing that a bearing goes in there — because
 * then the question stops being "what did I measure" and becomes "what does
 * this interface have to do", and that question has an answer with a tolerance
 * on it. A bearing seat is not 1.5744" because somebody chose 1.5744". It is
 * ⌀40 mm H7 because a 6203 goes in it, and 1.5744" is what a worn one measures.
 *
 * So this engine reasons from the mating component:
 *
 *   - which standard part is plausibly involved, given what was measured
 *   - whether the feature is the housing (bearing OD) or the shaft (bearing
 *     bore), which are different questions with different answers
 *   - what fit class that interface calls for, and therefore what tolerance
 *     belongs on the print
 *
 * Everything here is a SUGGESTION carrying STANDARD provenance. Nothing is
 * applied. A dimension that came from a table and a dimension that came from
 * an instrument are different kinds of fact, and CANVAS does not let the first
 * quietly become the second.
 */

import type { Provenanced } from "@/lib/provenance";
import { value } from "@/lib/provenance";

export const MATING_COMPONENTS = ["BEARING", "BUSHING", "SHAFT", "SEAL", "FASTENER", "DOWEL", "UNKNOWN"] as const;
export type MatingComponent = (typeof MATING_COMPONENTS)[number];

export const MATING_LABEL: Record<MatingComponent, string> = {
  BEARING: "Bearing",
  BUSHING: "Bushing",
  SHAFT: "Shaft",
  SEAL: "Seal",
  FASTENER: "Fastener",
  DOWEL: "Dowel",
  UNKNOWN: "Unknown",
};

/** Whether the feature under discussion is the hole or the thing that goes in it. */
export type InterfaceSide = "HOUSING" | "SHAFT";

const MM = 25.4;

/* ------------------------------------------------------------------ */
/* Deep groove ball bearings                                           */
/* ------------------------------------------------------------------ */

/**
 * Metric deep groove ball bearings, the 6000/6200/6300 series. Boundary
 * dimensions are standardised in ISO 15 and are identical across
 * manufacturers, which is what makes this table safe to reason from — the
 * dimensions belong to the standard, not to a vendor catalogue.
 */
export interface Bearing {
  designation: string;
  /** Inner diameter, mm — what the shaft journal must be. */
  bore: number;
  /** Outer diameter, mm — what the housing bore must be. */
  outer: number;
  width: number;
  series: string;
}

export const BEARINGS: Bearing[] = [
  // 6000 series — light
  { designation: "6000", bore: 10, outer: 26, width: 8, series: "6000" },
  { designation: "6001", bore: 12, outer: 28, width: 8, series: "6000" },
  { designation: "6002", bore: 15, outer: 32, width: 9, series: "6000" },
  { designation: "6003", bore: 17, outer: 35, width: 10, series: "6000" },
  { designation: "6004", bore: 20, outer: 42, width: 12, series: "6000" },
  { designation: "6005", bore: 25, outer: 47, width: 12, series: "6000" },
  { designation: "6006", bore: 30, outer: 55, width: 13, series: "6000" },
  { designation: "6007", bore: 35, outer: 62, width: 14, series: "6000" },
  { designation: "6008", bore: 40, outer: 68, width: 15, series: "6000" },
  { designation: "6009", bore: 45, outer: 75, width: 16, series: "6000" },
  { designation: "6010", bore: 50, outer: 80, width: 16, series: "6000" },
  // 6200 series — medium, the default for general machinery
  { designation: "6200", bore: 10, outer: 30, width: 9, series: "6200" },
  { designation: "6201", bore: 12, outer: 32, width: 10, series: "6200" },
  { designation: "6202", bore: 15, outer: 35, width: 11, series: "6200" },
  { designation: "6203", bore: 17, outer: 40, width: 12, series: "6200" },
  { designation: "6204", bore: 20, outer: 47, width: 14, series: "6200" },
  { designation: "6205", bore: 25, outer: 52, width: 15, series: "6200" },
  { designation: "6206", bore: 30, outer: 62, width: 16, series: "6200" },
  { designation: "6207", bore: 35, outer: 72, width: 17, series: "6200" },
  { designation: "6208", bore: 40, outer: 80, width: 18, series: "6200" },
  { designation: "6209", bore: 45, outer: 85, width: 19, series: "6200" },
  { designation: "6210", bore: 50, outer: 90, width: 20, series: "6200" },
  // 6300 series — heavy
  { designation: "6300", bore: 10, outer: 35, width: 11, series: "6300" },
  { designation: "6301", bore: 12, outer: 37, width: 12, series: "6300" },
  { designation: "6302", bore: 15, outer: 42, width: 13, series: "6300" },
  { designation: "6303", bore: 17, outer: 47, width: 14, series: "6300" },
  { designation: "6304", bore: 20, outer: 52, width: 15, series: "6300" },
  { designation: "6305", bore: 25, outer: 62, width: 17, series: "6300" },
  { designation: "6306", bore: 30, outer: 72, width: 19, series: "6300" },
  { designation: "6307", bore: 35, outer: 80, width: 21, series: "6300" },
  { designation: "6308", bore: 40, outer: 90, width: 23, series: "6300" },
];

export function findBearing(designation: string): Bearing | null {
  const key = designation.trim().toUpperCase().replace(/[\s-]/g, "");
  // Suffixes describe seals, clearance and cage — none of which change the
  // boundary dimensions, so 6203-2RS is dimensionally a 6203.
  const base = key.match(/^6[0-9]{3}/)?.[0];
  return BEARINGS.find((b) => b.designation === base) ?? null;
}

/* ------------------------------------------------------------------ */
/* Fits                                                                */
/* ------------------------------------------------------------------ */

/**
 * ISO 286 limits for the fit classes a bearing seat actually uses, by nominal
 * size band in mm. Deviations in micrometres.
 *
 * The choice of class is not arbitrary and is not CANVAS's opinion: it follows
 * the standard mounting recommendation, which turns on which ring rotates
 * relative to the load. A ring that turns under load must be an interference
 * fit or it will creep and fret the seat; the stationary ring is left loose
 * enough to be assembled and to allow axial movement for thermal growth.
 */
/**
 * ISO 286 size bands are stated as "over X up to and INCLUDING Y", so `upTo`
 * is an inclusive bound and `fitFor` selects with `<=`.
 *
 * It used to be exclusive, and the tables used to start at 30. Two things
 * went wrong, both of them widening the tolerance and both presented to the
 * operator as "per ISO 286":
 *
 *   Below 18 mm there was no band at all, so a 15 mm bearing bore fell into
 *   the 18–30 row: k6 came out +2/+15 µm where the standard says +1/+12.
 *
 *   An exact boundary size fell through to the NEXT band, because 30 is not
 *   less than 30. A 6006's 30 mm bore got the 30–50 row: k6 +2/+18 instead of
 *   +2/+15.
 *
 * Nineteen bearings in the table below are affected, including the 6000,
 * 6200 and 6300 series. On an interference fit a wider, upward-shifted band
 * means more interference than the standard allows — which on a bearing seat
 * crushes the outer race and takes out the internal clearance, or splits the
 * housing. This is the one place in CANVAS where a table is presented as
 * engineering fact rather than as DEVELOPMENT ANALYSIS, so it has to be the
 * standard's numbers exactly.
 */
interface FitBand {
  upTo: number; // mm, INCLUSIVE upper bound of the size band
  lower: number; // µm
  upper: number; // µm
}

const FIT_TABLE: Record<string, FitBand[]> = {
  // Housing bore, stationary outer ring — the normal case.
  H7: [
    { upTo: 3, lower: 0, upper: 10 },
    { upTo: 6, lower: 0, upper: 12 },
    { upTo: 10, lower: 0, upper: 15 },
    { upTo: 18, lower: 0, upper: 18 },
    { upTo: 30, lower: 0, upper: 21 },
    { upTo: 50, lower: 0, upper: 25 },
    { upTo: 80, lower: 0, upper: 30 },
    { upTo: 120, lower: 0, upper: 35 },
    { upTo: 180, lower: 0, upper: 40 },
  ],
  // Housing bore, rotating outer ring — interference.
  N7: [
    { upTo: 3, lower: -14, upper: -4 },
    { upTo: 6, lower: -16, upper: -4 },
    { upTo: 10, lower: -19, upper: -4 },
    { upTo: 18, lower: -23, upper: -5 },
    { upTo: 30, lower: -28, upper: -7 },
    { upTo: 50, lower: -33, upper: -8 },
    { upTo: 80, lower: -39, upper: -9 },
    { upTo: 120, lower: -45, upper: -10 },
    { upTo: 180, lower: -52, upper: -12 },
  ],
  // Shaft journal, rotating inner ring — interference.
  k6: [
    { upTo: 3, lower: 0, upper: 6 },
    { upTo: 6, lower: 1, upper: 9 },
    { upTo: 10, lower: 1, upper: 10 },
    { upTo: 18, lower: 1, upper: 12 },
    { upTo: 30, lower: 2, upper: 15 },
    { upTo: 50, lower: 2, upper: 18 },
    { upTo: 80, lower: 2, upper: 21 },
    { upTo: 120, lower: 3, upper: 25 },
    { upTo: 180, lower: 3, upper: 28 },
  ],
  // Shaft journal, stationary inner ring — transition.
  h6: [
    { upTo: 3, lower: -6, upper: 0 },
    { upTo: 6, lower: -8, upper: 0 },
    { upTo: 10, lower: -9, upper: 0 },
    { upTo: 18, lower: -11, upper: 0 },
    { upTo: 30, lower: -13, upper: 0 },
    { upTo: 50, lower: -16, upper: 0 },
    { upTo: 80, lower: -19, upper: 0 },
    { upTo: 120, lower: -22, upper: 0 },
    { upTo: 180, lower: -25, upper: 0 },
  ],
};

export interface FitResult {
  fitClass: string;
  /** Nominal size the class applies to, mm. */
  nominalMm: number;
  /** Limits in inches, relative to nominal. */
  lowerIn: number;
  upperIn: number;
  /** Total tolerance band, inches. */
  bandIn: number;
  minIn: number;
  maxIn: number;
  rationale: string;
}

export function fitFor(nominalMm: number, fitClass: string, rationale: string): FitResult | null {
  const bands = FIT_TABLE[fitClass];
  if (!bands) return null;
  // A nominal of zero or less is not a size. ISO's first band is "up to and
  // including 3 mm" with no lower bound, so without this a negative nominal
  // would quietly collect the smallest band's limits.
  if (!Number.isFinite(nominalMm) || nominalMm <= 0) return null;
  // Inclusive: ISO bands run "over X up to and including Y".
  const band = bands.find((b) => nominalMm <= b.upTo);
  if (!band) return null;

  const lowerIn = band.lower / 1000 / MM;
  const upperIn = band.upper / 1000 / MM;
  const nominalIn = nominalMm / MM;

  return {
    fitClass,
    nominalMm,
    lowerIn: Number(lowerIn.toFixed(5)),
    upperIn: Number(upperIn.toFixed(5)),
    bandIn: Number((upperIn - lowerIn).toFixed(5)),
    minIn: Number((nominalIn + lowerIn).toFixed(4)),
    maxIn: Number((nominalIn + upperIn).toFixed(4)),
    rationale,
  };
}

/* ------------------------------------------------------------------ */
/* Reasoning from the interface                                        */
/* ------------------------------------------------------------------ */

export interface MatingRequest {
  /** What was measured, inches. */
  measured: number;
  component: MatingComponent;
  side: InterfaceSide;
  /** Typed by the operator, if they know it. */
  designation?: string | null;
  /** True when the ring on this side turns relative to the load. */
  rotatingUnderLoad?: boolean;
  /**
   * Uncertainty of the instrument the measurement came from, inches.
   *
   * This matters more than it looks. Calipers carry roughly ±0.002", and a
   * bearing fit class is a 0.001" band — so a caliper reading simply cannot
   * distinguish "on nominal" from "four thou under". Reporting a discrepancy
   * smaller than the instrument's own noise as though it were a property of
   * the part is how software teaches people to distrust it.
   */
  measurementUncertainty?: number | null;
}

export interface MatingCandidate {
  bearing: Bearing;
  /** Nominal this feature would be, mm. */
  nominalMm: number;
  /** Difference between measured and that nominal, inches. */
  differenceIn: number;
  fit: FitResult | null;
  /** Whether the measured value falls inside the fit class limits. */
  withinFit: boolean | null;
}

export interface MatingAnalysis {
  ok: boolean;
  component: MatingComponent;
  side: InterfaceSide;
  /** Best candidate, when one is clearly ahead. */
  best: MatingCandidate | null;
  /** Everything within reach, so the operator can disagree with the pick. */
  candidates: MatingCandidate[];
  /** Suggested nominal — never applied, always provenanced. */
  suggestedNominal: Provenanced<number>;
  reasoning: string;
  /** What CANVAS needs before it can say more. */
  needs: string[];
}

/**
 * Roughly the amount a housing bore can be off nominal and still plausibly be
 * that nominal. Wider than any fit class, because a reverse-engineered part is
 * usually worn, and a bore that has spun a bearing can be several thousandths
 * over. Too tight a window and the engine refuses to recognise exactly the
 * parts most likely to be sitting on the bench.
 */
const RECOGNITION_WINDOW_IN = 0.012;

export function analyseMating(request: MatingRequest): MatingAnalysis {
  const { measured, component, side } = request;
  const needs: string[] = [];

  const empty = (reasoning: string): MatingAnalysis => ({
    ok: false,
    component,
    side,
    best: null,
    candidates: [],
    suggestedNominal: value<number>(null, "DEFAULT", "UNKNOWN", { note: reasoning }),
    reasoning,
    needs,
  });

  if (component === "UNKNOWN") {
    needs.push("What mates with this feature");
    return empty(
      "Nothing can be inferred about the intent behind this dimension until it is known what goes in it. The same 1.5744\" is a bearing seat, a slip fit for a shaft, or a clearance hole depending entirely on what it does.",
    );
  }

  if (component !== "BEARING") {
    // The other component families are real and are not modelled yet. Saying
    // so is the honest answer; inventing a fit for a seal would be worse than
    // returning nothing.
    needs.push(`Standard dimension tables for ${MATING_LABEL[component].toLowerCase()}s`);
    return empty(
      `CANVAS reasons from bearing interfaces today. ${MATING_LABEL[component]} interfaces are recorded against the feature and carried through to inspection, but the standard tables that would let CANVAS propose a nominal and a fit for them are not built.`,
    );
  }

  /* ---- Bearing, explicitly named ---- */

  if (request.designation) {
    const bearing = findBearing(request.designation);
    if (!bearing) {
      return empty(
        `"${request.designation}" is not in the deep groove ball bearing table. CANVAS carries the 6000, 6200 and 6300 series from ISO 15; other families are not loaded, so the dimension cannot be checked against the part.`,
      );
    }
    const candidate = evaluate(bearing, measured, side, request.rotatingUnderLoad ?? false);
    return {
      ok: true,
      component,
      side,
      best: candidate,
      candidates: [candidate],
      suggestedNominal: value<number>(candidate.nominalMm / MM, "STANDARD", "HIGH", {
        note: `${bearing.designation} ${side === "HOUSING" ? "outer diameter" : "bore"} per ISO 15`,
      }),
      reasoning: describe(candidate, bearing, side, measured, request.measurementUncertainty ?? null),
      needs: [],
    };
  }

  /* ---- Bearing, inferred from the dimension ---- */

  const key = side === "HOUSING" ? "outer" : "bore";
  const candidates = BEARINGS.map((b) => evaluate(b, measured, side, request.rotatingUnderLoad ?? false))
    .filter((c) => Math.abs(c.differenceIn) <= RECOGNITION_WINDOW_IN)
    .sort((a, b) => Math.abs(a.differenceIn) - Math.abs(b.differenceIn));

  if (candidates.length === 0) {
    return empty(
      `No standard deep groove ball bearing has ${key === "outer" ? "an outer diameter" : "a bore"} within ${RECOGNITION_WINDOW_IN.toFixed(3)}" of ${measured.toFixed(4)}". This may be a bearing family CANVAS does not carry — tapered roller, needle, angular contact — or the feature may not be a bearing seat at all.`,
    );
  }

  // Several bearings share a boundary dimension, which is the point of the
  // series system. Where they do, the dimension alone cannot choose between
  // them, and saying which is which is the operator's job.
  const sameNominal = candidates.filter((c) => c.nominalMm === candidates[0].nominalMm);
  const best = candidates[0];

  if (sameNominal.length > 1) {
    needs.push("Bearing designation, or the width across the outer ring");
  }

  return {
    ok: true,
    component,
    side,
    best,
    candidates: candidates.slice(0, 5),
    suggestedNominal: value<number>(best.nominalMm / MM, "STANDARD", "MEDIUM", {
      note: `Inferred from ${side === "HOUSING" ? "housing bore" : "shaft"} dimension — ${sameNominal.length > 1 ? `${sameNominal.length} bearings share this size` : best.bearing.designation}`,
    }),
    reasoning:
      sameNominal.length > 1
        ? `${describe(best, best.bearing, side, measured, request.measurementUncertainty ?? null)} ${sameNominal.length} bearings in the table share that ${key === "outer" ? "outer diameter" : "bore"} — ${sameNominal.map((c) => c.bearing.designation).join(", ")} — and they differ in width and load rating. The dimension alone cannot tell them apart.`
        : describe(best, best.bearing, side, measured, request.measurementUncertainty ?? null),
    needs,
  };
}

function evaluate(bearing: Bearing, measured: number, side: InterfaceSide, rotating: boolean): MatingCandidate {
  const nominalMm = side === "HOUSING" ? bearing.outer : bearing.bore;
  const nominalIn = nominalMm / MM;

  const fitClass =
    side === "HOUSING" ? (rotating ? "N7" : "H7") : rotating ? "k6" : "h6";
  const rationale =
    side === "HOUSING"
      ? rotating
        ? "The outer ring turns relative to the load, so it must be an interference fit or it will creep in the housing and fret the seat."
        : "The outer ring is stationary relative to the load, so it is left slightly loose to be assembled and to allow axial movement as the assembly grows with heat."
      : rotating
        ? "The inner ring turns relative to the load, so the shaft is an interference fit or the ring will creep and fret the journal."
        : "The inner ring is stationary relative to the load, so a transition fit is enough.";

  const fit = fitFor(nominalMm, fitClass, rationale);
  const withinFit = fit ? measured >= fit.minIn && measured <= fit.maxIn : null;

  return {
    bearing,
    nominalMm,
    differenceIn: Number((measured - nominalIn).toFixed(5)),
    fit,
    withinFit,
  };
}

function describe(
  c: MatingCandidate,
  bearing: Bearing,
  side: InterfaceSide,
  measured: number,
  uncertainty: number | null,
): string {
  const nominalIn = c.nominalMm / MM;
  const which = side === "HOUSING" ? "outer diameter" : "bore";
  const diff = Math.abs(c.differenceIn);
  const direction = c.differenceIn > 0 ? "over" : "under";

  // Below half a tenth the two numbers are the same number to four places,
  // and "0.0000 under" reads as a defect in the software rather than as a
  // match.
  const exact = diff < 0.00005;

  const base = exact
    ? `${measured.toFixed(4)}" is ⌀${c.nominalMm} mm (${nominalIn.toFixed(5)}"), the ${which} of a ${bearing.designation} — ${bearing.bore} × ${bearing.outer} × ${bearing.width} mm.`
    : `${measured.toFixed(4)}" is ${diff.toFixed(4)}" ${direction} ⌀${c.nominalMm} mm (${nominalIn.toFixed(5)}"), which is the ${which} of a ${bearing.designation} — ${bearing.bore} × ${bearing.outer} × ${bearing.width} mm.`;

  if (!c.fit) return base;

  const limits = `${c.fit.fitClass} (${c.fit.minIn.toFixed(4)}–${c.fit.maxIn.toFixed(4)}")`;

  if (exact) {
    return c.withinFit
      ? `${base} It sits inside ${limits}, which is the standard mounting fit for this interface.`
      : `${base} Note that it sits on nominal rather than inside ${limits} — a bore machined exactly to the nominal is at the bottom of the H-series band, which is a legitimate target but leaves nothing for the bearing to be pressed into.`;
  }

  // Before attributing a discrepancy to the part, check it is larger than the
  // instrument that produced it. A 0.0004" departure read on ±0.002" calipers
  // is not a property of the bore — it is noise, and the honest conclusion is
  // that this measurement cannot resolve the question at all.
  if (uncertainty != null && diff <= uncertainty) {
    return `${base} The ${diff.toFixed(4)}" departure is smaller than the ±${uncertainty.toFixed(4)}" uncertainty of the instrument it was measured with, so it is not evidence of anything about the part. This measurement cannot tell you whether the bore is inside ${limits} — a more capable instrument can.`;
  }

  if (c.withinFit === false && c.differenceIn > 0 && side === "HOUSING") {
    return `${base} That is above the top limit of ${limits}. A housing bore oversize is the signature of a seat that has had a bearing spinning in it, so the measurement may be describing wear rather than intent.`;
  }
  if (c.withinFit === false && c.differenceIn < 0 && side === "HOUSING") {
    return `${base} That is below the bottom limit of ${limits}. An undersize housing bore is not wear — wear opens a bore up — so this is either a different fit class, a bore that was never finished to size, or a measurement taken across a burr or an out-of-round section.`;
  }
  if (c.withinFit === false) {
    return `${base} That is outside ${limits}, so either the fit class is not the one this design used, or the feature is worn or damaged.`;
  }
  return `${base} It sits inside ${limits}, which is the standard mounting fit for this interface.`;
}
