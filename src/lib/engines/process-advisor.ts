import type { PartIntent } from "@/lib/domain/part-intent";
import { isCriticalApplication } from "@/lib/domain/part-intent";
import type { Feature, Stock } from "@/lib/domain/features";

/**
 * MANUFACTURING METHOD ADVISOR
 *
 * CANVAS is allowed to say "you should not machine this". It is not allowed to
 * say it casually. This engine is rule-based and volume-driven — it reasons
 * about tooling amortisation, geometry suitability and functional
 * responsibility, and it refuses to recommend a process change when the part's
 * responsibility profile is unknown, because switching a load-bearing billet
 * part to a casting without knowing the loading case is exactly the kind of
 * advice that gets someone hurt.
 */

export const PROCESSES = [
  "CNC_BILLET",
  "TURNING",
  "FABRICATION",
  "LASER",
  "WATERJET",
  "PLASMA",
  "STAMPING",
  "FORMING",
  "HYDROFORMING",
  "CASTING",
  "FORGING",
  "EXTRUSION",
  "INJECTION_MOLDING",
  "POLYMER_ADDITIVE",
  "METAL_ADDITIVE_PBF",
  "BINDER_JET",
  "DED",
  "HYBRID_ADDITIVE_SUBTRACTIVE",
  "EDM_WIRE",
  "EDM_SINKER",
  "PURCHASE_COTS",
] as const;
export type Process = (typeof PROCESSES)[number];

export const PROCESS_LABEL: Record<Process, string> = {
  CNC_BILLET: "3-axis billet machining",
  TURNING: "Turning",
  FABRICATION: "Weldment / fabrication",
  LASER: "Laser cutting",
  WATERJET: "Waterjet cutting",
  PLASMA: "Plasma cutting",
  STAMPING: "Stamping",
  FORMING: "Sheet forming",
  HYDROFORMING: "Hydroforming",
  CASTING: "Casting + finish machining",
  FORGING: "Forging + finish machining",
  EXTRUSION: "Extrusion + cut to length",
  INJECTION_MOLDING: "Injection molding",
  POLYMER_ADDITIVE: "Polymer additive",
  METAL_ADDITIVE_PBF: "Metal powder-bed fusion",
  BINDER_JET: "Binder jetting",
  DED: "Directed energy deposition",
  HYBRID_ADDITIVE_SUBTRACTIVE: "Hybrid additive + CNC finishing",
  EDM_WIRE: "Wire EDM",
  EDM_SINKER: "Sinker EDM",
  PURCHASE_COTS: "Purchase off the shelf",
};

export interface ProcessRecommendation {
  process: Process;
  verdict: "RECOMMENDED" | "VIABLE" | "INVESTIGATE" | "NOT_SUITABLE" | "INSUFFICIENT_DATA";
  /** Volume band where this process starts to make sense. */
  volumeBand: string;
  rationale: string[];
  blockers: string[];
  /** Non-recurring tooling cost order of magnitude, if the process needs it. */
  toolingCostOrder: string | null;
  leadTimeNote: string | null;
}

export interface ProcessAnalysis {
  quantity: number | null;
  annualVolume: number | null;
  recommendations: ProcessRecommendation[];
  /** Shown prominently when CANVAS thinks machining is the wrong answer. */
  headline: string;
  /** Named information gaps that would change the answer. */
  blockedBy: string[];
  volumeCrossovers: { volume: number; note: string }[];
}

export interface ProcessInput {
  intent: PartIntent;
  stock: Stock | null;
  features: Feature[];
  /** In³ of the finished part, if known. */
  finishedVolume: number | null;
  /** Machining cost per part from the cost engine, if computed. */
  machinedUnitCost: number | null;
}

