/**
 * INSPECTION CAPABILITY
 *
 * A tolerance you cannot measure is not a tolerance. It is a hope.
 *
 * This is the gate that most obviously cannot be cleared by a human clicking
 * Confirm, and it is the clearest illustration of the principle behind all of
 * them: the gate is not asking whether you believe the bore is right, it is
 * asking whether the shop owns an instrument that can tell. Clicking does not
 * change what is in the drawer. Only buying, borrowing or outsourcing does.
 *
 * The rule is the gauge maker's rule, which is not a CANVAS invention: the
 * measurement system's uncertainty should consume no more than 10% of the
 * tolerance band, and 25% is the outer limit at which a measurement is still
 * considered to be discriminating rather than guessing. Below that a
 * "measurement" is mostly reporting the noise in the instrument.
 *
 * See ASME B89.7.3.1 for the decision-rule framing this follows.
 */

import type { Feature } from "@/lib/domain/features";

export const CAPABILITY_VERDICTS = ["CAPABLE", "MARGINAL", "NOT_CAPABLE", "NO_INSTRUMENT", "NOT_REQUIRED"] as const;
export type CapabilityVerdict = (typeof CAPABILITY_VERDICTS)[number];

export const CAPABILITY_LABEL: Record<CapabilityVerdict, string> = {
  CAPABLE: "Capable",
  MARGINAL: "Marginal",
  NOT_CAPABLE: "Not capable",
  NO_INSTRUMENT: "No instrument",
  NOT_REQUIRED: "No tolerance",
};

/** Fraction of the tolerance band the instrument may consume. */
const TARGET_RATIO = 0.1;
const LIMIT_RATIO = 0.25;

export interface Instrument {
  id: string;
  deviceType: string;
  description: string;
  resolution: number;
  /** Expanded measurement uncertainty, inches. */
  uncertainty: number;
  rangeMin: number | null;
  rangeMax: number | null;
  calibrated: boolean;
}

/** What kind of geometry an instrument can actually reach. */
export const MEASURES_INTERNAL = new Set([
  "BORE_GAUGE",
  "INSIDE_MICROMETER",
  "TELESCOPING_GAUGE",
  "PIN_GAUGE",
  "CMM",
  "MACHINE_PROBE",
  "DIGITAL_CALIPER",
]);

export const MEASURES_EXTERNAL = new Set([
  "MICROMETER",
  "DIGITAL_CALIPER",
  "CMM",
  "MACHINE_PROBE",
  "HEIGHT_GAUGE",
  "OPTICAL_COMPARATOR",
]);

export const MEASURES_POSITION = new Set(["CMM", "HEIGHT_GAUGE", "MACHINE_PROBE", "SURFACE_PLATE", "DIAL_INDICATOR"]);

/**
 * Instruments a caliper-only shop should be pointed at, in ascending order of
 * cost. Concrete recommendations only — never "use a better instrument".
 */
interface Upgrade {
  text: string;
  /** Device type this suggestion amounts to buying. */
  deviceType: string;
  /** Uncertainty this class of instrument realistically achieves, inches. */
  achievable: number;
}

const UPGRADE_PATH: Record<string, Upgrade[]> = {
  INTERNAL: [
    { text: "Telescoping gauge read with a micrometer", deviceType: "TELESCOPING_GAUGE", achievable: 0.0003 },
    { text: "Dial or digital bore gauge set to a ring or micrometer standard", deviceType: "BORE_GAUGE", achievable: 0.0002 },
    { text: "Air gauge, or a CMM for production volumes", deviceType: "CMM", achievable: 0.00005 },
  ],
  EXTERNAL: [
    { text: "Outside micrometer in the right size range", deviceType: "MICROMETER", achievable: 0.0002 },
    { text: "Bench micrometer or optical comparator", deviceType: "OPTICAL_COMPARATOR", achievable: 0.0001 },
    { text: "CMM", deviceType: "CMM", achievable: 0.00005 },
  ],
  POSITION: [
    { text: "Height gauge on a surface plate with the part on datum", deviceType: "HEIGHT_GAUGE", achievable: 0.001 },
    { text: "Machine probe, if the datum can be established in the fixture", deviceType: "MACHINE_PROBE", achievable: 0.0005 },
    { text: "CMM for a true position callout", deviceType: "CMM", achievable: 0.00005 },
  ],
};

