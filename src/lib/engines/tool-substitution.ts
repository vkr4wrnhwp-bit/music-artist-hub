import type { Tool } from "@/lib/domain/shop";
import { canReach } from "@/lib/domain/shop";

/**
 * TOOL SUBSTITUTION
 *
 * "Drill a 1.000 hole." Do you own a 1.000 drill? Most shops do not own every
 * size, and the answer a machinist gives is never "you cannot make this part".
 * It is: drill 15/16, then come in and take the remainder with a boring head,
 * or an end mill, or a reamer — one clean finishing pass to size.
 *
 * This produces that chain. It works only from the crib as recorded, states
 * the remaining stock per side at every step, and refuses the chain when the
 * remainder lands somewhere a finishing pass will not behave — too little and
 * the tool rubs and chatters instead of cutting, too much and it is a roughing
 * pass wearing a finishing pass's name.
 *
 * When nothing in the crib can do it, it says what to buy rather than
 * inventing a way through.
 */

export type HoleStrategy = "EXACT_DRILL" | "DRILL_THEN_REAM" | "DRILL_THEN_BORE" | "DRILL_THEN_MILL" | "MILL_ONLY";

export interface SubstitutionStep {
  order: number;
  action: string;
  toolId: string | null;
  toolNumber: number | null;
  toolDescription: string;
  /** Diameter this step leaves behind. */
  resultingDiameter: number;
  /** Material left on the wall after this step, per side. */
  remainingPerSide: number;
  rationale: string;
}

export interface SubstitutionResult {
  ok: boolean;
  strategy: HoleStrategy | null;
  /** True when a single tool does the job and no chain is needed. */
  exact: boolean;
  targetDiameter: number;
  steps: SubstitutionStep[];
  warnings: string[];
  /** Populated only when the crib genuinely cannot produce the feature. */
  blocked: string | null;
  /** Concrete purchase that would remove the problem. */
  suggestedPurchase: string | null;
}

/**
 * A finishing pass wants a predictable bite. Below the minimum the cutting
 * edge burnishes rather than cuts, which work-hardens the wall and chatters;
 * above the maximum it deflects and you are no longer finishing.
 */
const MIN_FINISH_PER_SIDE = 0.004;
const MAX_FINISH_PER_SIDE = 0.03;
/** A reamer expects a specific allowance; too much and it will not hold size. */
const REAM_MIN_PER_SIDE = 0.005;
const REAM_MAX_PER_SIDE = 0.016;

const near = (a: number, b: number, tol = 0.0005) => Math.abs(a - b) <= tol;

export interface SubstitutionInput {
  targetDiameter: number;
  depth: number;
  /** True when the hole carries a real tolerance and needs a finishing step. */
  precision: boolean;
  tools: Tool[];
}

