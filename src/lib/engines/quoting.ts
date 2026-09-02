import type { CostAssumptions, CostResult } from "./cost";

/**
 * QUOTING — a stored estimate is a promise, and a promise has to be defensible
 *
 * The page's own subtitle said quotes "carry their assumption set… so a quote
 * can be defended, re-run against changed rates, or compared against what the
 * job actually cost", and nothing in the application could store one. The Cost
 * panel computed a live figure and threw it away on navigation.
 *
 * Three deterministic things live here:
 *
 *   1. What a quote may do next — a closed transition table, like a job's.
 *   2. Whether a stored estimate still reflects today's rates, and exactly
 *      which assumptions moved.
 *   3. What the job actually cost against what was quoted.
 *
 * None of it invents a number. Every comparison returns null and names what is
 * missing rather than substituting a plausible value.
 */

/* ------------------------------------------------------------------ */
/* Quote lifecycle                                                     */
/* ------------------------------------------------------------------ */

export const QUOTE_STATUSES = ["DRAFT", "SENT", "WON", "LOST", "EXPIRED"] as const;
export type QuoteStatus = (typeof QUOTE_STATUSES)[number];

export const QUOTE_STATUS_LABEL: Record<QuoteStatus, string> = {
  DRAFT: "Draft",
  SENT: "Sent to the customer",
  WON: "Won",
  LOST: "Lost",
  EXPIRED: "Expired",
};

/**
 * A quote goes out once. After that it was won, lost, or it ran out — and
 * none of those are edited back into a draft, because the number the customer
 * holds does not change when the shop changes its mind. A revised price is a
 * new quote.
 */
export const NEXT_QUOTE_STATUS: Record<QuoteStatus, QuoteStatus[]> = {
  DRAFT: ["SENT"],
  SENT: ["WON", "LOST", "EXPIRED"],
  WON: [],
  LOST: [],
  EXPIRED: [],
};

export function canTransitionQuote(from: string, to: string): boolean {
  if (!(QUOTE_STATUSES as readonly string[]).includes(from)) return false;
  if (!(QUOTE_STATUSES as readonly string[]).includes(to)) return false;
  return NEXT_QUOTE_STATUS[from as QuoteStatus].includes(to as QuoteStatus);
}

/** A quote may only be sent with an estimate on it. Otherwise it prices nothing. */
export function canSend(estimateCount: number): boolean {
  return estimateCount > 0;
}

/* ------------------------------------------------------------------ */
/* Has the ground moved under a stored estimate?                       */
/* ------------------------------------------------------------------ */

export interface AssumptionDrift {
  key: keyof CostAssumptions;
  label: string;
  quoted: number;
  now: number;
}

/** The assumptions worth telling somebody about when they move. */
const WATCHED: { key: keyof CostAssumptions; label: string }[] = [
  { key: "machineRate", label: "Machine rate, $/hr" },
  { key: "operatorRate", label: "Operator rate, $/hr" },
  { key: "materialCostPerPound", label: "Material, $/lb" },
  { key: "cycleMinutes", label: "Cycle, min/part" },
  { key: "setupHours", label: "Setup, hours" },
  { key: "scrapRate", label: "Scrap rate" },
  { key: "marginRate", label: "Margin" },
  { key: "materialUtilization", label: "Material utilisation" },
];

/**
 * Which stored assumptions no longer match the shop's current ones.
 *
 * This is why the whole assumption set is stored rather than just the price.
 * A quote sent three months ago at $85/hr is not wrong — it is a record of a
 * promise made at $85/hr — and the useful thing to show is exactly which
 * inputs moved, not a recomputed figure presented as if it were the quote.
 */
export function assumptionDrift(quoted: CostAssumptions, current: CostAssumptions): AssumptionDrift[] {
  const out: AssumptionDrift[] = [];
  for (const { key, label } of WATCHED) {
    const a = quoted[key];
    const b = current[key];
    if (typeof a !== "number" || typeof b !== "number") continue;
    // Exact comparison would report float noise as a rate change.
    if (Math.abs(a - b) < 1e-9) continue;
    out.push({ key, label, quoted: a, now: b });
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Quoted against what it actually cost                                */
/* ------------------------------------------------------------------ */

export interface ActualInputs {
  /** From the job, per part. Null when it was not recorded. */
  actualCycleMinutes: number | null;
  actualSetupHours: number | null;
  scrapCount: number;
  quantityRun: number;
}

export interface QuoteVsActual {
  quotedUnitCost: number;
  actualUnitCost: number;
  deltaPerPart: number;
  /** actual / quoted. Above 1 means the job cost more than it was quoted at. */
  ratio: number;
  /** Which recorded facts the actual cost was rebuilt from. */
  usedActuals: string[];
  /** What was not recorded, so the actual is partly the quoted assumption. */
  assumedFromQuote: string[];
}

/**
 * What the job cost, using the SAME cost engine and the same assumptions,
 * with the recorded actuals substituted where they exist.
 *
 * The honesty this needs: a job that recorded no setup hours has not told us
 * what setup cost, and the comparison must say that it fell back to the
 * quoted assumption rather than presenting a number as if it were measured.
 * When nothing at all was recorded there is no comparison, and it returns
 * null — a quote compared against itself is not feedback.
 */
export function compareQuoteToActual(
  quoted: CostResult,
  quotedAssumptions: CostAssumptions,
  actual: ActualInputs,
  recompute: (a: CostAssumptions, quantity: number) => CostResult,
): QuoteVsActual | null {
  const usedActuals: string[] = [];
  const assumedFromQuote: string[] = [];

  if (actual.actualCycleMinutes != null) usedActuals.push("cycle time");
  else assumedFromQuote.push("cycle time");
  if (actual.actualSetupHours != null) usedActuals.push("setup hours");
  else assumedFromQuote.push("setup hours");

  /*
   * The observed scrap rate, uncapped. cost.ts already clamps the divisor and
   * warns that "no part ever ships" at 100% — capping here at 0.99 would
   * suppress that warning and quietly present a run where nothing shipped as
   * a slightly expensive one.
   */
  const scrapRate = actual.quantityRun > 0 ? actual.scrapCount / actual.quantityRun : null;
  if (scrapRate != null) usedActuals.push("scrap rate");
  else assumedFromQuote.push("scrap rate");

  // Nothing was recorded: rebuilding the cost from the quote's own numbers
  // would produce a ratio of exactly 1.00 and call it agreement.
  if (usedActuals.length === 0) return null;

  const withActuals: CostAssumptions = {
    ...quotedAssumptions,
    cycleMinutes: actual.actualCycleMinutes ?? quotedAssumptions.cycleMinutes,
    setupHours: actual.actualSetupHours ?? quotedAssumptions.setupHours,
    scrapRate: scrapRate ?? quotedAssumptions.scrapRate,
  };
  const rebuilt = recompute(withActuals, quoted.quantity);

  return {
    quotedUnitCost: quoted.unitCost,
    actualUnitCost: rebuilt.unitCost,
    deltaPerPart: rebuilt.unitCost - quoted.unitCost,
    ratio: quoted.unitCost > 0 ? rebuilt.unitCost / quoted.unitCost : 0,
    usedActuals,
    assumedFromQuote,
  };
}