/**
 * Suggest only equipment that would actually change the answer.
 *
 * Telling a shop to buy a bore gauge when there is one on the bench is how
 * software gets ignored. A suggestion survives only if the shop does not
 * already own that class of instrument, and if owning it would bring the
 * measurement inside the target.
 */
function upgradesFor(
  geometry: MeasurementGeometry,
  owned: Instrument[],
  requiredUncertainty: number,
): string[] {
  const ownedTypes = new Set(owned.map((d) => d.deviceType));
  return UPGRADE_PATH[geometry]
    .filter((u) => !ownedTypes.has(u.deviceType))
    .filter((u) => u.achievable <= requiredUncertainty)
    .map((u) => u.text);
}

export type MeasurementGeometry = "INTERNAL" | "EXTERNAL" | "POSITION";

/**
 * Which family of instrument a feature needs. A bore and a boss of the same
 * size are not measured with the same tool, and a position is not measured with
 * either of them.
 *
 * THIS IS THE ONLY CLASSIFIER. It lives beside `assessCapability` because the
 * geometry class and the instrument list together decide the verdict, and a
 * second copy of either produces a screen that contradicts the gate that blocks
 * NC export. Every caller — the readiness gate, the part workspace and the
 * feature detail page — routes through here.
 */
export function measurementGeometry(f: Feature): MeasurementGeometry {
  switch (f.kind) {
    case "DRILLED_HOLE":
    case "TAPPED_HOLE":
    case "BORE":
    case "CIRC_POCKET":
    case "RECT_POCKET":
    case "SLOT":
      return f.functionalRole === "DOWEL_HOLE" || f.functionalRole === "MOUNTING_HOLE" ? "POSITION" : "INTERNAL";
    default:
      return "EXTERNAL";
  }
}

export interface CapabilityRequest {
  featureId: string;
  featureLabel: string;
  geometry: MeasurementGeometry;
  /** Nominal size, used to check the instrument's range. */
  nominal: number | null;
  /** Total tolerance band, inches. Null when the feature carries no tolerance. */
  toleranceBand: number | null;
  critical: boolean;
}

export interface CapabilityResult {
  featureId: string;
  featureLabel: string;
  verdict: CapabilityVerdict;
  toleranceBand: number | null;
  /** The best instrument the shop owns for this measurement. */
  bestInstrument: Instrument | null;
  /** Fraction of the tolerance band that instrument consumes. */
  consumedFraction: number | null;
  /** Uncertainty an instrument would need to reach the 10:1 target. */
  requiredUncertainty: number | null;
  reason: string;
  recommendations: string[];
  /**
   * Always false. Inspection capability is a property of the instruments the
   * shop owns, and no amount of user acknowledgement changes it.
   */
  clearableByConfirmation: false;
}

function canReachGeometry(device: Instrument, geometry: MeasurementGeometry): boolean {
  const set =
    geometry === "INTERNAL" ? MEASURES_INTERNAL : geometry === "EXTERNAL" ? MEASURES_EXTERNAL : MEASURES_POSITION;
  return set.has(device.deviceType);
}

function inRange(device: Instrument, nominal: number | null): boolean {
  if (nominal == null) return true;
  if (device.rangeMin != null && nominal < device.rangeMin) return false;
  if (device.rangeMax != null && nominal > device.rangeMax) return false;
  return true;
}