export function planHole(input: SubstitutionInput): SubstitutionResult {
  const { targetDiameter: target, depth, precision, tools } = input;
  const warnings: string[] = [];

  const usable = tools.filter((t) => canReach(t, depth));
  const drills = usable.filter((t) => t.toolClass === "DRILL").sort((a, b) => b.diameter - a.diameter);
  const reamers = usable.filter((t) => t.toolClass === "REAMER");
  const boring = usable.filter((t) => t.toolClass === "BORING_TOOL");
  const mills = usable
    .filter((t) => t.toolClass === "FLAT_END_MILL" || t.toolClass === "BULL_NOSE")
    .sort((a, b) => b.diameter - a.diameter);

  const result = (partial: Partial<SubstitutionResult>): SubstitutionResult => ({
    ok: false,
    strategy: null,
    exact: false,
    targetDiameter: target,
    steps: [],
    warnings,
    blocked: null,
    suggestedPurchase: null,
    ...partial,
  });

  /* ---- 1. Exact drill, and the hole does not need to hold size ---- */

  const exactDrill = drills.find((d) => near(d.diameter, target));
  if (exactDrill && !precision) {
    return result({
      ok: true,
      exact: true,
      strategy: "EXACT_DRILL",
      steps: [
        step(1, `Drill ⌀${target.toFixed(4)}`, exactDrill, target, 0, "Exact size in the crib and the hole carries no tolerance, so one operation finishes it."),
      ],
    });
  }

  /* ---- 2. Reamed: drill under, ream to size ---- */

  const reamer = reamers.find((r) => near(r.diameter, target));
  if (reamer) {
    const candidate = drills.find((d) => {
      const per = (target - d.diameter) / 2;
      return per >= REAM_MIN_PER_SIDE && per <= REAM_MAX_PER_SIDE;
    });
    if (candidate) {
      const per = (target - candidate.diameter) / 2;
      return result({
        ok: true,
        strategy: "DRILL_THEN_REAM",
        steps: [
          step(1, `Drill ⌀${candidate.diameter.toFixed(4)}`, candidate, candidate.diameter, per, `Largest drill that leaves a reaming allowance — ${(per * 2).toFixed(4)} on diameter.`),
          step(2, `Ream ⌀${target.toFixed(4)}`, reamer, target, 0, "A reamer follows the drilled hole and holds size and finish without an interpolation."),
        ],
      });
    }
    warnings.push(
      `A ⌀${target.toFixed(4)} reamer is in the crib but no drill leaves a workable ${REAM_MIN_PER_SIDE}–${REAM_MAX_PER_SIDE}" reaming allowance.`,
    );
  }

  /* ---- 3. Bored: drill under, single finish pass with the boring head ---- */

  const boringHead = boring.find((b) => target >= b.diameter * 0.5 && target <= Math.max(b.diameter * 1.6, b.diameter + 1));
  if (boringHead) {
    const candidate = drills.find((d) => {
      const per = (target - d.diameter) / 2;
      return per >= MIN_FINISH_PER_SIDE && per <= MAX_FINISH_PER_SIDE;
    });
    if (candidate) {
      const per = (target - candidate.diameter) / 2;
      return result({
        ok: true,
        strategy: "DRILL_THEN_BORE",
        steps: [
          step(1, `Drill ⌀${candidate.diameter.toFixed(4)}`, candidate, candidate.diameter, per, `Largest drill under size — leaves ${per.toFixed(4)}" per side for the boring head.`),
          step(2, `Bore to ⌀${target.toFixed(4)}`, boringHead, target, 0, `Single finishing pass takes the remaining ${per.toFixed(4)}" per side. A boring head holds size and roundness in a way a drill cannot.`),
        ],
      });
    }
    // Drill leaves too much — rough it out with a mill first, then bore.
    const rougher = mills.find((m) => m.diameter < target - 2 * MIN_FINISH_PER_SIDE);
    const biggestDrill = drills[0];
    if (rougher) {
      const roughDiameter = Number((target - 2 * MAX_FINISH_PER_SIDE).toFixed(4));
      const steps: SubstitutionStep[] = [];
      let order = 1;
      if (biggestDrill && biggestDrill.diameter < roughDiameter) {
        steps.push(
          step(order++, `Drill ⌀${biggestDrill.diameter.toFixed(4)}`, biggestDrill, biggestDrill.diameter, (target - biggestDrill.diameter) / 2, "Largest drill in the crib, used to open a starting hole rather than to size."),
        );
      }
      steps.push(
        step(order++, `Interpolate to ⌀${roughDiameter.toFixed(4)}`, rougher, roughDiameter, MAX_FINISH_PER_SIDE, `Helical interpolation opens the hole to within ${MAX_FINISH_PER_SIDE.toFixed(3)}" per side of finish size.`),
      );
      steps.push(
        step(order, `Bore to ⌀${target.toFixed(4)}`, boringHead, target, 0, "Boring head takes the remainder in one pass for size and roundness."),
      );
      return result({ ok: true, strategy: "DRILL_THEN_BORE", steps });
    }
  }

  /* ---- 4. Milled: interpolate with an end mill ---- */

  const mill = mills.find((m) => m.diameter < target - 2 * MIN_FINISH_PER_SIDE);
  if (mill) {
    const steps: SubstitutionStep[] = [];
    let order = 1;
    const starter = drills.find((d) => d.diameter < target - 2 * MIN_FINISH_PER_SIDE);
    if (starter) {
      steps.push(
        step(order++, `Drill ⌀${starter.diameter.toFixed(4)}`, starter, starter.diameter, (target - starter.diameter) / 2, "Drilling first removes the bulk faster than interpolating from solid."),
      );
    }
    if (precision) {
      const roughDiameter = Number((target - 2 * 0.012).toFixed(4));
      steps.push(
        step(order++, `Rough interpolate to ⌀${roughDiameter.toFixed(4)}`, mill, roughDiameter, 0.012, "Leaves 0.012\" per side so the finishing pass cuts rather than rubs."),
      );
      steps.push(
        step(order, `Finish interpolate to ⌀${target.toFixed(4)}`, mill, target, 0, "Light finishing pass at reduced feed. An interpolated hole will hold size but not roundness as well as a bored one."),
      );
      warnings.push(
        `${target.toFixed(4)} is being produced by interpolation because there is no boring head or reamer at size. Expect to inspect the first article carefully — roundness is the weak point.`,
      );
    } else {
      steps.push(
        step(order, `Interpolate to ⌀${target.toFixed(4)}`, mill, target, 0, `⌀${mill.diameter.toFixed(4)} end mill interpolated to size — no tolerance on this hole, so a single pass is enough.`),
      );
    }
    return result({ ok: true, strategy: steps.length > 1 ? "DRILL_THEN_MILL" : "MILL_ONLY", steps });
  }

  /* ---- 5. Nothing works ---- */

  const biggest = mills[0] ?? drills[0];
  return result({
    blocked:
      drills.length === 0 && mills.length === 0
        ? "There are no drills or end mills in the crib that reach this depth."
        : `Nothing in the crib is small enough to produce a ⌀${target.toFixed(4)} hole — the smallest usable cutter is ⌀${(biggest?.diameter ?? 0).toFixed(4)}.`,
    suggestedPurchase:
      target > 0.5
        ? `A boring head covering ⌀${target.toFixed(4)}, or a ⌀${(target - 0.0625).toFixed(4)} drill to rough with.`
        : `A ⌀${target.toFixed(4)} reamer, or an end mill smaller than ⌀${(target - 2 * MIN_FINISH_PER_SIDE).toFixed(4)} to interpolate with.`,
  });
}

function step(
  order: number,
  action: string,
  tool: Tool,
  resultingDiameter: number,
  remainingPerSide: number,
  rationale: string,
): SubstitutionStep {
  return {
    order,
    action,
    toolId: tool.id,
    toolNumber: tool.toolNumber,
    toolDescription: tool.description,
    resultingDiameter,
    remainingPerSide,
    rationale,
  };
}

/**
 * Plain-language summary of a chain, for the places that show one line rather
 * than the whole plan.
 */
export function describeSubstitution(r: SubstitutionResult): string {
  if (r.blocked) return r.blocked;
  if (r.exact) return `⌀${r.targetDiameter.toFixed(4)} drill, one operation.`;
  return r.steps.map((s) => s.action).join(" → ");
}
