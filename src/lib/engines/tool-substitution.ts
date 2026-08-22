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
export const MIN_FINISH_PER_SIDE = 0.004;
export const MAX_FINISH_PER_SIDE = 0.03;
/** A reamer expects a specific allowance; too much and it will not hold size. */
const REAM_MIN_PER_SIDE = 0.005;
const REAM_MAX_PER_SIDE = 0.016;
/**
 * What a roughing pass leaves for the pass that follows it. Comfortably
 * inside MIN..MAX so the finishing tool has a predictable bite whichever
 * route the chain took to get there.
 */
const ROUGH_LEAVES_PER_SIDE = 0.01;

/** A cutter has to be smaller than the hole it interpolates, with engagement to spare. */
const fitsInside = (toolDiameter: number, holeDiameter: number) =>
  toolDiameter + 2 * MIN_FINISH_PER_SIDE <= holeDiameter;

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

  if (!Number.isFinite(target) || target <= 0) {
    return {
      ok: false, strategy: null, exact: false, targetDiameter: target, steps: [], warnings,
      blocked: "No hole diameter was given, so there is nothing to plan a chain for.",
      suggestedPurchase: null,
    };
  }

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
    // Drill leaves too much for a single finishing pass. Something has to
    // rough it out first — either a mill, or the boring head itself.
    const roughDiameter = Number((target - 2 * ROUGH_LEAVES_PER_SIDE).toFixed(4));

    // The rougher has to fit inside the hole it is opening. This filter used
    // to be `m.diameter < target - 2 * MIN_FINISH_PER_SIDE`, which is the
    // FINISHED size, while the mill was then asked to interpolate the rough
    // hole 0.060 smaller. A ⌀0.980 mill passed the filter for a ⌀1.000 hole
    // and was handed a ⌀0.940 rough pass it cannot physically make.
    const rougher = mills.find((m) => fitsInside(m.diameter, roughDiameter));
    const biggestDrill = drills[0];

    const steps: SubstitutionStep[] = [];
    let order = 1;
    if (biggestDrill && fitsInside(biggestDrill.diameter, roughDiameter)) {
      steps.push(
        step(order++, `Drill ⌀${biggestDrill.diameter.toFixed(4)}`, biggestDrill, biggestDrill.diameter, (target - biggestDrill.diameter) / 2, "Largest drill in the crib, used to open a starting hole rather than to size."),
      );
    }

    if (rougher) {
      steps.push(
        step(order++, `Interpolate to ⌀${roughDiameter.toFixed(4)}`, rougher, roughDiameter, ROUGH_LEAVES_PER_SIDE, `Helical interpolation opens the hole to within ${ROUGH_LEAVES_PER_SIDE.toFixed(3)}" per side of finish size.`),
      );
    } else if (steps.length > 0 || drills.length > 0) {
      // No mill can rough it — so the boring head roughs it.
      //
      // This branch did not exist, and its absence broke the worked example
      // in this file's own header. "Drill 15/16, then come in with a boring
      // head" for a 1.000 hole leaves 0.03125 per side, a thousandth over
      // MAX_FINISH_PER_SIDE. With no mill in the crib to rough with, the
      // whole chain collapsed to blocked: "nothing in the crib is small
      // enough to produce a 1.0000 hole". A boring head was sitting in the
      // crib, and 15/16 is exactly the drill a machinist would reach for.
      // A boring head is not limited to one pass.
      steps.push(
        step(order++, `Rough bore to ⌀${roughDiameter.toFixed(4)}`, boringHead, roughDiameter, ROUGH_LEAVES_PER_SIDE, `The drilled hole leaves more than a finishing pass should take, so the boring head opens it in two: this pass leaves ${ROUGH_LEAVES_PER_SIDE.toFixed(3)}" per side.`),
      );
    }

    if (steps.length > 0) {
      steps.push(
        step(order, `Bore to ⌀${target.toFixed(4)}`, boringHead, target, 0, "Boring head takes the remainder in one pass for size and roundness."),
      );
      return result({
        ok: true,
        strategy: "DRILL_THEN_BORE",
        steps: steps.map((st, i) => ({ ...st, order: i + 1 })),
      });
    }
  }

  /* ---- 4. Milled: interpolate with an end mill ---- */

  // A precision hole is interpolated in two passes, so the mill has to fit
  // the ROUGH diameter — the smallest hole it is asked to make — not the
  // finished one. The filter checked the finished size and the mill was then
  // handed a rough pass 0.024 smaller: a ⌀0.985 mill was accepted for a
  // ⌀1.000 hole and told to interpolate ⌀0.976.
  const millRoughDiameter = Number((target - 2 * ROUGH_LEAVES_PER_SIDE).toFixed(4));
  const smallestHoleMilled = precision ? millRoughDiameter : target;
  const mill = mills.find((m) => fitsInside(m.diameter, smallestHoleMilled));
  if (mill) {
    const steps: SubstitutionStep[] = [];
    let order = 1;
    const starter = drills.find((d) => fitsInside(d.diameter, smallestHoleMilled));
    let drilled = false;
    if (starter) {
      drilled = true;
      steps.push(
        step(order++, `Drill ⌀${starter.diameter.toFixed(4)}`, starter, starter.diameter, (target - starter.diameter) / 2, "Drilling first removes the bulk faster than interpolating from solid."),
      );
    }
    if (precision) {
      steps.push(
        step(order++, `Rough interpolate to ⌀${millRoughDiameter.toFixed(4)}`, mill, millRoughDiameter, ROUGH_LEAVES_PER_SIDE, `Leaves ${ROUGH_LEAVES_PER_SIDE.toFixed(3)}" per side so the finishing pass cuts rather than rubs.`),
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
    // The strategy names the steps that are actually in the chain. This read
    // `steps.length > 1`, so a precision hole interpolated in two passes with
    // no drill anywhere came back as DRILL_THEN_MILL.
    return result({ ok: true, strategy: drilled ? "DRILL_THEN_MILL" : "MILL_ONLY", steps });
  }

  /* ---- 5. Nothing works ---- */

  // "The smallest usable cutter" used to be read off mills and drills only,
  // ignoring reamers and boring heads entirely — so a crib holding a boring
  // head at size was told nothing in it was small enough.
  const everySize = [...mills, ...drills, ...reamers, ...boring].map((t) => t.diameter);
  const smallest = everySize.length > 0 ? Math.min(...everySize) : null;
  return result({
    blocked:
      usable.length === 0
        ? "No tool in the crib reaches this depth."
        : smallest === null
          ? "There are no cutters in the crib that could produce a hole."
          : `Nothing in the crib can produce a ⌀${target.toFixed(4)} hole — the smallest usable cutter is ⌀${smallest.toFixed(4)}.`,
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
    // Rounded because these are displayed. (1.0 - 0.99) / 2 evaluates to
    // 0.0050000000000000044, and a stock allowance printed to seventeen
    // decimal places reads as a bug in the place a machinist is deciding
    // whether the pass is sane.
    resultingDiameter: Number(resultingDiameter.toFixed(4)),
    remainingPerSide: Number(remainingPerSide.toFixed(5)),
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
