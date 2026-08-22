import { RISK_ORDER, type RiskLevel } from "./engines/workholding";
import type { MachinistPlan } from "./engines/machinist";

/**
 * Comparing scored plans. Split out of machinist-review.ts, which is
 * server-only because it drives the CAM engine — this half is arithmetic over
 * numbers already computed, and keeping it here lets it be exercised without
 * generating a toolpath.
 */

export interface ScoredPlanSummary {
  plan: MachinistPlan;
  setupCount: number;
  /**
   * DISTINCT tools the plan needs — not the number of times the spindle
   * changes tool, which depends on the order operations run in and is what
   * sequencing.ts's countToolChanges measures. This field was called
   * `toolChanges`, which is a different quantity: a plan running tools
   * 1, 2, 1, 2 needs two tools and makes four changes. The UI has always
   * labelled it "tools", so the number shown was right and only the name was
   * wrong — but the next person to read it would have believed the name.
   */
  distinctTools: number;
  operationCount: number;
  cycleMinutes: number;
  risk: RiskLevel;
  unitCost: number;
  errors: string[];
}

export interface PlanComparison {
  fastest: string | null;
  cheapest: string | null;
  safest: string | null;
  fewestSetups: string | null;
  fewestTools: string | null;
}

/**
 * Names the plan that wins on each axis. Deliberately does not declare an
 * overall winner: which axis matters is a business decision about this job,
 * and that belongs to the person who owns the shop, not to the software.
 */
export function comparePlans<T extends ScoredPlanSummary>(scored: T[]): PlanComparison {
  const none: PlanComparison = { fastest: null, cheapest: null, safest: null, fewestSetups: null, fewestTools: null };
  const usable = scored.filter((s) => s.errors.length === 0 && s.cycleMinutes > 0);
  if (usable.length === 0) return none;

  const best = (list: T[], by: (s: T) => number) =>
    list.reduce((a, b) => (by(a) <= by(b) ? a : b)).plan.philosophy.name;

  // A plan whose workholding could not be assessed is not a safe plan; it is
  // an unassessed one. When that is true of every plan there is no safest,
  // and naming one would present an unknown as a comparison result.
  const assessed = usable.filter((s) => s.risk !== "UNKNOWN");

  return {
    fastest: best(usable, (s) => s.cycleMinutes),
    cheapest: best(usable, (s) => s.unitCost),
    safest: assessed.length > 0 ? best(assessed, (s) => RISK_ORDER[s.risk]) : null,
    fewestSetups: best(usable, (s) => s.setupCount),
    fewestTools: best(usable, (s) => s.distinctTools),
  };
}
