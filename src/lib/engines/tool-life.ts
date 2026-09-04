/**
 * WHAT THIS TOOL HAS ACTUALLY DONE.
 *
 * `Tool.lifeRemaining` was a 0-1 float. It was required on the tool form,
 * shown on the tools page as a colour-coded percentage chip — green above 40%,
 * review above 15%, risk below — and **nothing in the system ever changed it**.
 * It was whatever somebody typed when the tool was added, possibly a year ago,
 * presented as a live gauge.
 *
 * A machinist reading "T2 · 100%" in green reasonably concludes that tool has
 * plenty of life left. That is worse than showing nothing, and it is worse than
 * a stub, because a stub says so.
 *
 * WHAT IS COUNTED, AND WHAT IS NOT
 *
 * Minutes accumulate when a job is marked COMPLETE, from the cutting time the
 * toolpaths charge to this tool times the quantity made. That makes every
 * figure here a LOWER BOUND: a job run without being recorded, a tool borrowed
 * for another part, a re-run after a scrap — all of it is time this never saw.
 * The verdict says so rather than implying the count is complete, because a
 * machinist who thinks 40% is left and actually has 5% is the person this
 * feature exists to protect.
 *
 * And a tool with no expected life recorded gets **no percentage at all**.
 * There is nothing to be a percentage of, and inventing a denominator is how
 * the 0-1 float got there in the first place.
 */

export type ToolLifeState = "UNTRACKED" | "FRESH" | "IN_USE" | "NEAR_END" | "PAST_EXPECTED";

export interface ToolLifeInput {
  description: string;
  minutesUsed: number;
  partsCut: number;
  expectedLifeMinutes: number;
  lifeCountedFrom: Date | null;
  regrindCount: number;
}

export interface ToolLife {
  state: ToolLifeState;
  /** Null when there is no expected life to measure against. */
  fractionUsed: number | null;
  minutesUsed: number;
  partsCut: number;
  /** One line for a table cell. */
  summary: string;
  /** What the number does and does not include. */
  caveat: string;
}

/** Past this, a shop wants to be looking at the edge before the next job. */
const NEAR_END = 0.8;

/*
 * A spot drill charged 0.4 min of a job reads "0 min over 1 part" at whole-
 * minute resolution, which says the tool did nothing. It is the same class of
 * error as the float this replaced, just small: a number that is wrong in a
 * direction a machinist cannot see. Short times keep a decimal, and a real
 * charge never rounds down to nothing.
 */
export function formatMinutes(m: number): string {
  if (m >= 10) return m.toFixed(0);
  if (m >= 0.1) return m.toFixed(1);
  return m > 0 ? "under 0.1" : "0";
}

export function toolLife(t: ToolLifeInput): ToolLife {
  const since = t.lifeCountedFrom
    ? `since ${t.lifeCountedFrom.toISOString().slice(0, 10)}`
    : "since nobody said when";
  const counted = `${formatMinutes(t.minutesUsed)} min over ${t.partsCut} part${t.partsCut === 1 ? "" : "s"} ${since}`;

  /*
   * The caveat is not a footnote. It is the difference between a figure a
   * machinist can act on and one they cannot, and it belongs beside the number
   * rather than under it.
   */
  const caveat =
    `Counted from jobs marked complete in CANVAS, so it is a floor and not a total — a job run without being recorded, or this tool borrowed for another part, is time nothing here saw.` +
    (t.regrindCount > 0 ? ` Reground ${t.regrindCount} time${t.regrindCount === 1 ? "" : "s"}.` : "");

  if (!(t.expectedLifeMinutes > 0)) {
    return {
      state: "UNTRACKED",
      fractionUsed: null,
      minutesUsed: t.minutesUsed,
      partsCut: t.partsCut,
      summary: `${counted}. No expected life recorded, so there is nothing to measure it against.`,
      caveat,
    };
  }

  const fraction = t.minutesUsed / t.expectedLifeMinutes;
  const state: ToolLifeState =
    t.minutesUsed <= 0 ? "FRESH" : fraction >= 1 ? "PAST_EXPECTED" : fraction >= NEAR_END ? "NEAR_END" : "IN_USE";

  const summary =
    state === "FRESH"
      ? `Nothing recorded against it yet. Expected life ${t.expectedLifeMinutes.toFixed(0)} min.`
      : state === "PAST_EXPECTED"
        ? `${counted} — past the ${t.expectedLifeMinutes.toFixed(0)} min this tool is expected to give. Look at the edge before the next job.`
        : `${counted}, against ${t.expectedLifeMinutes.toFixed(0)} min expected.`;

  return { state, fractionUsed: fraction, minutesUsed: t.minutesUsed, partsCut: t.partsCut, summary, caveat };
}

/**
 * Minutes to charge to each tool for one completed job.
 *
 * The ACTUAL cycle time is used where a machinist recorded one, because it is
 * what the tool was in the cut for; the estimate is the fallback and the caller
 * says which it used. Actual time is one number for the whole job, so it is
 * apportioned across tools in the ratio of their estimated cutting times —
 * there is nothing per tool to measure against, and pretending otherwise would
 * put a measured-looking figure on a share that was derived.
 */
export function minutesPerTool(
  toolpaths: { toolId: string; cycleTimeMinutes: number }[],
  quantity: number,
  actualCycleMinutes: number | null,
): { byTool: Map<string, number>; source: "MEASURED" | "ESTIMATED" } {
  const byTool = new Map<string, number>();
  const estimatedTotal = toolpaths.reduce((sum, tp) => sum + tp.cycleTimeMinutes, 0);
  const useActual = actualCycleMinutes !== null && actualCycleMinutes > 0 && estimatedTotal > 0;
  const scale = useActual ? actualCycleMinutes! / estimatedTotal : 1;

  for (const tp of toolpaths) {
    const minutes = tp.cycleTimeMinutes * scale * Math.max(1, quantity);
    byTool.set(tp.toolId, (byTool.get(tp.toolId) ?? 0) + minutes);
  }
  return { byTool, source: useActual ? "MEASURED" : "ESTIMATED" };
}
