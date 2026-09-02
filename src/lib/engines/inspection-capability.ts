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
import { METROLOGY_LABELS, type MetrologyDeviceType } from "@/lib/domain/shop";

/**
 * A device type in a sentence. Falls back to the raw token rather than an
 * empty string, so an instrument class this vocabulary has not caught up with
 * reads as unfamiliar rather than as nothing at all.
 */
const METHOD_LABEL = (deviceType: string): string =>
  METROLOGY_LABELS[deviceType as MetrologyDeviceType] ?? deviceType.replace(/_/g, " ").toLowerCase();

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
/**
 * The gauge-maker's rule, both ends, exported because they are the ONE
 * home of the ratio — the turning side judges capability with these same
 * numbers rather than keeping its own copy. Uncertainty consuming ≤10% of
 * the band is the target; past 25% the reading is largely its own noise.
 */
export const TARGET_RATIO = 0.1;
export const LIMIT_RATIO = 0.25;

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
/**
 * Round internal features only. A bore gauge, a pin gauge and a telescoping
 * gauge physically require a round hole — recommending a dial bore gauge for
 * a rectangular relief pocket is the kind of wrong that erodes trust in every
 * other recommendation on the screen.
 */
export const MEASURES_INTERNAL_ROUND = new Set([
  "BORE_GAUGE",
  "INSIDE_MICROMETER",
  "TELESCOPING_GAUGE",
  "PIN_GAUGE",
  "CMM",
  "MACHINE_PROBE",
  "DIGITAL_CALIPER",
]);