export function assessCapability(request: CapabilityRequest, instruments: Instrument[]): CapabilityResult {
  const base = {
    featureId: request.featureId,
    featureLabel: request.featureLabel,
    toleranceBand: request.toleranceBand,
    clearableByConfirmation: false as const,
  };

  if (request.toleranceBand == null || request.toleranceBand <= 0) {
    return {
      ...base,
      verdict: "NOT_REQUIRED",
      bestInstrument: null,
      consumedFraction: null,
      requiredUncertainty: null,
      reason: "No tolerance is specified on this feature, so no measurement capability is required to accept it.",
      recommendations: [],
    };
  }

  const requiredUncertainty = Number((request.toleranceBand * TARGET_RATIO).toFixed(5));

  const usable = instruments
    .filter((d) => canReachGeometry(d, request.geometry))
    .filter((d) => inRange(d, request.nominal));

  if (usable.length === 0) {
    return {
      ...base,
      verdict: "NO_INSTRUMENT",
      bestInstrument: null,
      consumedFraction: null,
      requiredUncertainty,
      reason:
        request.nominal != null
          ? `No instrument on the metrology list can measure a ${request.geometry.toLowerCase()} dimension at ⌀${request.nominal.toFixed(4)}.`
          : `No instrument on the metrology list can measure a ${request.geometry.toLowerCase()} dimension.`,
      recommendations: upgradesFor(request.geometry, instruments, requiredUncertainty),
    };
  }

  // Best is the lowest uncertainty; calibration is a hard filter rather than a
  // tiebreak, because an uncalibrated instrument has no defensible uncertainty
  // at all — but an uncalibrated instrument is still reported, with the reason.
  const calibrated = usable.filter((d) => d.calibrated);
  const pool = calibrated.length > 0 ? calibrated : usable;
  const best = pool.reduce((a, b) => (a.uncertainty <= b.uncertainty ? a : b));

  const consumed = Number((best.uncertainty / request.toleranceBand).toFixed(3));

  if (calibrated.length === 0) {
    return {
      ...base,
      verdict: "NOT_CAPABLE",
      bestInstrument: best,
      consumedFraction: consumed,
      requiredUncertainty,
      reason: `${best.description} is not recorded as calibrated. An uncalibrated instrument has no traceable uncertainty, so it cannot provide evidence for a toleranced dimension.`,
      recommendations: ["Calibrate the instrument and record the certificate", ...upgradesFor(request.geometry, instruments, requiredUncertainty)],
    };
  }

  const band = request.toleranceBand;

  if (consumed <= TARGET_RATIO) {
    return {
      ...base,
      verdict: "CAPABLE",
      bestInstrument: best,
      consumedFraction: consumed,
      requiredUncertainty,
      reason: `${best.description} at ±${best.uncertainty.toFixed(4)}" consumes ${(consumed * 100).toFixed(0)}% of the ${band.toFixed(4)}" band, inside the 10% target.`,
      recommendations: [],
    };
  }

  if (consumed <= LIMIT_RATIO) {
    return {
      ...base,
      verdict: "MARGINAL",
      bestInstrument: best,
      consumedFraction: consumed,
      requiredUncertainty,
      reason: `${best.description} at ±${best.uncertainty.toFixed(4)}" consumes ${(consumed * 100).toFixed(0)}% of the ${band.toFixed(4)}" band. Above 10% the measurement starts rejecting good parts and accepting bad ones; below 25% it is still discriminating.`,
      recommendations: [
        `Guard-band the accept limits by ±${best.uncertainty.toFixed(4)}" to keep the risk on the shop's side`,
        ...upgradesFor(request.geometry, instruments, requiredUncertainty),
      ],
    };
  }

  return {
    ...base,
    verdict: "NOT_CAPABLE",
    bestInstrument: best,
    consumedFraction: consumed,
    requiredUncertainty,
    reason: `The best available instrument is ${best.description} at ±${best.uncertainty.toFixed(4)}", which consumes ${(consumed * 100).toFixed(0)}% of the ${band.toFixed(4)}" tolerance band. This method cannot provide sufficient evidence to verify the requested tolerance — what it reports is largely its own noise.`,
    recommendations: [
      `An instrument with uncertainty at or below ±${requiredUncertainty.toFixed(5)}" is required — the best on hand is ±${best.uncertainty.toFixed(4)}"`,
      ...upgradesFor(request.geometry, instruments, requiredUncertainty),
      "Outsource the inspection of this dimension to a calibration house or a shop with a CMM",
    ],
  };
}

/**
 * Worst verdict across a set — aggregation is always by worst case, never by
 * proportion. Nine capable measurements do not average away a tenth that
 * cannot be made at all.
 */
const ORDER: Record<CapabilityVerdict, number> = {
  NOT_REQUIRED: 0,
  CAPABLE: 1,
  MARGINAL: 2,
  NOT_CAPABLE: 3,
  NO_INSTRUMENT: 4,
};

export function worstCapability(results: CapabilityResult[]): CapabilityVerdict {
  return results.reduce<CapabilityVerdict>(
    (acc, r) => (ORDER[r.verdict] > ORDER[acc] ? r.verdict : acc),
    "NOT_REQUIRED",
  );
}
