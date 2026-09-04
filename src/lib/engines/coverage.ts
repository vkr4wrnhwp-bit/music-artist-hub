import type { Feature } from "@/lib/domain/features";

/**
 * FEATURE COVERAGE — is every feature on the part actually made by this program?
 *
 * The pre-flight gate already reasons this way one level down. Its own comment,
 * about operations whose toolpath engine produced no motion:
 *
 *   "An operation with no engine is not omitted from the program; the post
 *    writes it in as a comment and moves on. The program is syntactically
 *    complete, runs start to finish, and simply never cuts those features."
 *
 * The same hole sits one level up and nothing watched it. A feature that no
 * operation is planned against is not refused, not warned about and not
 * mentioned — the program runs to completion and hands back a part missing its
 * bearing bore. Nobody inspects for the ABSENCE of a feature; every inspection
 * method in this system measures something that is there.
 *
 * TWO LAYERS, TWO FACTS
 *
 * This engine answers "is every feature addressed by an operation". The
 * pre-flight item `toolpaths` answers "did every operation produce motion".
 * Neither substitutes for the other, and both are needed: an unplanned feature
 * and a planned one whose engine refused are different failures with the same
 * consequence at the machine.
 *
 * NOT EVERY FEATURE IS CUT BY THE PROGRAM, AND THAT IS NOT A DEFECT
 *
 * A FILLET has no operation type in the CAM engine at all. A chamfer is often
 * broken by hand at the bench. A bore can be a vendor operation, or already in
 * the extrusion. A gate that could not express any of that would be a gate
 * every shop learns to ignore, which is worse than no gate.
 *
 * So a human may state that a feature is not machined by this program — in a
 * sentence, recorded with their name and the time, not a checkbox. It is a
 * manufacturing fact only a person can know, in the same class as confirming
 * the material, and it is deliberately NOT the same thing as clearing a safety
 * gate by acknowledging it: nothing here is an engineering condition that
 * evidence would have to settle. The sentence is the evidence, and the gate
 * repeats it rather than swallowing it.
 */

export interface CoverageOperation {
  id: string;
  label: string;
  /** Null for operations that cut stock rather than a named feature. */
  featureId: string | null;
}

export type CoverageState = "CUT" | "ACCOUNTED_FOR" | "UNCUT";

export interface FeatureCoverage {
  featureId: string;
  label: string;
  kind: string;
  state: CoverageState;
  /** Operations planned against this feature. Empty unless CUT. */
  operationLabels: string[];
  /** What the human said instead. Null unless ACCOUNTED_FOR. */
  reason: string | null;
}

export interface CoverageReport {
  entries: FeatureCoverage[];
  cut: FeatureCoverage[];
  accountedFor: FeatureCoverage[];
  uncut: FeatureCoverage[];
  /**
   * False when there is nothing to assess yet — no features, or no operation
   * anywhere in the plan. An unwritten plan is not a coverage failure, and
   * reporting it as one would put the wrong sentence in front of the operator.
   */
  planned: boolean;
}

export function assessCoverage(features: Feature[], operations: CoverageOperation[]): CoverageReport {
  const byFeature = new Map<string, string[]>();
  for (const op of operations) {
    if (!op.featureId) continue;
    const list = byFeature.get(op.featureId) ?? [];
    list.push(op.label);
    byFeature.set(op.featureId, list);
  }

  const entries: FeatureCoverage[] = features.map((f) => {
    const ops = byFeature.get(f.id) ?? [];
    if (ops.length > 0) {
      return { featureId: f.id, label: f.label, kind: f.kind, state: "CUT" as const, operationLabels: ops, reason: null };
    }
    // Blank and whitespace are not a reason. A row carrying an empty string is
    // a feature nobody accounted for, and it reads as uncut here.
    const reason = (f.notMachinedReason ?? "").trim();
    return reason
      ? { featureId: f.id, label: f.label, kind: f.kind, state: "ACCOUNTED_FOR" as const, operationLabels: [], reason }
      : { featureId: f.id, label: f.label, kind: f.kind, state: "UNCUT" as const, operationLabels: [], reason: null };
  });

  return {
    entries,
    cut: entries.filter((e) => e.state === "CUT"),
    accountedFor: entries.filter((e) => e.state === "ACCOUNTED_FOR"),
    uncut: entries.filter((e) => e.state === "UNCUT"),
    planned: features.length > 0 && operations.length > 0,
  };
}

/**
 * The sentence both the readiness gate and the export pre-flight say.
 *
 * One function because the two used to be the place this codebase learned its
 * lesson about duplicated gate logic: if the rule exists in two places, it does
 * not exist. The status is decided here too, so the export gate and the
 * readiness gate cannot disagree about the same part.
 */
export function coverageVerdict(report: CoverageReport): { ok: boolean; detail: string } {
  if (!report.planned) {
    return {
      ok: false,
      detail:
        report.entries.length === 0
          ? "No features are defined, so there is nothing to cut."
          : "No operations are planned, so no feature on this part is cut by this program.",
    };
  }

  if (report.uncut.length > 0) {
    const named = report.uncut.slice(0, 3).map((e) => e.label).join(", ");
    const more = report.uncut.length > 3 ? ` and ${report.uncut.length - 3} more` : "";
    return {
      ok: false,
      detail: `${report.uncut.length} of ${report.entries.length} features have no operation: ${named}${more}. The program runs to completion without cutting them.`,
    };
  }

  if (report.accountedFor.length > 0) {
    const named = report.accountedFor.map((e) => `${e.label} — ${e.reason}`).join("; ");
    return {
      ok: true,
      detail: `${report.cut.length} of ${report.entries.length} features are cut by this program. Not by this program: ${named}.`,
    };
  }

  return { ok: true, detail: `All ${report.entries.length} features are cut by an operation in this plan.` };
}