export function analyzeProcesses(input: ProcessInput): ProcessAnalysis {
  const { intent } = input;
  const qty = intent.quantity.value;
  const annual = intent.annualVolume.value;
  const critical = isCriticalApplication(intent);
  const blockedBy: string[] = [];

  if (intent.loadBearing.value === null) blockedBy.push("Load bearing status unknown");
  if (intent.failureConsequence.value === null) blockedBy.push("Failure consequence not assessed");
  if (qty === null) blockedBy.push("Quantity not specified");
  if (intent.material.value === null) blockedBy.push("Material not specified");

  const effectiveVolume = annual ?? qty ?? null;
  const recs: ProcessRecommendation[] = [];

  /**
   * A process that changes the material's properties — cast grain instead of
   * wrought, forged flow lines, fused powder — cannot be weighed against
   * billet until it is known what the part carries and what happens when it
   * fails. CASTING already honoured this and returned INSUFFICIENT_DATA;
   * FORGING and powder-bed did not, so an incomplete part sat under a
   * headline reading "CANVAS will not compare alternative processes until 2
   * outstanding inputs are resolved" with FORGING marked INVESTIGATE directly
   * beneath it. Two near-identical near-net processes answered the same
   * question differently, and the unsafe one was the one that spoke.
   *
   * Through-cutting the same wrought plate is not a property change, so
   * waterjet is not gated here — only by whether the geometry allows it.
   */
  const propertyChangeGated = blockedBy.length > 0;

  /* ---- Machining: the baseline ---- */
  const machiningRationale: string[] = [];
  if (effectiveVolume !== null && effectiveVolume <= 50) {
    machiningRationale.push("At this volume there is no tooling amortisation to beat — billet machining is almost always the lowest total cost.");
  }
  machiningRationale.push("Produces final tolerances and finish directly, with no secondary process chain.");
  if (critical) machiningRationale.push("Wrought billet gives predictable, certifiable material properties, which matters for a load-bearing part.");

  recs.push({
    process: "CNC_BILLET",
    verdict: effectiveVolume !== null && effectiveVolume > 2000 ? "VIABLE" : "RECOMMENDED",
    volumeBand: "1 – 500 typical",
    rationale: machiningRationale,
    blockers: [],
    toolingCostOrder: "Soft jaws / fixture only",
    leadTimeNote: "Days, limited by schedule rather than tooling.",
  });

  /* ---- Casting ---- */
  const castingBlockers: string[] = [];
  if (blockedBy.length > 0) {
    castingBlockers.push("Part responsibility profile is incomplete — CANVAS will not recommend a material process change without it.");
  }
  if (critical && intent.loadingType.value === null) {
    castingBlockers.push("Loading case unknown. Cast material has different fatigue behaviour to wrought and cannot be substituted blind.");
  }
  recs.push({
    process: "CASTING",
    verdict:
      castingBlockers.length > 0
        ? "INSUFFICIENT_DATA"
        : effectiveVolume !== null && effectiveVolume >= 2000
          ? "INVESTIGATE"
          : "NOT_SUITABLE",
    volumeBand: "2,000+ /year",
    rationale: [
      "Casting moves material cost and cycle time down sharply once pattern and tooling costs are amortised.",
      "Almost always still requires finish machining on bearing seats, datums and threaded features.",
    ],
    blockers: castingBlockers,
    toolingCostOrder: "$5k – $40k pattern / die",
    leadTimeNote: "8 – 16 weeks for first articles.",
  });

  /* ---- Near-net blank ---- */
  recs.push({
    process: "FORGING",
    verdict: propertyChangeGated
      ? "INSUFFICIENT_DATA"
      : effectiveVolume !== null && effectiveVolume >= 500
        ? "INVESTIGATE"
        : "NOT_SUITABLE",
    volumeBand: "500+ /year",
    rationale: [
      "A near-net forged or sawn blank cuts roughing time and material buy substantially while keeping wrought grain structure.",
      "Grain flow follows the part shape, which is a genuine advantage for fatigue-loaded components.",
    ],
    blockers: propertyChangeGated
      ? ["Responsibility profile incomplete — CANVAS will not recommend a material process change without it."]
      : [],
    toolingCostOrder: "$8k – $60k die",
    leadTimeNote: "12+ weeks for tooling.",
  });

  /* ---- Sheet / plate processes for flat parts ---- */
  const flat = isEssentiallyFlat(input);
  recs.push({
    process: "WATERJET",
    verdict: flat ? (effectiveVolume !== null && effectiveVolume >= 25 ? "VIABLE" : "INVESTIGATE") : "NOT_SUITABLE",
    volumeBand: "Any — no hard tooling",
    rationale: flat
      ? [
          "Part profile is essentially 2D through the full thickness, which waterjet cuts with no tooling cost.",
          "Bores, tapped holes and any surface with a tolerance tighter than about ±0.005 still need machining afterwards.",
        ]
      : ["Part has 3D features that a through-cut process cannot produce."],
    blockers: flat ? [] : ["Geometry is not a through-profile"],
    toolingCostOrder: null,
    leadTimeNote: "Days.",
  });

  /* ---- Additive ---- */
  const complex = input.features.length > 12;
  recs.push({
    process: "METAL_ADDITIVE_PBF",
    verdict: propertyChangeGated ? "INSUFFICIENT_DATA" : "INVESTIGATE",
    volumeBand: "1 – 200, geometry-driven",
    rationale: [
      complex
        ? "Feature count is high enough that additive's geometric freedom may reduce setups."
        : "Geometry is prismatic and machines efficiently — additive would add cost without buying anything.",
      "Powder-bed parts still need datum creation, stress relief and CNC finishing on functional surfaces.",
    ],
    blockers: [
      ...(propertyChangeGated ? ["Responsibility profile incomplete — fused powder is not wrought material and cannot be substituted blind."] : []),
      ...(critical
        ? ["Safety-critical additive parts require qualified powder, process controls and NDT that CANVAS does not model."]
        : []),
    ],
    toolingCostOrder: null,
    leadTimeNote: "1 – 3 weeks including post-processing.",
  });

  recs.push({
    process: "HYBRID_ADDITIVE_SUBTRACTIVE",
    verdict: propertyChangeGated
      ? "INSUFFICIENT_DATA"
      : complex && effectiveVolume !== null && effectiveVolume < 100
        ? "INVESTIGATE"
        : "NOT_SUITABLE",
    volumeBand: "Low volume, high complexity",
    rationale: ["Print near-net, then finish functional surfaces on the mill. Useful when the machining time is dominated by roughing."],
    blockers: propertyChangeGated
      ? ["Responsibility profile incomplete — the printed portion is not wrought material."]
      : [],
    toolingCostOrder: null,
    leadTimeNote: null,
  });

  /* ---- Buy ---- */
  recs.push({
    process: "PURCHASE_COTS",
    verdict: "INSUFFICIENT_DATA",
    volumeBand: "Any",
    rationale: [
      "If this part is a standard item — a bearing housing, a pillow block, a standard mount — buying it will beat making it at almost any volume.",
    ],
    blockers: ["No catalogue matching is connected in Phase 1."],
    toolingCostOrder: null,
    leadTimeNote: null,
  });

  /* ---- Headline ---- */
  let headline: string;
  if (blockedBy.length > 0) {
    headline = `Machining is the working assumption. CANVAS will not compare alternative processes until ${blockedBy.length} outstanding input${blockedBy.length > 1 ? "s are" : " is"} resolved.`;
  } else if (effectiveVolume !== null && effectiveVolume >= 2000) {
    headline = `At ${effectiveVolume.toLocaleString()} per year, billet machining is unlikely to be the right long-term process. Casting or a near-net blank plus finish machining should be investigated.`;
  } else if (flat && effectiveVolume !== null && effectiveVolume >= 25) {
    headline = "The outside profile is a through-cut. Buying waterjet blanks and machining only the functional features is likely cheaper than roughing from plate.";
  } else {
    headline = `At ${effectiveVolume?.toLocaleString() ?? "the stated"} volume, 3-axis billet machining is the correct process. No alternative has a favourable amortisation.`;
  }

  // These are the volumes at which each process's tooling starts to amortise
  // — general process economics, the same for every part.
  //
  // They were gated on machinedUnitCost being non-null while never reading
  // it, so a fixed list of three numbers appeared under a heading that
  // implied it had been computed against this part's machining cost. It had
  // not: the volumes are identical whether the part costs $5 or $500. A real
  // crossover is where two cost curves meet and CANVAS has no supplier
  // quotes to draw the second curve from, so the note says what these are
  // instead of implying what they are not.
  const crossovers = [
    { volume: 500, note: "Near-net blank plus finish machining typically becomes attractive here. Industry tooling-amortisation band, not computed against this part." },
    { volume: 2000, note: "Casting plus finish machining should be quoted at this point. Industry tooling-amortisation band, not computed against this part." },
    { volume: 20000, note: "Dedicated tooling and a production cell change the economics entirely. Industry tooling-amortisation band, not computed against this part." },
  ];

  return {
    quantity: qty,
    annualVolume: annual,
    recommendations: recs,
    headline,
    blockedBy,
    volumeCrossovers: crossovers,
  };
}

