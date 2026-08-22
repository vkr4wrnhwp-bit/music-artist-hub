/**
 * COST ENGINE
 *
 * Every number this produces is traceable to a stored assumption. There is no
 * "AI estimated $47" anywhere — if an input is a guess, it is a guess the user
 * can see and change, and the quote carries the assumption set that produced
 * it. That matters commercially as much as it does technically: a quote you
 * cannot defend in a customer meeting is worthless.
 */

export interface CostAssumptions {
  /** $/lb for the raw material. */
  materialCostPerPound: number;
  materialDensity: number; // lb/in³
  /** Stock volume per part, in³ — includes saw kerf and facing allowance. */
  stockVolumePerPart: number;
  /** Fraction of purchased stock that ends up in the finished part. */
  materialUtilization: number;
  /** Shop burdened machine rate, $/hr. */
  machineRate: number;
  /** Operator rate, $/hr — separate because a lights-out job is not the same job. */
  operatorRate: number;
  /** Fraction of the cycle that needs an operator present. */
  operatorAttendance: number;
  /** Setup time, hours — amortised across the lot. */
  setupHours: number;
  /** Machining cycle, minutes per part. */
  cycleMinutes: number;
  /** Total tooling cost consumed per part. */
  toolCostPerPart: number;
  /** Inspection minutes per part. */
  inspectionMinutes: number;
  inspectionRate: number;
  /** First-article inspection hours, charged once per lot. */
  firstArticleHours: number;
  /** Expected scrap fraction, 0–1. */
  scrapRate: number;
  /** Outside processing (anodise, heat treat, plating) $/part. */
  outsideProcessPerPart: number;
  packagingPerPart: number;
  /** Shop overhead applied to the cost base, as a fraction. */
  overheadRate: number;
  /** Target margin on the sell price, as a fraction of price. */
  marginRate: number;
}

export interface CostLine {
  label: string;
  perPart: number;
  perLot: number;
  /** Where this number came from, shown in the assumptions drawer. */
  basis: string;
}

export interface CostResult {
  quantity: number;
  lines: CostLine[];
  materialCost: number;
  machineCost: number;
  labourCost: number;
  toolingCost: number;
  inspectionCost: number;
  setupCostPerPart: number;
  outsideCost: number;
  scrapAdder: number;
  overhead: number;
  /** What it costs the shop to put the part on the bench. */
  unitCost: number;
  /** What the shop charges. */
  unitPrice: number;
  lotPrice: number;
  marginDollars: number;
  /** Spindle hours per part, so capacity can be worked out from the result. */
  cycleHoursPerPart: number;
  /** Setup hours for the lot, charged once. */
  setupHours: number;
  /**
   * Assumptions that are outside the range the arithmetic is valid over.
   * A quote carrying one of these is not defensible in a customer meeting,
   * which is the whole point of this engine.
   */
  warnings: string[];
}

/**
 * Assumptions the model cannot work with. These are not tuning judgements —
 * each one makes a specific term in the arithmetic meaningless.
 */
function assumptionWarnings(a: CostAssumptions): string[] {
  const w: string[] = [];

  for (const [key, value] of Object.entries(a) as [keyof CostAssumptions, number][]) {
    if (!Number.isFinite(value)) w.push(`${key} is not a number, so every figure derived from it is meaningless.`);
  }

  // Margin here is a fraction OF THE PRICE, so it cannot reach 1 — that would
  // be an infinite price. The settings form divides a typed percentage by 100,
  // so a shop owner entering 100 meaning "100% markup" lands exactly here, and
  // the quote came back at cost with zero margin and said nothing.
  if (Number.isFinite(a.marginRate) && a.marginRate >= 1) {
    w.push(
      `Margin is recorded as ${(a.marginRate * 100).toFixed(0)}% of the sell price, which cannot be reached — margin on price approaches 100% only as the price approaches infinity. The quote below is at cost with no margin at all. If 100% markup was meant, that is a margin of 50%.`,
    );
  }
  if (Number.isFinite(a.marginRate) && a.marginRate < 0) {
    w.push(`Margin is negative, so the quote is below cost by design.`);
  }
  if (Number.isFinite(a.materialUtilization) && a.materialUtilization > 1) {
    w.push(
      `Material utilisation is recorded as ${a.materialUtilization}, which is more than the stock purchased. Material cost is being divided by it and has come out far too low; utilisation is a fraction between 0 and 1.`,
    );
  }
  if (Number.isFinite(a.scrapRate) && a.scrapRate >= 1) {
    w.push(`Scrap rate is ${(a.scrapRate * 100).toFixed(0)}%, which means no part ever ships. The scrap allowance below is not a usable number.`);
  }
  return w;
}