/** Flat internal features — pockets and slots. Widths, lengths and depths. */
export const MEASURES_INTERNAL_FLAT = new Set([
  "DIGITAL_CALIPER",
  "DEPTH_MICROMETER",
  "INSIDE_MICROMETER",
  "CMM",
  "MACHINE_PROBE",
  "HEIGHT_GAUGE",
  "OPTICAL_COMPARATOR",
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
 * Instruments that can reach the geometry but cannot ACCEPT the feature.
 *
 * A spindle-mounted probe measuring the part in the fixture that just cut it
 * is not an independent measurement. It shares the machine's own geometric
 * errors — the same scale and lead-screw error, the same squareness, the same
 * thermal growth, the same fixture and the same work offset. If the machine
 * cut the bore 0.0008" off position because the X axis is off, the probe
 * reports it in position, because it is measuring with the same ruler that
 * made the mistake. Its stated uncertainty is real for repeatability and says
 * nothing about that shared bias.
 *
 * This is not a reason to own less probing. A probe is the best process-control
 * instrument on the floor: finding a datum, correcting a work offset, catching
 * a broken tool, trending size across a run, deciding whether to take another
 * pass while the part is still clamped. Every one of those is worth having and
 * none of them is acceptance.
 *
 * So a probe is excluded from the instrument that clears the inspection gate,
 * and the reason is stated rather than the probe being silently ignored — a
 * shop that just bought one is entitled to know why CANVAS is not counting it.
 */
export const PROCESS_CONTROL_ONLY = new Set(["MACHINE_PROBE"]);

/** What the probe IS for, said in the same breath as declining it. */
const PROBE_ROLE =
  "in-process control — establishing the datum, correcting the work offset, catching a broken tool and trending size across the run";

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
  INTERNAL_ROUND: [
    { text: "Telescoping gauge read with a micrometer", deviceType: "TELESCOPING_GAUGE", achievable: 0.0003 },
    { text: "Dial or digital bore gauge set to a ring or micrometer standard", deviceType: "BORE_GAUGE", achievable: 0.0002 },
    { text: "Air gauge, or a CMM for production volumes", deviceType: "CMM", achievable: 0.00005 },
  ],
  INTERNAL_FLAT: [
    { text: "Depth micrometer for the floor, inside micrometer for the walls", deviceType: "DEPTH_MICROMETER", achievable: 0.0002 },
    { text: "CMM for the full pocket form", deviceType: "CMM", achievable: 0.00005 },
  ],
  EXTERNAL: [
    { text: "Outside micrometer in the right size range", deviceType: "MICROMETER", achievable: 0.0002 },
    { text: "Bench micrometer or optical comparator", deviceType: "OPTICAL_COMPARATOR", achievable: 0.0001 },
    { text: "CMM", deviceType: "CMM", achievable: 0.00005 },
  ],
  POSITION: [
    { text: "Height gauge on a surface plate with the part on datum", deviceType: "HEIGHT_GAUGE", achievable: 0.001 },
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

export type MeasurementGeometry = "INTERNAL_ROUND" | "INTERNAL_FLAT" | "EXTERNAL" | "POSITION";

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
      return f.functionalRole === "DOWEL_HOLE" || f.functionalRole === "MOUNTING_HOLE" ? "POSITION" : "INTERNAL_ROUND";
    case "RECT_POCKET":
    case "SLOT":
      // A pocket is measured for width, length and depth — a bore gauge has
      // nothing round to register against.
      return "INTERNAL_FLAT";
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
  /**
   * The instrument class the shop has DECIDED to verify this feature with,
   * when one has been assigned.
   *
   * Without it this gate answers "could the shop measure this with the best
   * thing it owns", which is not the question once a method exists. A shop
   * that owns a bore gauge and plans to check the bore with calipers would
   * otherwise pass on the bore gauge it is not going to pick up — the drawer
   * would be clearing a gate the plan does not.
   *
   * So when a method is assigned, the pool narrows to it and the verdict is
   * about the method. Choosing a worse instrument makes the verdict worse,
   * which is the correct and uncomfortable answer.
   */
  chosenDeviceType?: string | null;
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
    geometry === "INTERNAL_ROUND"
      ? MEASURES_INTERNAL_ROUND
      : geometry === "INTERNAL_FLAT"
        ? MEASURES_INTERNAL_FLAT
        : geometry === "EXTERNAL"
          ? MEASURES_EXTERNAL
          : MEASURES_POSITION;
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

  const reachable = instruments
    .filter((d) => canReachGeometry(d, request.geometry))
    .filter((d) => inRange(d, request.nominal))
    // Once a method is chosen, the verdict is about the method. See
    // `chosenDeviceType` — the drawer must not clear a gate the plan does not.
    .filter((d) => !request.chosenDeviceType || d.deviceType === request.chosenDeviceType);

  // An on-machine probe can reach the geometry and still cannot accept the
  // feature. Split it out here rather than letting it win on uncertainty.
  const processControl = reachable.filter((d) => PROCESS_CONTROL_ONLY.has(d.deviceType));
  const usable = reachable.filter((d) => !PROCESS_CONTROL_ONLY.has(d.deviceType));

  if (usable.length === 0) {
    // Owning a probe and nothing else is a different situation from owning
    // nothing, and a shop that just bought one will read "no instrument" as a
    // bug unless the sentence says why it is not being counted.
    const probeOwned = processControl[0] ?? null;
    return {
      ...base,
      verdict: "NO_INSTRUMENT",
      bestInstrument: null,
      consumedFraction: null,
      requiredUncertainty,
      reason: probeOwned
        ? `${probeOwned.description} can reach this feature, but it measures the part in the fixture that cut it, using the machine's own scales — it cannot detect an error the machine itself made, so it is not acceptance evidence. Nothing else on the metrology list can measure this feature.`
        : request.chosenDeviceType
          ? `This feature is assigned to be verified with ${METHOD_LABEL(request.chosenDeviceType)}, and the shop has no such instrument that can reach a ${request.geometry.toLowerCase()} dimension${request.nominal != null ? ` at ⌀${request.nominal.toFixed(4)}` : ""}. The assigned method is the one judged here, not the best instrument in the drawer.`
          : request.nominal != null
            ? `No instrument on the metrology list can measure a ${request.geometry.toLowerCase()} dimension at ⌀${request.nominal.toFixed(4)}.`
            : `No instrument on the metrology list can measure a ${request.geometry.toLowerCase()} dimension.`,
      recommendations: [
        ...(probeOwned ? [`Keep the probe for ${PROBE_ROLE}; accept the feature off the machine`] : []),
        ...upgradesFor(request.geometry, instruments, requiredUncertainty),
      ],
    };
  }

  /*
   * A shop whose probe is finer than anything in the drawer will ask why the
   * feature still reads MARGINAL. Answered where the question arises, and only
   * there: on a CAPABLE result nobody is looking for the missing instrument,
   * and the note would just be noise on a passing check.
   */
  const finerProbe = processControl.find((d) => d.calibrated && d.uncertainty < request.toleranceBand! * TARGET_RATIO);
  const probeNote = finerProbe
    ? [
        `${finerProbe.description} is finer than this, and is deliberately not counted: it measures the part on the machine that cut it, so it cannot see an error the machine made. Use it for ${PROBE_ROLE}.`,
      ]
    : [];

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
      recommendations: [
        "Calibrate the instrument and record the certificate",
        ...probeNote,
        ...upgradesFor(request.geometry, instruments, requiredUncertainty),
      ],
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
        ...probeNote,
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
      ...probeNote,
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