/**
 * A waterjet cuts all the way through, in one thickness, everywhere. So the
 * question is not whether the part is thin — it is whether anything on it
 * stops partway down.
 *
 * This used to ask that of RECT_POCKET and CIRC_POCKET only. A 0.250" plate
 * with a 0.100"-deep SLOT was therefore "essentially flat", waterjet came back
 * VIABLE, and the headline told the shop to buy waterjet blanks and machine
 * only the functional features — for a part with a blind slot a waterjet
 * cannot produce at all. The same slot as a pocket was caught correctly,
 * which is what an allow-list of feature kinds does as soon as the feature
 * list grows.
 *
 * The test is now the other way round: any feature that has a depth and does
 * not go through is depth variation, whatever it is called.
 */
function isEssentiallyFlat(input: ProcessInput): boolean {
  const stock = input.stock;
  if (!stock) return false;

  const hasDepthVariation = input.features.some((f) => {
    if ("through" in f && f.through) return false;
    if (!("depth" in f) || typeof f.depth !== "number") return false;
    // A face cut removes stock from the top rather than putting a step in the
    // profile, so it does not stop the outline being a through-cut.
    if (f.kind === "FACE") return false;
    return f.depth < stock.z * 0.9;
  });

  const thin = stock.z <= Math.min(stock.x, stock.y) * 0.2;
  return thin && !hasDepthVariation;
}
