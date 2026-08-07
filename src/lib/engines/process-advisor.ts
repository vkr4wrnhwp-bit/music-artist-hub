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
    verdict: effectiveVolume !== null && effectiveVolume >= 500 ? "INVESTIGATE" : "NOT_SUITABLE",
    volumeBand: "500+ /year",
    rationale: [
      "A near-net forged or sawn blank cuts roughing time and material buy substantially while keeping wrought grain structure.",
      "Grain flow follows the part shape, which is a genuine advantage for fatigue-loaded components.",
    ],
    blockers: blockedBy.length > 0 ? ["Responsibility profile incomplete"] : [],
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
    verdict: "INVESTIGATE",
    volumeBand: "1 – 200, geometry-driven",
    rationale: [
      complex
        ? "Feature count is high enough that additive's geometric freedom may reduce setups."
        : "Geometry is prismatic and machines efficiently — additive would add cost without buying anything.",
      "Powder-bed parts still need datum creation, stress relief and CNC finishing on functional surfaces.",
    ],
    blockers: critical
      ? ["Safety-critical additive parts require qualified powder, process controls and NDT that CANVAS does not model."]
      : [],
    toolingCostOrder: null,
    leadTimeNote: "1 – 3 weeks including post-processing.",
  });

  recs.push({
    process: "HYBRID_ADDITIVE_SUBTRACTIVE",
    verdict: complex && effectiveVolume !== null && effectiveVolume < 100 ? "INVESTIGATE" : "NOT_SUITABLE",
    volumeBand: "Low volume, high complexity",
    rationale: ["Print near-net, then finish functional surfaces on the mill. Useful when the machining time is dominated by roughing."],
    blockers: [],
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

  const crossovers: { volume: number; note: string }[] = [];
  if (input.machinedUnitCost !== null) {
    crossovers.push({ volume: 500, note: "Near-net blank plus finish machining typically becomes attractive here." });
    crossovers.push({ volume: 2000, note: "Casting plus finish machining should be quoted at this point." });
    crossovers.push({ volume: 20000, note: "Dedicated tooling and a production cell change the economics entirely." });
  }

  return {
    quantity: qty,
    annualVolume: annual,
    recommendations: recs,
    headline,
    blockedBy,
    volumeCrossovers: crossovers,
  };
}

function isEssentiallyFlat(input: ProcessInput): boolean {
  if (!input.stock) return false;
  const hasDepthVariation = input.features.some(
    (f) =>
      (f.kind === "RECT_POCKET" || f.kind === "CIRC_POCKET") &&
      !("through" in f && f.through) &&
      f.depth < input.stock!.z * 0.9,
  );
  const thin = input.stock.z <= Math.min(input.stock.x, input.stock.y) * 0.2;
  return thin && !hasDepthVariation;
}