export function computeCost(q: number, a: CostAssumptions): CostResult {
  const quantity = Math.max(1, Math.floor(q));

  const stockWeight = a.stockVolumePerPart * a.materialDensity;
  const materialCost = (stockWeight * a.materialCostPerPound) / Math.max(a.materialUtilization, 0.01);

  const cycleHours = a.cycleMinutes / 60;
  const machineCost = cycleHours * a.machineRate;
  const labourCost = cycleHours * a.operatorAttendance * a.operatorRate;

  const setupCostPerPart = ((a.setupHours * (a.machineRate + a.operatorRate)) / quantity);
  const firstArticlePerPart = (a.firstArticleHours * a.inspectionRate) / quantity;
  const inspectionCost = (a.inspectionMinutes / 60) * a.inspectionRate + firstArticlePerPart;

  const base =
    materialCost +
    machineCost +
    labourCost +
    a.toolCostPerPart +
    inspectionCost +
    setupCostPerPart +
    a.outsideProcessPerPart +
    a.packagingPerPart;

  // Scrap is charged on the base cost — a scrapped part consumed material,
  // machine time and an operator, not just material.
  const scrapAdder = base * (a.scrapRate / Math.max(1 - a.scrapRate, 0.01));
  const overhead = (base + scrapAdder) * a.overheadRate;

  const unitCost = base + scrapAdder + overhead;
  const unitPrice = a.marginRate >= 1 ? unitCost : unitCost / (1 - a.marginRate);
  const warnings = assumptionWarnings(a);

  const lines: CostLine[] = [
    { label: "Material", perPart: materialCost, perLot: materialCost * quantity, basis: `${a.stockVolumePerPart.toFixed(2)} in³ × ${a.materialDensity} lb/in³ × $${a.materialCostPerPound.toFixed(2)}/lb ÷ ${(a.materialUtilization * 100).toFixed(0)}% utilisation` },
    { label: "Machine time", perPart: machineCost, perLot: machineCost * quantity, basis: `${a.cycleMinutes.toFixed(2)} min × $${a.machineRate.toFixed(2)}/hr` },
    { label: "Operator", perPart: labourCost, perLot: labourCost * quantity, basis: `${(a.operatorAttendance * 100).toFixed(0)}% attendance × $${a.operatorRate.toFixed(2)}/hr` },
    { label: "Setup (amortised)", perPart: setupCostPerPart, perLot: a.setupHours * (a.machineRate + a.operatorRate), basis: `${a.setupHours.toFixed(2)} hr ÷ ${quantity} parts` },
    { label: "Tooling", perPart: a.toolCostPerPart, perLot: a.toolCostPerPart * quantity, basis: "Consumed tool life per part" },
    { label: "Inspection", perPart: inspectionCost, perLot: inspectionCost * quantity, basis: `${a.inspectionMinutes} min/part + ${a.firstArticleHours} hr FAI ÷ ${quantity}` },
    { label: "Outside processing", perPart: a.outsideProcessPerPart, perLot: a.outsideProcessPerPart * quantity, basis: "Per-part outside process cost" },
    { label: "Packaging", perPart: a.packagingPerPart, perLot: a.packagingPerPart * quantity, basis: "Per-part packaging" },
    { label: "Scrap allowance", perPart: scrapAdder, perLot: scrapAdder * quantity, basis: `${(a.scrapRate * 100).toFixed(1)}% expected scrap on full cost` },
    { label: "Overhead", perPart: overhead, perLot: overhead * quantity, basis: `${(a.overheadRate * 100).toFixed(0)}% of cost base` },
  ];

  return {
    quantity,
    lines,
    materialCost,
    machineCost,
    labourCost,
    toolingCost: a.toolCostPerPart,
    inspectionCost,
    setupCostPerPart,
    outsideCost: a.outsideProcessPerPart,
    scrapAdder,
    overhead,
    unitCost,
    unitPrice,
    lotPrice: unitPrice * quantity,
    marginDollars: (unitPrice - unitCost) * quantity,
    cycleHoursPerPart: cycleHours,
    setupHours: a.setupHours,
    warnings,
  };
}

export const STANDARD_QUANTITY_BREAKS = [1, 5, 10, 25, 100, 500, 1000];

export function quantityBreaks(a: CostAssumptions, quantities = STANDARD_QUANTITY_BREAKS): CostResult[] {
  return quantities.map((q) => computeCost(q, a));
}

/* ------------------------------------------------------------------ */
/* Make vs Buy                                                         */
/* ------------------------------------------------------------------ */

