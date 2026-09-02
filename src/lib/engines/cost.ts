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
  /**
   * Setup time, hours — amortised across the lot. Null when no setup has been
   * planned, rather than a stand-in figure.
   */
  setupHours: number | null;
  /**
   * Machining cycle, minutes per part.
   *
   * NULL WHEN NOTHING HAS DERIVED IT. This used to fall back to a 12-minute
   * default whenever the toolpath-derived figure was zero — `0 || 12` — so a
   * part whose operations could not be toolpathed was priced at twelve minutes
   * of machine time nobody calculated. The cost page printed "12.00 min ×
   * $75.00/hr" as the basis directly beneath a tile reading "CYCLE TIME 0.00
   * min FROM GENERATED TOOLPATHS", and a stored estimate froze that invented
   * number into a customer price.
   *
   * A partially-guessed number is worse than no number, because it looks
   * authoritative.
   */
  cycleMinutes: number | null;
  /** Total tooling cost consumed per part. Null when no tool life is known. */
  toolCostPerPart: number | null;
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
  /** Null when an input this line needs has not been established. */
  perPart: number | null;
  perLot: number | null;
  /** Where this number came from — or what is missing, when it is null. */
  basis: string;
}

export interface CostResult {
  quantity: number;
  lines: CostLine[];
  materialCost: number;
  /**
   * Null wherever an input was never established. Nothing here is filled in
   * with a stand-in figure: a missing input makes its own line null, and any
   * null line makes the total null, because a total that silently omits
   * machine time is a bid the shop loses money on.
   */
  machineCost: number | null;
  labourCost: number | null;
  toolingCost: number | null;
  inspectionCost: number;
  setupCostPerPart: number | null;
  outsideCost: number;
  scrapAdder: number | null;
  overhead: number | null;
  /** What it costs the shop to put the part on the bench. */
  unitCost: number | null;
  /** What the shop charges. */
  unitPrice: number | null;
  lotPrice: number | null;
  /** What has not been established, in a machinist's words. Empty when costed. */
  missingInputs: string[];
  marginDollars: number | null;
  /** Spindle hours per part, so capacity can be worked out from the result. */
  cycleHoursPerPart: number | null;
  /** Setup hours for the lot, charged once. */
  setupHours: number | null;
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

  /*
   * WHAT HAS NOT BEEN ESTABLISHED
   *
   * Each of these was previously substituted with a stand-in from
   * DEFAULT_ASSUMPTIONS whenever the derived figure came out zero, and the
   * result was presented with a basis string that read as though it had been
   * measured. Nothing is substituted now: a missing input makes its own line
   * null, and any line that is null makes the TOTAL null.
   *
   * A total that silently omits machine time is worse than no total, because a
   * quote at that price is a bid the shop loses money on.
   */
  const missingInputs: string[] = [];
  if (a.cycleMinutes == null)
    missingInputs.push(
      "Machining cycle time — no toolpath has been generated for this part, so nothing has derived how long it takes to cut.",
    );
  if (a.setupHours == null) missingInputs.push("Setup time — no setup has been planned for this part.");
  if (a.toolCostPerPart == null)
    missingInputs.push("Tooling cost — no tool with a recorded life and cost is assigned to the operations.");

  const cycleHours = a.cycleMinutes != null ? a.cycleMinutes / 60 : null;
  const machineCost = cycleHours != null ? cycleHours * a.machineRate : null;
  const labourCost = cycleHours != null ? cycleHours * a.operatorAttendance * a.operatorRate : null;

  const setupCostPerPart = a.setupHours != null ? (a.setupHours * (a.machineRate + a.operatorRate)) / quantity : null;
  const firstArticlePerPart = (a.firstArticleHours * a.inspectionRate) / quantity;
  const inspectionCost = (a.inspectionMinutes / 60) * a.inspectionRate + firstArticlePerPart;

  const base =
    machineCost == null || labourCost == null || setupCostPerPart == null || a.toolCostPerPart == null
      ? null
      : materialCost +
        machineCost +
        labourCost +
        a.toolCostPerPart +
        inspectionCost +
        setupCostPerPart +
        a.outsideProcessPerPart +
        a.packagingPerPart;

  // Scrap is charged on the base cost — a scrapped part consumed material,
  // machine time and an operator, not just material.
  const scrapAdder = base != null ? base * (a.scrapRate / Math.max(1 - a.scrapRate, 0.01)) : null;
  const overhead = base != null && scrapAdder != null ? (base + scrapAdder) * a.overheadRate : null;

  const unitCost = base != null && scrapAdder != null && overhead != null ? base + scrapAdder + overhead : null;
  const unitPrice = unitCost == null ? null : a.marginRate >= 1 ? unitCost : unitCost / (1 - a.marginRate);
  const warnings = assumptionWarnings(a);

