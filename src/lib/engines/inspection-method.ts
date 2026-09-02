import {
  assessCapability,
  measurementGeometry,
  PROCESS_CONTROL_ONLY,
  type CapabilityResult,
  type Instrument,
  type MeasurementGeometry,
} from "./inspection-capability";
import { METROLOGY_LABELS, type MetrologyDeviceType } from "@/lib/domain/shop";
import type { Feature } from "@/lib/domain/features";

/**
 * CHOOSING HOW A FEATURE WILL BE VERIFIED
 *
 * The readiness gate "Critical tolerance strategy" asked the shop to assign an
 * inspection method to every critical feature, and nothing in the application
 * could write one — `Feature.inspectionMethod` had twenty readers and no
 * writer. Any part carrying a critical feature could therefore never post,
 * because the pre-flight requires that gate and no evidence could satisfy it.
 *
 * WHY THIS IS NOT A CONFIRM BUTTON
 *
 * Two gates sit either side of this decision and they answer different
 * questions:
 *
 *   - "Critical tolerance strategy" asks HAVE YOU DECIDED how this will be
 *     checked. That is a human engineering decision and a human makes it.
 *   - "Inspection capability" asks CAN THAT METHOD ACTUALLY DO IT. That is a
 *     property of the instrument and no click changes it —
 *     `clearableByConfirmation` is typed `false`.
 *
 * The decision is only worth anything if it is constrained, so a method may
 * only name an instrument class the shop OWNS and that can physically reach
 * the feature's geometry. A bore gauge cannot be assigned to a rectangular
 * pocket and a CMM the shop does not have cannot be assigned to anything.
 *
 * And the choice has consequences: assigning a coarser instrument than the
 * best one in the drawer makes the capability verdict WORSE, because from then
 * on the capability gate judges the method rather than the drawer. A shop that
 * owns a bore gauge and plans to check the bore with calipers should not pass
 * on the bore gauge it is not going to pick up.
 */

/**
 * Range check, mirroring the one inside `assessCapability`. It is duplicated
 * only to decide what to SHOW; the verdict still comes from the engine, so the
 * two cannot disagree about whether a feature can be measured — at worst this
 * lists an instrument the engine ignored, never the reverse.
 */
const inRangeFor = (d: Instrument, nominal: number | null): boolean => {
  if (nominal == null) return true;
  if (d.rangeMin != null && nominal < d.rangeMin) return false;
  if (d.rangeMax != null && nominal > d.rangeMax) return false;
  return true;
};

export interface MethodOption {
  deviceType: string;
  label: string;
  /** The shop's own instruments of this class that can reach the feature. */
  instruments: Instrument[];
  /** Verdict this feature would get if this method were assigned. */
  verdict: CapabilityResult["verdict"];
  /** Fraction of the tolerance band the best of them consumes, when known. */
  consumedFraction: number | null;
  /** The engine's sentence about this method, so the choice is informed. */
  reason: string;
}

/**
 * Every method the shop could honestly assign to this feature, each carrying
 * the verdict it would produce.
 *
 * The verdicts are computed by `assessCapability` rather than by comparing
 * uncertainties here. There is one capability rule in this codebase and this
 * is not a second copy of it — a picker that ranked instruments its own way
 * would eventually disagree with the gate that blocks NC export.
 */
