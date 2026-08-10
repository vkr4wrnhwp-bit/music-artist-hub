import type { Feature } from "@/lib/domain/features";
import type { MeasurementInfo } from "./panel-data";

/**
 * THE TWO NUMBER SYSTEMS
 *
 * A feature carries a dimension from the model. A measurement carries a
 * reading from an instrument. On the demo part those are 1.5748" and 1.5744",
 * and they are not the same kind of fact — one is what the plan will cut, the
 * other is what somebody measured on a worn original that nobody has yet
 * decided about.
 *
 * Everything in this module exists to keep them apart. There is no function
 * here that returns "the" value of a feature, because there isn't one.
 */

export interface PrimaryDimension {
  /** What this dimension is called on a drawing. */
  name: string;
  /** ⌀ or R, when the dimension carries one. */
  prefix: string;
  value: number;
}

/** The dimension a machinist would read first. Null when the kind has none. */
export function primaryDimension(f: Feature): PrimaryDimension | null {
  if ("diameter" in f && typeof f.diameter === "number") {
    return { name: "Diameter", prefix: "⌀", value: f.diameter };
  }
  if (f.kind === "FACE") return { name: "Face depth", prefix: "", value: f.depth };
  if (f.kind === "FILLET") return { name: "Radius", prefix: "R", value: f.radius };
  if (f.kind === "CHAMFER") return { name: "Chamfer width", prefix: "", value: f.width };
  if ("width" in f && typeof f.width === "number") return { name: "Width", prefix: "", value: f.width };
  return null;
}

export type BandVerdict = "INSIDE" | "OUTSIDE" | "UNKNOWN";

export interface Comparison {
  /** measured − model. */
  deviation: number;
  /** Whether the reading falls inside the stated tolerance band. */
  band: BandVerdict;
  lower: number | null;
  upper: number | null;
}

/**
 * Arithmetic, and nothing more.
 *
 * This is NOT an inspection result. `InspectionResult.pass` has no write path
 * in CANVAS, the seeded reading is unresolved, and whether a measured value is
 * acceptable is a decision a human makes with the measurement uncertainty in
 * front of them. Every caller must label what this returns as computed.
 */
export function compare(feature: Feature, measured: number): Comparison | null {
  const model = primaryDimension(feature);
  if (!model) return null;
  const deviation = Number((measured - model.value).toFixed(6));
  if (!feature.tolerance) {
    return { deviation, band: "UNKNOWN", lower: null, upper: null };
  }
  const lower = model.value - feature.tolerance.minus;
  const upper = model.value + feature.tolerance.plus;
  return {
    deviation,
    band: measured >= lower && measured <= upper ? "INSIDE" : "OUTSIDE",
    lower,
    upper,
  };
}

export const RESOLUTION_LABEL: Record<string, string> = {
  PENDING: "Unresolved",
  ACCEPTED_NOMINAL: "Nominal accepted",
  KEPT_MEASURED: "Measured value kept",
  INVESTIGATING: "Under investigation",
};

/**
 * The colour a resolution state is entitled to.
 *
 * Orange means review / outstanding in this system. KEPT_MEASURED and
 * ACCEPTED_NOMINAL are decided — a human resolved them — so painting them the
 * same orange as PENDING tells an inspector a settled reading is still open.
 * Only PENDING and INVESTIGATING are outstanding.
 */
export const RESOLUTION_TONE: Record<string, "review" | "neutral"> = {
  PENDING: "review",
  INVESTIGATING: "review",
  ACCEPTED_NOMINAL: "neutral",
  KEPT_MEASURED: "neutral",
};

export const RESOLUTION_DETAIL: Record<string, string> = {
  PENDING: "Nobody has decided yet whether this reading is the nominal or a worn dimension.",
  ACCEPTED_NOMINAL: "A human accepted a standard nominal in place of this reading.",
  KEPT_MEASURED: "A human kept the measured value as the dimension.",
  INVESTIGATING: "Flagged for investigation. The reading is not being used as geometry.",
};

/** The most recent reading, which is the one worth showing large. */
export function latestMeasurement(measurements: MeasurementInfo[]): MeasurementInfo | null {
  return measurements[0] ?? null;
}