  /** perPart × quantity, or null when the per-part figure was never established. */
  const perLot = (v: number | null) => (v == null ? null : v * quantity);

  const lines: CostLine[] = [
    { label: "Material", perPart: materialCost, perLot: perLot(materialCost), basis: `${a.stockVolumePerPart.toFixed(2)} in³ × ${a.materialDensity} lb/in³ × $${a.materialCostPerPound.toFixed(2)}/lb ÷ ${(a.materialUtilization * 100).toFixed(0)}% utilisation` },
    {
      label: "Machine time",
      perPart: machineCost,
      perLot: perLot(machineCost),
      // The basis says what is missing rather than printing a rate against a
      // cycle time nobody derived. This line read "12.00 min × $75.00/hr"
      // beneath a tile saying the cycle time was 0.00 min from toolpaths.
      basis:
        a.cycleMinutes != null
          ? `${a.cycleMinutes.toFixed(2)} min × $${a.machineRate.toFixed(2)}/hr`
          : "No cycle time — nothing has generated a toolpath for this part",
    },
    {
      label: "Operator",
      perPart: labourCost,
      perLot: perLot(labourCost),
      basis:
        a.cycleMinutes != null
          ? `${(a.operatorAttendance * 100).toFixed(0)}% attendance × $${a.operatorRate.toFixed(2)}/hr`
          : "No cycle time to attend",
    },
    {
      label: "Setup (amortised)",
      perPart: setupCostPerPart,
      perLot: a.setupHours != null ? a.setupHours * (a.machineRate + a.operatorRate) : null,
      basis: a.setupHours != null ? `${a.setupHours.toFixed(2)} hr ÷ ${quantity} parts` : "No setup planned",
    },
    {
      label: "Tooling",
      perPart: a.toolCostPerPart,
      perLot: perLot(a.toolCostPerPart),
      basis: a.toolCostPerPart != null ? "Consumed tool life per part" : "No tool with a recorded life and cost is assigned",
    },
    { label: "Inspection", perPart: inspectionCost, perLot: perLot(inspectionCost), basis: `${a.inspectionMinutes} min/part + ${a.firstArticleHours} hr FAI ÷ ${quantity}` },
    { label: "Outside processing", perPart: a.outsideProcessPerPart, perLot: perLot(a.outsideProcessPerPart), basis: "Per-part outside process cost" },
    { label: "Packaging", perPart: a.packagingPerPart, perLot: perLot(a.packagingPerPart), basis: "Per-part packaging" },
    {
      label: "Scrap allowance",
      perPart: scrapAdder,
      perLot: perLot(scrapAdder),
      basis: scrapAdder != null ? `${(a.scrapRate * 100).toFixed(1)}% expected scrap on full cost` : "No cost base to apply scrap to",
    },
    {
      label: "Overhead",
      perPart: overhead,
      perLot: perLot(overhead),
      basis: overhead != null ? `${(a.overheadRate * 100).toFixed(0)}% of cost base` : "No cost base to apply overhead to",
    },
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
    lotPrice: perLot(unitPrice),
    marginDollars: unitPrice != null && unitCost != null ? (unitPrice - unitCost) * quantity : null,
    cycleHoursPerPart: cycleHours,
    setupHours: a.setupHours,
    warnings,
    missingInputs,
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
    // Null when nothing derived a cycle or a setup. The capacity comparison is
    // then not made at all rather than made against a stand-in figure — the
    // caveat below says why, which is more use than a spindle-hour number
    // computed from an invented cycle time.
    const hoursNeeded =
      makeCost.setupHours != null && makeCost.cycleHoursPerPart != null
        ? makeCost.setupHours + makeCost.cycleHoursPerPart * makeCost.quantity
        : null;
    if (hoursNeeded == null) {
      caveats.push(
        "Spindle hours for this lot cannot be worked out — " + makeCost.missingInputs.join(" ") +
          " Capacity has not been compared.",
      );
    } else if (Number.isFinite(hoursNeeded) && hoursNeeded > capacityHoursAvailable) {
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
/**
 * A figure, or an em dash where there is no figure.
 *
 * Accepts null so a cost line that was never established renders as "—"
 * rather than as $0.00. Zero is a claim: it says this costs nothing.
 */
export const money = (v: number | null) => {
  if (v == null || !Number.isFinite(v)) return "—";
  const sign = v < 0 ? "-" : "";
  const abs = Math.abs(v);
  return abs >= 100 ? `${sign}$${abs.toFixed(0)}` : `${sign}$${abs.toFixed(2)}`;
};
