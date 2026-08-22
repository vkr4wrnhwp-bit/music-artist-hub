import type { RotationalProfile } from "./geometry";

/**
 * TURNING PACKAGE — the pure derivations.
 *
 * These used to live inline in `package.ts`, which imports the database and
 * so cannot be tested. They are the small pieces of arithmetic that decide
 * whether a gate blocks, which makes them exactly the pieces that need to be
 * testable. Nothing here reads or writes anything: profile and recorded
 * numbers in, a value or null out.
 */

/**
 * Distance from the jaw face to the cutoff plane.
 *
 * Convention (geometry.ts): Z0 is the machining datum face, the part runs to
 * +Z, and the chuck grips the far end of the bar. So the jaw face sits at
 * `stockLength - gripLength` and the free length in front of it is the
 * stickout.
 *
 * The old expression was
 *
 *   cutoffZ - gripLength + stickout - (stockLength - gripLength)
 *
 * in which the two gripLength terms cancel, leaving `cutoffZ + stickout -
 * stockLength` — i.e. `cutoffZ - gripLength` for a consistently recorded
 * setup. That is measured from the wrong end and grows the wrong way: the
 * cutoff FURTHEST from the jaws, which is the one that whips and pinches the
 * blade at separation, came out smallest, and for a short part parted near
 * the datum face it came out NEGATIVE — a guaranteed PASS on the least
 * stable cutoff there is.
 *
 * Returns null when the stickout has not been recorded. A part-off overhang
 * computed from an assumed zero is a confident number about a setup nobody
 * measured.
 */
export function cutoffDistanceFromChuck(input: {
  cutoffZ: number;
  stickout: number | null;
}): number | null {
  if (input.stickout == null || !Number.isFinite(input.stickout) || input.stickout < 0) return null;
  if (!Number.isFinite(input.cutoffZ)) return null;
  // The cutoff cannot be behind the jaws; a plan that says so is reported as
  // zero overhang rather than as a negative one.
  return Math.max(0, input.stickout - input.cutoffZ);
}

/**
 * The tightest total tolerance band among the critical segments, inches.
 *
 * Null means no critical segment carries a tolerance — nothing to verify,
 * which is not the same as verified. A segment recording only a plus or only
 * a minus still carries a band; the old filter demanded `toleranceMinus`
 * and silently dropped a plus-only critical dimension out of the inspection
 * check entirely.
 */
export function criticalToleranceBand(profile: RotationalProfile): number | null {
  const bands = profile.segments
    .filter((s) => s.critical && (s.tolerancePlus != null || s.toleranceMinus != null))
    .map((s) => (s.tolerancePlus ?? 0) + (s.toleranceMinus ?? 0))
    .filter((b) => b > 0);
  return bands.length === 0 ? null : Math.min(...bands);
}

/**
 * Instruments that can measure a turned DIAMETER at all.
 *
 * INSIDE_MICROMETER is on this list because it measures a bore, and a turned
 * part's critical band is as often in a bore as on a journal. It was missing,
 * so a shop whose only bore instrument was an inside micrometer read as
 * owning nothing that could prove the tolerance.
 *
 * Left off deliberately: DEPTH_MICROMETER and HEIGHT_GAUGE measure axially,
 * SURFACE_PLATE is a reference surface, and PIN_GAUGE and
 * OPTICAL_COMPARATOR need a rule about go/no-go and profile measurement
 * that nobody has written yet. An instrument is added here when somebody
 * decides it belongs, not because its uncertainty number looks small.
 */
const MEASURING_DEVICE_TYPES = ["MICROMETER", "INSIDE_MICROMETER", "BORE_GAUGE", "CMM"] as const;

/**
 * Can the shop's instruments prove the tightest critical band?
 *
 * A profile with no critical tolerance band has nothing for this gate to
 * refuse, and returns true: the gate is not a standing block that no
 * evidence could ever clear. False means the instruments on file cannot
 * prove the band, including the case of owning none.
 *
 * NOTE — the ratio here is 4:1, the gauge-maker's rule taken at its limit.
 * `engines/inspection-capability.ts` targets 10:1 and treats 4:1 as the
 * floor, so the same band can read capable turned and marginal milled. That
 * difference is deliberate until somebody decides which one the shop runs
 * to; it is not an oversight to be quietly averaged away.
 */
export const TURN_INSPECTION_RATIO = 4;

export function inspectionCapableFor(
  band: number | null,
  instruments: { deviceType: string; uncertainty: number }[],
): boolean {
  if (band === null) return true;
  const usable = instruments
    .filter((m) => (MEASURING_DEVICE_TYPES as readonly string[]).includes(m.deviceType))
    .filter((m) => Number.isFinite(m.uncertainty) && m.uncertainty > 0)
    .sort((a, b) => a.uncertainty - b.uncertainty);
  if (usable.length === 0) return false;
  return usable[0].uncertainty * TURN_INSPECTION_RATIO <= band;
}

/**
 * The material the part's own intent records, or null. A turned part whose
 * material gate was handed a literal `true` could not fail a PASS/FAIL gate.
 */
export function materialFromIntent(intentJson: string | null | undefined): string | null {
  try {
    const intent = JSON.parse(intentJson ?? "{}") as { material?: { value?: unknown } };
    const v = intent.material?.value;
    return typeof v === "string" && v.trim() !== "" ? v.trim() : null;
  } catch {
    return null;
  }
}
