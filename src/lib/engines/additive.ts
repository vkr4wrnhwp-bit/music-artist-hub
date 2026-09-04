import type { Feature } from "@/lib/domain/features";
import type { LoadingType, PartIntent } from "@/lib/domain/part-intent";

/**
 * SHOULD THIS BE PRINTED?
 *
 * The method advisor already listed additive, and reasoned about it only from
 * feature count and volume — "geometry is prismatic and machines efficiently"
 * either way, whatever the part's tolerances were and whatever the shop owned.
 * A shop with a Prusa on the bench and a ±0.0005 bearing bore on the drawing
 * got the same sentence as a shop with a laser powder-bed machine.
 *
 * This answers the question against what the shop actually has, and the three
 * things that decide it:
 *
 *   TOLERANCE. A printer holds what it holds. A ±0.008 machine cannot produce
 *   a ±0.0005 bore, and no orientation, layer height or wishful thinking
 *   changes that. This is the same gauge-maker's arithmetic the inspection
 *   gate uses, pointed at a process instead of an instrument.
 *
 *   ANISOTROPY. This is the one a machinist most needs told. A printed part is
 *   continuous within a layer and BONDED between layers, so its strength
 *   through Z is a fraction of its strength in XY — commonly half, sometimes a
 *   quarter. A part loaded across the layers is a different part from the one
 *   the datasheet describes. Where the shop records both figures the engine
 *   uses them; where it records only one, it says so rather than assuming
 *   isotropy, which is the assumption that breaks the part.
 *
 *   SERVICE CONDITIONS. A polymer above its deflection temperature is not a
 *   structural material, and a sustained load in a polymer is a creep question
 *   that a tensile figure does not answer.
 *
 * WHAT IT WILL NOT DO
 *
 * It will not recommend printing a part whose responsibility profile is
 * unknown. Not knowing what a part carries is not the same as it carrying
 * nothing, and additive changes material properties more than any other
 * substitution in the advisor's list.
 */

export const PRINT_TECHNOLOGIES = ["FDM", "SLA", "SLS", "MJF", "METAL_PBF", "BINDER_JET"] as const;
export type PrintTechnology = (typeof PRINT_TECHNOLOGIES)[number];

export const TECHNOLOGY_LABEL: Record<PrintTechnology, string> = {
  FDM: "FDM — fused filament",
  SLA: "SLA — resin",
  SLS: "SLS — nylon powder",
  MJF: "MJF — multi jet fusion",
  METAL_PBF: "Metal powder-bed fusion",
  BINDER_JET: "Binder jetting",
};

export interface PrinterRecord {
  id: string;
  manufacturer: string;
  model: string;
  technology: string;
  buildX: number;
  buildY: number;
  buildZ: number;
  /** Plus/minus, inches, as this shop has measured it. Null when unmeasured. */
  achievableTolerance: number | null;
  achievableRa: number | null;
}

export interface PrintMaterialRecord {
  id: string;
  name: string;
  technology: string;
  tensileXY: number | null;
  tensileZ: number | null;
  maxServiceTempF: number | null;
  creepDataOnFile: boolean;
}

/**
 * Whether a recorded pair of tensile figures is physically possible.
 *
 * A printed part is continuous within a layer and bonded between them, so it
 * cannot be stronger across the layers than within them. A row entered the
 * wrong way round is not merely wrong — the anisotropy check would then report
 * the part is fine in the direction it is actually weakest.
 *
 * Lives here rather than in the form action because it is an engineering rule,
 * and because a rule inside a "use server" module cannot be exported to a test.
 */
export function anisotropyIsPossible(tensileXY: number | null, tensileZ: number | null): boolean {
  if (tensileXY === null || tensileZ === null) return true;
  return tensileZ <= tensileXY;
}

export interface AdditiveInput {
  intent: PartIntent;
  features: Feature[];
  /** Finished envelope, inches. Null when the part has no size recorded. */
  envelope: { x: number; y: number; z: number } | null;
  printers: PrinterRecord[];
  printMaterials: PrintMaterialRecord[];
}

export type AdditiveVerdict = "VIABLE" | "REVIEW" | "NOT_RECOMMENDED" | "INSUFFICIENT_DATA";

export interface AdditiveFinding {
  /** What was checked. */
  check: "BUILD_VOLUME" | "TOLERANCE" | "ANISOTROPY" | "TEMPERATURE" | "CREEP" | "RESPONSIBILITY";
  verdict: AdditiveVerdict;
  /** A machinist's sentence, with the numbers in it. */
  detail: string;
}

export interface AdditiveAssessment {
  printerId: string;
  printerLabel: string;
  technology: string;
  verdict: AdditiveVerdict;
  findings: AdditiveFinding[];
  /** The honest middle path, when there is one. */
  hybridNote: string | null;
}

export interface AdditiveResult {
  assessments: AdditiveAssessment[];
  /** Why nothing could be assessed, when nothing could. */
  unavailable: string | null;
  /** The tightest band on the part, inches, or null when nothing is toleranced. */
  tightestBand: number | null;
}