export function methodOptions(feature: Feature, instruments: Instrument[]): MethodOption[] {
  const geometry = measurementGeometry(feature);
  const request = {
    featureId: feature.id,
    featureLabel: feature.label,
    geometry,
    nominal: "diameter" in feature ? (feature.diameter as number | null) : null,
    toleranceBand: feature.tolerance ? feature.tolerance.plus + feature.tolerance.minus : null,
    critical: feature.critical,
  };

  const byType = new Map<string, Instrument[]>();
  for (const d of instruments) byType.set(d.deviceType, [...(byType.get(d.deviceType) ?? []), d]);

  const options: MethodOption[] = [];
  for (const [deviceType, list] of byType) {
    // A spindle probe measures the part on the machine that cut it, so it is
    // never the method that accepts a feature. `assessCapability` already
    // refuses it — but only once there is a tolerance to judge, and it returns
    // NOT_REQUIRED before that for an untoleranced feature. Without this the
    // probe was offered as a method for exactly those features, which is the
    // rule leaking through the one door it does not cover.
    if (PROCESS_CONTROL_ONLY.has(deviceType)) continue;
    const result = assessCapability({ ...request, chosenDeviceType: deviceType }, list);
    // NO_INSTRUMENT here means this class cannot reach the geometry or the
    // size, so it is not a choice the shop can make — it is left out rather
    // than offered with a warning nobody can act on.
    if (result.verdict === "NO_INSTRUMENT") continue;
    // Only the units that can actually be used on this feature. Listing the
    // whole class named a 1" air gauge under a method for a 1.5748" bore —
    // an instrument the verdict had already excluded on range, sitting in the
    // UI as though it were one of the two the shop would reach for.
    const usableHere = list.filter((d) => inRangeFor(d, request.nominal));
    options.push({
      deviceType,
      label: METROLOGY_LABELS[deviceType as MetrologyDeviceType] ?? deviceType.replace(/_/g, " ").toLowerCase(),
      instruments: usableHere.length > 0 ? usableHere : list,
      verdict: result.verdict,
      consumedFraction: result.consumedFraction,
      reason: result.reason,
    });
  }

  // Best first, by what the measurement would actually be worth. Ties keep a
  // stable alphabetical order so the list does not shuffle between loads.
  const rank: Record<string, number> = { CAPABLE: 0, MARGINAL: 1, NOT_CAPABLE: 2, NOT_REQUIRED: 3, NO_INSTRUMENT: 4 };
  return options.sort(
    (a, b) =>
      (rank[a.verdict] ?? 9) - (rank[b.verdict] ?? 9) ||
      (a.consumedFraction ?? 9) - (b.consumedFraction ?? 9) ||
      a.label.localeCompare(b.label),
  );
}

export type MethodRefusal = { ok: false; reason: string };
export type MethodAccepted = { ok: true; deviceType: string; method: string; verdict: CapabilityResult["verdict"] };

/**
 * Whether this shop may assign this method to this feature, and the sentence
 * to store if so.
 *
 * Refusals name what is wrong rather than returning a bare false: a picker
 * that silently rejects a choice teaches the machinist nothing, and this is
 * the one place that can explain why a bore gauge is not an option for a
 * rectangular pocket.
 */
export function validateMethod(
  feature: Feature,
  instruments: Instrument[],
  deviceType: string,
): MethodAccepted | MethodRefusal {
  const label = METROLOGY_LABELS[deviceType as MetrologyDeviceType];
  if (!label) return { ok: false, reason: `${deviceType} is not an instrument class CANVAS recognises.` };

  const owned = instruments.filter((d) => d.deviceType === deviceType);
  if (owned.length === 0) {
    return {
      ok: false,
      reason: `The metrology list records no ${label.toLowerCase()}. A method has to name an instrument the shop can actually pick up; add it on the metrology page first.`,
    };
  }

  const option = methodOptions(feature, instruments).find((o) => o.deviceType === deviceType);
  if (!option) {
    return {
      ok: false,
      reason: `A ${label.toLowerCase()} cannot reach a ${measurementGeometry(feature).replace(/_/g, " ").toLowerCase()} feature of this size, so it cannot be the method for ${feature.label}.`,
    };
  }

  // A method that is MARGINAL or NOT_CAPABLE is still a decision the shop is
  // entitled to record — guard-banding a marginal reading is ordinary practice.
  // It is not hidden either: the capability gate now judges this choice, so
  // recording a poor method makes the part read worse, not better.
  return { ok: true, deviceType, method: methodSentence(label, option), verdict: option.verdict };
}

/**
 * The sentence stored on the feature and printed on the first-article report.
 *
 * It carries the instrument class and what it consumes of the band, because
 * "Micrometer" on an inspection report tells the next reader nothing about
 * whether the micrometer was up to the job.
 */
export function methodSentence(label: string, option: MethodOption): string {
  return option.consumedFraction != null
    ? `${label} — consumes ${(option.consumedFraction * 100).toFixed(0)}% of the tolerance band`
    : label;
}

/** Geometry in a sentence, for the refusal text and the picker's empty state. */
export function geometryPhrase(g: MeasurementGeometry): string {
  return g === "INTERNAL_ROUND"
    ? "round internal"
    : g === "INTERNAL_FLAT"
      ? "flat internal"
      : g === "EXTERNAL"
        ? "external"
        : "position";
}
