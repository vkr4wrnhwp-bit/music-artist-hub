import type { Feature } from "@/lib/domain/features";
import type { FeatureDetail, RunwayOperation } from "./panel-data";

/**
 * THE FOUR THINGS WORTH KNOWING ABOUT A FEATURE.
 *
 * DETAIL, MEASURE, MAKE, VERIFY. Three of them existed on the click-through
 * panel and none of them on the lens, and MAKE existed nowhere at all — a
 * machinist who selected a bore could not get from it to the operation that
 * cuts it, the tool, or whether anything cuts it, without reading the runway
 * table at the bottom of the screen and matching labels by eye.
 *
 * Every rule here reads data the workspace already holds. Nothing is
 * inferred, and an absence is stated as an absence: "no operation in the plan
 * cuts this feature" is a fact worth knowing before Cycle Start, not an error.
 */

export type ActionAvailability = { available: true; detail: string } | { available: false; reason: string };

export interface FeatureActions {
  detail: ActionAvailability;
  measure: ActionAvailability;
  make: ActionAvailability;
  verify: ActionAvailability;
  /**
   * The operation MAKE names, so a caller can go to it without re-deriving
   * which one it was and risking a different answer.
   */
  makeOperationId: string | null;
}

const VERIFY_WORDS: Record<FeatureDetail["verify"]["state"], string> = {
  CONFORMS: "Conforms",
  NONCONFORMS: "Does not conform",
  NOT_MEASURED: "Not measured",
  CANNOT_DETERMINE: "Cannot determine",
};

/**
 * The same predicate the feature panel and the FAIR engine use. A feature
 * with no tolerance, no critical flag and no stated inspection method is not
 * an inspection characteristic, and offering to measure it would invent a
 * requirement nobody set.
 */
function isCharacteristic(feature: Feature): boolean {
  return Boolean(feature.tolerance || feature.critical || feature.inspectionMethod);
}

export function featureActions(input: {
  feature: Feature;
  detail: FeatureDetail | undefined;
  operations: RunwayOperation[];
  inspectionSessionId: string | null;
}): FeatureActions {
  const { feature, detail, operations, inspectionSessionId } = input;

  const cutting = operations
    .filter((o) => o.featureId === feature.id)
    .sort((a, b) => a.sequence - b.sequence);
  const first = cutting[0];

  return {
    makeOperationId: first?.id ?? null,

    detail: { available: true, detail: feature.functionalRole ?? feature.kind.replace(/_/g, " ").toLowerCase() },

    measure: !isCharacteristic(feature)
      ? { available: false, reason: "Not an inspection characteristic" }
      : { available: true, detail: inspectionSessionId ? "Session open" : "Start a session" },

    // MAKE names the operation that cuts this feature. It never CREATES one —
    // planning is the machinist's act on the setups page — so where nothing
    // cuts the feature this says so rather than offering a control.
    make: !first
      ? { available: false, reason: "No operation in the plan cuts this feature" }
      : {
          available: true,
          // A placeholder operation has no toolpath, so it has no cycle time
          // to quote. Printing one would be quoting a number for motion that
          // does not exist.
          detail: first.error
            ? `Op ${first.sequence} · ${first.error}`
            : first.isPlaceholder
              ? `Op ${first.sequence} · ${first.toolNumber != null ? `T${first.toolNumber}` : "no tool"} · no toolpath`
              : `Op ${first.sequence} · ${first.toolNumber != null ? `T${first.toolNumber}` : "no tool"}${
                  first.cycleMinutes != null ? ` · ${first.cycleMinutes.toFixed(2)} min` : ""
                }`,
        },

    verify: !detail
      ? { available: false, reason: "No inspection plan" }
      : detail.verify.state === "NOT_MEASURED" && !detail.capability
        ? { available: false, reason: "No inspection plan" }
        : { available: true, detail: VERIFY_WORDS[detail.verify.state] },
  };
}