export interface MakeVsBuyOption {
  id: string;
  route: "MAKE" | "BUY" | "OUTSOURCE" | "ALTERNATIVE_PROCESS";
  label: string;
  unitCost: number | null;
  leadTimeDays: number | null;
  /** Every option records what it assumed, including "we do not know". */
  assumptions: string[];
  /** Populated only when the number is grounded in stored data. */
  grounded: boolean;
  notes: string;
}

export interface MakeVsBuyComparison {
  quantity: number;
  options: MakeVsBuyOption[];
  /** Null when nothing is grounded enough to recommend. */
  recommendation: string | null;
  caveats: string[];
}

export function compareMakeVsBuy(
  quantity: number,
  makeCost: CostResult,
  externalQuotes: { label: string; unitCost: number; leadTimeDays: number; source: string }[],
  capacityHoursAvailable: number | null,
): MakeVsBuyComparison {
  const options: MakeVsBuyOption[] = [
    {
      id: "make",
      route: "MAKE",
      label: "Make in-house",
      unitCost: makeCost.unitCost,
      leadTimeDays: null,
      assumptions: makeCost.lines.map((l) => `${l.label}: ${l.basis}`),
      grounded: true,
      notes: `Cost model output at quantity ${quantity}. Lead time depends on schedule and is not modelled.`,
    },
    ...externalQuotes.map((q, i) => ({
      id: `ext-${i}`,
      route: "BUY" as const,
      label: q.label,
      unitCost: q.unitCost,
      leadTimeDays: q.leadTimeDays,
      assumptions: [`Source: ${q.source}`],
      grounded: true,
      notes: "Externally supplied quote.",
    })),
  ];

  const caveats: string[] = [];
  if (capacityHoursAvailable === null) {
    caveats.push("Available machine capacity is not recorded, so opportunity cost of the spindle time is not included.");
  } else {
    // This read
    //   makeCost.quantity * (makeCost.machineCost / Math.max(makeCost.machineCost, 1))
    // which for any machine cost at or above $1 collapses to the quantity
    // itself. The lot's spindle demand was therefore the PART COUNT treated
    // as hours: 100 parts at 12 minutes each is 20 spindle hours, and it
    // reported 100, so a shop with 50 hours free was told the lot displaced
    // other work. The result now carries its own cycle and setup hours.
    const hoursNeeded = makeCost.setupHours + makeCost.cycleHoursPerPart * makeCost.quantity;
    if (Number.isFinite(hoursNeeded) && hoursNeeded > capacityHoursAvailable) {
      caveats.push(
        `This lot needs ${hoursNeeded.toFixed(1)} spindle hours against ${capacityHoursAvailable.toFixed(1)} recorded available — making it in-house displaces other work.`,
      );
    }
  }
  if (externalQuotes.length === 0) {
    caveats.push("No external quotes have been entered, so BUY cannot be evaluated. CANVAS will not estimate a supplier price it has no basis for.");
  }

  const grounded = options.filter((o) => o.grounded && o.unitCost !== null);
  const best = grounded.sort((a, b) => (a.unitCost ?? Infinity) - (b.unitCost ?? Infinity))[0];

  const recommendation =
    externalQuotes.length === 0
      ? null
      : best
        ? `${best.label} at $${best.unitCost!.toFixed(2)}/part is the lowest grounded cost at quantity ${quantity}.`
        : null;

  return { quantity, options, recommendation, caveats };
}

export const DEFAULT_ASSUMPTIONS: CostAssumptions = {
  materialCostPerPound: 4.25,
  materialDensity: 0.098,
  stockVolumePerPart: 18,
  materialUtilization: 0.85,
  machineRate: 75,
  operatorRate: 38,
  operatorAttendance: 0.6,
  setupHours: 1.5,
  cycleMinutes: 12,
  toolCostPerPart: 1.4,
  inspectionMinutes: 4,
  inspectionRate: 45,
  firstArticleHours: 0.75,
  scrapRate: 0.02,
  outsideProcessPerPart: 0,
  packagingPerPart: 0.35,
  overheadRate: 0.18,
  marginRate: 0.32,
};

/**
 * Currency for display. Whole dollars once the figure is large enough that
 * cents are noise; cents below that.
 *
 * A non-finite value renders as an em dash rather than "$NaN". This function
 * is the last thing between the cost model and five pages a shop owner quotes
 * from, and a price of "$NaN" is worse than a blank because it looks like a
 * number until you read it. The second and third branches used to be
 * identical, which is what a dead ternary looks like.
 */
export const money = (v: number) => {
  if (!Number.isFinite(v)) return "—";
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  return abs >= 100 ? `${sign}$${abs.toFixed(0)}` : `${sign}$${abs.toFixed(2)}`;
};