/**
 * Loads that act through the layers rather than within them.
 *
 * A printed part is at its weakest across the bond between layers, and these
 * are the load types where that governs rather than being a detail. Static
 * compression down the build axis is the one case that is genuinely fine, and
 * it is not in this list.
 */
const LAYER_SENSITIVE: LoadingType[] = ["CYCLIC", "SHOCK", "IMPACT", "VIBRATION", "BENDING", "TORSION", "PRESSURE"];

/** The worst verdict wins, the same way every gate in CANVAS aggregates. */
const ORDER: Record<AdditiveVerdict, number> = {
  VIABLE: 0,
  REVIEW: 1,
  INSUFFICIENT_DATA: 2,
  NOT_RECOMMENDED: 3,
};
const worst = (vs: AdditiveVerdict[]): AdditiveVerdict =>
  vs.reduce<AdditiveVerdict>((a, b) => (ORDER[b] > ORDER[a] ? b : a), "VIABLE");

/** The tightest total tolerance band on the part, inches. */
export function tightestBand(features: Feature[]): number | null {
  const bands = features
    .map((f) => (f.tolerance ? f.tolerance.plus + f.tolerance.minus : null))
    .filter((b): b is number => b != null && b > 0);
  return bands.length > 0 ? Math.min(...bands) : null;
}

export function assessAdditive(input: AdditiveInput): AdditiveResult {
  const band = tightestBand(input.features);

  if (input.printers.length === 0) {
    return {
      assessments: [],
      unavailable:
        "No printer is on file for this shop, so there is nothing to judge additive against. CANVAS will not answer from a generic machine — what a printer holds is a property of that printer.",
      tightestBand: band,
    };
  }

  const assessments = input.printers.map((p) => assessOne(p, input, band));
  return { assessments, unavailable: null, tightestBand: band };
}

