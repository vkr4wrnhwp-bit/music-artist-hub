import { FEATURE_FIELDS } from "@/lib/domain/feature-input";
import type { Feature, FeatureKind } from "@/lib/domain/features";

/**
 * THE FEATURE SPECIMEN
 *
 * "When the user selects a feature: isolate it, enlarge it, allow rotation,
 * show dimension lines, show nominal vs measured, show the mating component,
 * show tabs — GEOMETRY, FUNCTION, MEASURE."
 *
 * Nothing rendered a specimen. The only trace was a `specimenMode` boolean and
 * a SPECIMEN action in the interaction reducer with no consumers at all, so
 * selecting a feature opened the ordinary side panel.
 *
 * This is the deterministic half: what each tab is entitled to say, assembled
 * from records rather than described. The rule throughout is the one that
 * matters on a page a machinist reads dimensions off — **a value that was not
 * recorded is reported as not recorded.** A nominal-vs-measured comparison
 * where one side is missing is not a comparison, and printing a dash where a
 * measurement should be is better than printing the nominal twice.
 */

export const SPECIMEN_TABS = ["GEOMETRY", "FUNCTION", "MEASURE", "MACHINE", "INSPECT", "HISTORY"] as const;
export type SpecimenTab = (typeof SPECIMEN_TABS)[number];

export const SPECIMEN_TAB_LABEL: Record<SpecimenTab, string> = {
  GEOMETRY: "Geometry",
  FUNCTION: "Function",
  MEASURE: "Measure",
  MACHINE: "Machine",
  INSPECT: "Inspect",
  HISTORY: "History",
};

export interface DimensionRow {
  label: string;
  /** As designed. Null when the feature does not carry it. */
  nominal: number | null;
  unit: string;
  /** As measured, when something measured it. Null is "not measured". */
  measured: number | null;
  /** measured − nominal. Null when either side is missing. */
  deviation: number | null;
  /** The instrument's uncertainty on that reading, when one is recorded. */
  uncertainty: number | null;
  /** Whether the deviation sits inside the feature's own tolerance band. */
  verdict: "IN_TOLERANCE" | "OUT_OF_TOLERANCE" | "NO_TOLERANCE_STATED" | "NOT_MEASURED";
}

export interface MeasuredValue {
  /** Which dimension it is a reading of, matched by the feature's own field name. */
  field: string;
  value: number;
  uncertainty: number;
  at: Date;
}

/**
 * The dimensions this feature actually has, from the same field spec the entry
 * form and the proposal path use — so a specimen cannot show a dimension the
 * feature does not carry, or miss one it does.
 */
export function specimenDimensions(
  feature: Feature,
  tolerance: { plus: number; minus: number } | null,
  measured: MeasuredValue[],
): DimensionRow[] {
  const fields = FEATURE_FIELDS[feature.kind as FeatureKind] ?? [];
  const record = feature as unknown as Record<string, unknown>;

  return fields
    .filter((f) => f.type === "number")
    .map((f) => {
      const raw = record[f.name];
      const nominal = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
      const hit = measured.find((m) => m.field === f.name) ?? null;
      const value = hit?.value ?? null;
      const deviation = nominal != null && value != null ? value - nominal : null;

      let verdict: DimensionRow["verdict"];
      if (value == null) verdict = "NOT_MEASURED";
      else if (tolerance == null) verdict = "NO_TOLERANCE_STATED";
      else if (deviation == null) verdict = "NOT_MEASURED";
      else verdict = deviation <= tolerance.plus && deviation >= -tolerance.minus ? "IN_TOLERANCE" : "OUT_OF_TOLERANCE";

      return {
        label: f.label,
        nominal,
        unit: f.unit ?? "",
        measured: value,
        deviation,
        uncertainty: hit?.uncertainty ?? null,
        verdict,
      };
    });
}

/**
 * Whether a deviation is worth calling out at all given the instrument.
 *
 * A 0.0002" deviation read with a ±0.0005" caliper is not a deviation, it is
 * the instrument. Saying otherwise sends somebody chasing a dimension that was
 * never out.
 */
export function deviationIsResolvable(deviation: number | null, uncertainty: number | null): boolean | null {
  if (deviation == null || uncertainty == null) return null;
  return Math.abs(deviation) > uncertainty;
}

/** Which views of this feature a drawing can honestly produce. */
export const SPECIMEN_VIEWS = ["PLAN", "SECTION"] as const;
export type SpecimenView = (typeof SPECIMEN_VIEWS)[number];

/**
 * A section is only a different drawing for a feature with depth. A chamfer
 * or a fillet sectioned looks like the plan and adds nothing, so the view is
 * not offered rather than offered and empty.
 */
export function viewsFor(kind: string): SpecimenView[] {
  const hasDepth = (FEATURE_FIELDS[kind as FeatureKind] ?? []).some((f) => f.name === "depth" || f.name === "height");
  return hasDepth ? ["PLAN", "SECTION"] : ["PLAN"];
}