function assessOne(printer: PrinterRecord, input: AdditiveInput, band: number | null): AdditiveAssessment {
  const findings: AdditiveFinding[] = [];
  const label = `${printer.manufacturer} ${printer.model}`;
  const materials = input.printMaterials.filter((m) => m.technology === printer.technology);

  /* ---- Does it fit on the bed? ---- */
  if (input.envelope === null) {
    findings.push({
      check: "BUILD_VOLUME",
      verdict: "INSUFFICIENT_DATA",
      detail: "The finished envelope is not recorded, so whether the part fits the build volume cannot be answered.",
    });
  } else {
    // Longest part dimension against longest build dimension, and so on: the
    // part can be turned on the bed, so comparing axis to axis in the order
    // they happen to be recorded would reject parts that fit perfectly well.
    const part = [input.envelope.x, input.envelope.y, input.envelope.z].sort((a, b) => b - a);
    const bed = [printer.buildX, printer.buildY, printer.buildZ].sort((a, b) => b - a);
    const fits = part.every((v, i) => v <= bed[i]);
    findings.push({
      check: "BUILD_VOLUME",
      verdict: fits ? "VIABLE" : "NOT_RECOMMENDED",
      detail: fits
        ? `${part.map((v) => v.toFixed(2)).join(" × ")} fits the ${bed.map((v) => v.toFixed(2)).join(" × ")} build volume in some orientation.`
        : `${part.map((v) => v.toFixed(2)).join(" × ")} does not fit the ${bed.map((v) => v.toFixed(2)).join(" × ")} build volume in any orientation. Splitting and bonding is a different part.`,
    });
  }

  /* ---- Can it hold the tolerance? ---- */
  if (band === null) {
    findings.push({
      check: "TOLERANCE",
      verdict: "VIABLE",
      detail: "No feature on this part carries a tolerance, so nothing constrains the process on dimensional accuracy.",
    });
  } else if (printer.achievableTolerance === null) {
    findings.push({
      check: "TOLERANCE",
      verdict: "INSUFFICIENT_DATA",
      detail: `The tightest band on this part is ${band.toFixed(4)}″ and nobody has measured what ${label} actually holds. A manufacturer's figure is a marketing number; print and measure a test coupon before deciding.`,
    });
  } else {
    // Same arithmetic as the inspection gate: the process's own spread against
    // the band it has to sit inside.
    const spread = printer.achievableTolerance * 2;
    const ratio = spread / band;
    findings.push({
      check: "TOLERANCE",
      verdict: ratio <= 0.5 ? "VIABLE" : ratio <= 1 ? "REVIEW" : "NOT_RECOMMENDED",
      detail:
        ratio <= 1
          ? `±${printer.achievableTolerance.toFixed(4)}″ against the tightest band of ${band.toFixed(4)}″ — the process consumes ${(ratio * 100).toFixed(0)}% of it.`
          : `The tightest band on this part is ${band.toFixed(4)}″ and ${label} holds ±${printer.achievableTolerance.toFixed(4)}″ — ${ratio.toFixed(0)}× the band. That feature cannot be printed to size.`,
    });
  }

  /* ---- Is the responsibility profile known at all? ---- */
  const loading = input.intent.loadingType.value ?? [];
  const loadBearing = input.intent.loadBearing.value;
  if (loadBearing === null || loadBearing === undefined) {
    findings.push({
      check: "RESPONSIBILITY",
      verdict: "INSUFFICIENT_DATA",
      detail:
        "Whether this part carries load is not recorded. Additive changes material properties more than any other substitution on this list, and not knowing what a part carries is not the same as it carrying nothing.",
    });
  }

  /* ---- Anisotropy: which way does the load act? ---- */
  const layerLoads = loading.filter((l) => LAYER_SENSITIVE.includes(l));
  if (loadBearing && layerLoads.length > 0) {
    const withBoth = materials.filter((m) => m.tensileXY != null && m.tensileZ != null);
    if (materials.length === 0) {
      findings.push({
        check: "ANISOTROPY",
        verdict: "INSUFFICIENT_DATA",
        detail: `This part is loaded in ${layerLoads.join(", ").toLowerCase()} and no ${TECHNOLOGY_LABEL[printer.technology as PrintTechnology] ?? printer.technology} material is on file, so there is nothing to judge layer strength against.`,
      });
    } else if (withBoth.length === 0) {
      findings.push({
        check: "ANISOTROPY",
        verdict: "INSUFFICIENT_DATA",
        detail: `This part is loaded in ${layerLoads.join(", ").toLowerCase()}. No material on file records strength through the layers as well as within them, and assuming they are equal is the assumption that breaks a printed part.`,
      });
    } else {
      // The best material the shop has for this, by the figure that governs.
      const best = withBoth.reduce((a, b) => (b.tensileZ! > a.tensileZ! ? b : a));
      const retained = best.tensileZ! / best.tensileXY!;
      findings.push({
        check: "ANISOTROPY",
        verdict: retained >= 0.7 ? "REVIEW" : "NOT_RECOMMENDED",
        detail: `This part is loaded in ${layerLoads.join(", ").toLowerCase()}, which acts across the layers. The best material on file for this machine is ${best.name}, which keeps ${(retained * 100).toFixed(0)}% of its strength through Z (${best.tensileZ!.toFixed(0)} psi against ${best.tensileXY!.toFixed(0)} in plane). A printed part is bonded between layers, not continuous through them.`,
      });
    }
  }

  /* ---- Creep: a sustained load in a polymer ---- */
  const polymer = printer.technology !== "METAL_PBF" && printer.technology !== "BINDER_JET";
  const sustained = loadBearing === true && (loading.includes("STATIC") || loading.includes("PRESSURE"));
  if (polymer && sustained && materials.length > 0 && !materials.some((m) => m.creepDataOnFile)) {
    findings.push({
      check: "CREEP",
      verdict: "INSUFFICIENT_DATA",
      detail:
        "This part carries a sustained load and no polymer on file has a recorded creep figure. A tensile number does not answer what a plastic does under load over months, and a press-fit is a creep question.",
    });
  }

  /* ---- Temperature ---- */
  const temp = input.intent.temperatureRange.value;
  if (temp && typeof temp.max === "number" && materials.length > 0) {
    const rated = materials.filter((m) => m.maxServiceTempF != null);
    if (rated.length === 0) {
      findings.push({
        check: "TEMPERATURE",
        verdict: "INSUFFICIENT_DATA",
        detail: `The part sees ${temp.max}°F and no material on file for this machine records a service temperature.`,
      });
    } else {
      const bestTemp = rated.reduce((a, b) => (b.maxServiceTempF! > a.maxServiceTempF! ? b : a));
      findings.push({
        check: "TEMPERATURE",
        verdict: bestTemp.maxServiceTempF! >= temp.max ? "VIABLE" : "NOT_RECOMMENDED",
        detail:
          bestTemp.maxServiceTempF! >= temp.max
            ? `${bestTemp.name} is rated to ${bestTemp.maxServiceTempF}°F against a service maximum of ${temp.max}°F.`
            : `The part sees ${temp.max}°F and the best material on file for this machine is ${bestTemp.name} at ${bestTemp.maxServiceTempF}°F. Above its deflection temperature a polymer is not a structural material.`,
      });
    }
  }

  const verdict = worst(findings.map((f) => f.verdict));

  /*
   * The middle path, and the reason this engine is worth having.
   *
   * A part that fits the bed and fails only on tolerance is not a part that
   * cannot be printed — it is a part that cannot be printed TO SIZE. Printing
   * near-net and finishing the toleranced features on the mill is real, it is
   * already in the advisor's vocabulary as HYBRID, and it is two processes
   * rather than one.
   */
  const toleranceOnly =
    findings.find((f) => f.check === "TOLERANCE")?.verdict === "NOT_RECOMMENDED" &&
    findings.filter((f) => f.check !== "TOLERANCE").every((f) => f.verdict === "VIABLE");

  return {
    printerId: printer.id,
    printerLabel: label,
    technology: printer.technology,
    verdict,
    findings,
    hybridNote: toleranceOnly
      ? "Everything except the tolerance is workable. Printing near-net and finishing the toleranced features on the mill is a real option — that is two processes and two setups, not one."
      : null,
  };
}
