import type { Feature, Stock } from "@/lib/domain/features";
import type { JawBlank, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import {
  estimateCuttingForce as runCuttingModel,
  type CuttingForceEstimate,
  type ToolCondition,
} from "./cutting-force";
import { assessHoldingMargin, type HoldingMargin, type JawSurface } from "./holding-margin";

/**
 * WORKHOLDING INTELLIGENCE
 *
 * This engine is deliberately conservative and deliberately explicit. It does
 * not return a number pretending to be a safety factor. It returns a rating,
 * the factors that produced it, and what the operator can do about it — and it
 * returns UNKNOWN loudly whenever an input it needs is missing, rather than
 * substituting a default and quietly implying confidence.
 *
 * The cutting-force model here is a simplified specific-energy estimate. It is
 * adequate for ranking setups against each other; it is NOT a substitute for
 * engineering judgement, and every consumer of this module labels it as a
 * CANVAS model estimate. See /docs/MANUFACTURING_SAFETY.md.
 */

export const RISK_LEVELS = ["SAFE", "LIKELY_SAFE", "REVIEW", "HIGH_RISK", "UNKNOWN"] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

/**
 * Severity order. HIGH_RISK is the top, and that is the whole point.
 *
 * This used to rank UNKNOWN above HIGH_RISK, and the effect was to hide a
 * definite finding behind an absent one. `worst()` collapses a setup's
 * factors to a single level, so a setup with a real high-risk factor AND one
 * unknown reported UNKNOWN — which readiness maps to MISSING rather than
 * FAIL, and which the setups page and the operation runway both print as
 * "Unknown". A machinist reading UNKNOWN goes to fill in missing data; one
 * reading HIGH RISK fixes the setup. Those are different actions, and the
 * more urgent one was being suppressed.
 *
 * It was worse in machinist-review.ts, which picks the "safest" plan by the
 * MINIMUM of this order: with UNKNOWN on top, a plan known to be high risk
 * out-ranked a plan whose risk could not be computed, so CANVAS would
 * nominate the known-dangerous one as safest.
 *
 * Only one pair changes: (UNKNOWN, HIGH_RISK). Everything else keeps its
 * relative order, so nothing is weakened — the single affected case moves
 * from MISSING to FAIL, which is stricter.
 *
 * This is also the ordering readiness.ts already uses for the same idea, and
 * it now lives in one place. It was copy-pasted into three files, which is a
 * poor way to keep a safety constant.
 */
export const RISK_ORDER: Record<RiskLevel, number> = {
  SAFE: 0,
  LIKELY_SAFE: 1,
  REVIEW: 2,
  UNKNOWN: 3,
  HIGH_RISK: 4,
};

/** The worst of several risk levels. Max over RISK_ORDER, never an average. */
export function worstRisk(levels: RiskLevel[]): RiskLevel {
  return levels.reduce<RiskLevel>((acc, l) => (RISK_ORDER[l] > RISK_ORDER[acc] ? l : acc), "SAFE");
}

export const RISK_LABEL: Record<RiskLevel, string> = {
  SAFE: "Safe",
  LIKELY_SAFE: "Likely safe",
  REVIEW: "Review",
  HIGH_RISK: "High risk",
  UNKNOWN: "Unknown",
};

export interface RiskFactor {
  id: string;
  label: string;
  level: RiskLevel;
  /** What the engine actually observed. */
  observed: string;
  /** What the engine wanted to see. */
  expected?: string;
  reason: string;
  suggestions: string[];
}

export interface WorkholdingAssessment {
  level: RiskLevel;
  factors: RiskFactor[];
  /** Inputs the engine needed and did not have. */
  missingInputs: string[];
  gripDepth: number | null;
  gripLength: number | null;
  engagementPercent: number | null;
  stockProjection: number | null;
  estimatedCuttingForce: number | null;
  /** Full traceable output of the cutting model, for "show calculation". */
  forceEstimate: CuttingForceEstimate;
  /** Force-based holding margin. Null when the setup cannot support one. */
  holdingMargin: HoldingMargin | null;
}

export interface SetupContext {
  stock: Stock;
  /** Amount of stock held below the top of the jaws. */
  gripDepth: number | null;
  /** Length of jaw contact along X. */
  gripLength: number | null;
  /** Height of the part standing proud of the jaws. */
  stockProjection: number | null;
  parallelHeight: number | null;
  device: WorkholdingDevice | null;
  features: Feature[];
  /** Heaviest roughing tool in the setup, if operations are planned. */
  roughingTool: Tool | null;
  /** Radial engagement of the heaviest roughing pass, as a fraction of D. */
  radialEngagement: number | null;
  axialDepthOfCut: number | null;
  /** Material specific cutting energy, hp/in³/min. Aluminium ≈ 0.3, steel ≈ 1.0. */
  specificEnergy: number | null;
  materialFamily?: string;

  /* ---- Phase 2: inputs the force-based holding model needs ---- */

  /** Clamping force the vise applies, lbf. Falls back to the device record. */
  clampForce?: number | null;
  jawSurface?: JawSurface;
  /** Condition of the roughing tool — a dull tool pulls harder. */
  toolCondition?: ToolCondition;
  /** True when the part seats against a machined step or fixed stop. */
  hasPositiveStop?: boolean;
  /** Direction the governing cut pushes the part, e.g. "+X". */
  loadDirection?: string;
  operationLabel?: string;
}

const worst = worstRisk;

/**
 * Minimum grip depth recommendation. Scales with the cutting load rather than
 * being a fixed rule of thumb, because "0.125 is fine" is exactly the kind of
 * folk wisdom that produces a part in the chip pan.
 */
export function recommendedGripDepth(ctx: SetupContext): number | null {
  if (!ctx.roughingTool) return null;
  const base = Math.max(0.125, ctx.roughingTool.diameter * 0.25);
  const force = estimateCuttingForce(ctx);
  if (force === null) return base;
  // Above roughly 150 lbf of lateral load, ask for meaningfully more grip.
  const loadFactor = 1 + Math.max(0, (force - 150) / 300);
  return Number((base * loadFactor).toFixed(3));
}

/**
 * Runs the cutting model against a setup. The arithmetic lives in
 * ./cutting-force so there is exactly one force model in CANVAS and every
 * consumer sees the same inputs, assumptions and uncertainty band.
 */
export function cuttingForceFor(ctx: SetupContext): CuttingForceEstimate {
  const t = ctx.roughingTool;
  const sfm = t ? (t.sfmMin + t.sfmMax) / 2 : null;
  const rpm = t && sfm ? Math.min(t.maxRPM, (sfm * 12) / (Math.PI * t.diameter)) : null;
  return runCuttingModel({
    materialFamily: ctx.materialFamily ?? null,
    toolDiameter: t?.diameter ?? null,
    flutes: t?.flutes ?? null,
    axialDepth: ctx.axialDepthOfCut,
    radialWidth: t && ctx.radialEngagement != null ? ctx.radialEngagement * t.diameter : null,
    chipload: t ? (t.chiploadMin + t.chiploadMax) / 2 : null,
    rpm,
    toolCondition: ctx.toolCondition ?? t?.condition ?? "UNKNOWN",
    helixAngle: t?.helixAngle ?? null,
  });
}

/**
 * Tangential cutting force, lbf, or null when the model declined to run.
 * Retained as a convenience for callers that only want the headline number;
 * anything showing the figure to an operator should use cuttingForceFor() and
 * display the method and assumptions alongside it.
 */
export function estimateCuttingForce(ctx: SetupContext): number | null {
  return cuttingForceFor(ctx).tangential;
}

export function assessWorkholding(ctx: SetupContext): WorkholdingAssessment {
  const factors: RiskFactor[] = [];
  const missing: string[] = [];

  if (!ctx.device) missing.push("Workholding device not selected");
  if (ctx.gripDepth == null) missing.push("Grip depth not defined");
  if (ctx.gripLength == null) missing.push("Grip length not defined");
  if (!ctx.roughingTool) missing.push("No roughing tool assigned — cutting load unknown");
  if (ctx.specificEnergy == null) missing.push("Material specific cutting energy unknown");

  const forceEstimate = cuttingForceFor(ctx);
  const force = forceEstimate.tangential;
  const recommended = recommendedGripDepth(ctx);

  /* ---- Holding margin ---- */

  // The force-based model is the real answer when the inputs exist. Grip depth
  // on its own is a proxy, and a poor one: it is the ratio of applied load to
  // resisting load that decides whether a part stays in the vise.
  const clampForce = ctx.clampForce ?? ctx.device?.clampForce ?? null;
  const margin = assessHoldingMargin({
    clampForce,
    jawSurface: ctx.jawSurface ?? "UNKNOWN",
    gripDepth: ctx.gripDepth,
    gripLength: ctx.gripLength,
    jawHeight: ctx.device?.jawHeight ?? null,
    hasPositiveStop: ctx.hasPositiveStop ?? false,
    force: forceEstimate,
    loadDirection: ctx.loadDirection,
    operationLabel: ctx.operationLabel,
    // The cut happens at the top of the projecting stock, which is the worst
    // lever arm available in the setup.
    cutHeightAboveJaws: ctx.stockProjection,
  });

  if (margin.verdict !== "INDETERMINATE") {
    const level: RiskLevel =
      margin.verdict === "ADEQUATE" ? "SAFE" : margin.verdict === "MARGINAL" ? "REVIEW" : "HIGH_RISK";
    factors.push({
      id: "holding-margin",
      label: "Holding margin",
      level,
      observed: `${margin.margin?.toFixed(2)}× — ${margin.resistingForce} lbf resisting against ${margin.appliedLoad} lbf applied at peak`,
      expected: "≥ 2.00×",
      reason:
        margin.primaryRisk ??
        "Clamping friction and any positive stop exceed the peak lateral load of the governing cut by the target factor.",
      suggestions: margin.recommendations,
    });
  } else if (clampForce == null) {
    missing.push(
      "Clamping force not recorded for this vise — the holding margin cannot be calculated, only approximated by grip depth",
    );
  }

  /* ---- Grip depth ---- */
  if (ctx.gripDepth == null || recommended == null) {
    factors.push({
      id: "grip-depth",
      label: "Grip depth",
      level: "UNKNOWN",
      observed: ctx.gripDepth == null ? "Not defined" : `${ctx.gripDepth.toFixed(3)}"`,
      reason:
        "Grip depth cannot be evaluated until both the setup geometry and the roughing load are defined.",
      suggestions: ["Define stock position in the vise", "Assign a roughing operation"],
    });
  } else {
    const ratio = ctx.gripDepth / recommended;
    const heuristic: RiskLevel =
      ratio >= 1.25 ? "SAFE" : ratio >= 1.0 ? "LIKELY_SAFE" : ratio >= 0.75 ? "REVIEW" : "HIGH_RISK";
    // Grip depth is a rule of thumb standing in for a force balance. Once the
    // force balance itself is available it governs, and the rule of thumb is
    // demoted to advice — otherwise a setup the real model clears would still
    // be failed by a proxy for it.
    const governed = margin.verdict !== "INDETERMINATE";
    const level: RiskLevel = governed
      ? heuristic === "HIGH_RISK"
        ? "REVIEW"
        : heuristic
      : heuristic;
    factors.push({
      id: "grip-depth",
      label: "Grip depth",
      level,
      observed: `${ctx.gripDepth.toFixed(3)}"`,
      expected: `≥ ${recommended.toFixed(3)}"`,
      reason:
        level === "SAFE" || level === "LIKELY_SAFE"
          ? "Jaw contact is sufficient for the estimated roughing load."
          : `Roughing load is applied normal to a limited jaw contact area${
              force ? ` (estimated ${force} lbf lateral)` : ""
            }. The part may lift or shift under interrupted cuts.`,
      suggestions:
        level === "SAFE" || level === "LIKELY_SAFE"
          ? []
          : [
              "Increase grip by using taller stock or lower parallels",
              "Reduce radial engagement on roughing passes",
              "Generate soft jaws with a machined seat",
              "Move to a dovetail fixture for the second operation",
            ],
    });
  }

  /* ---- Grip length / engagement ---- */
  let engagement: number | null = null;
  if (ctx.gripLength != null && ctx.device) {
    engagement = Math.min(1, ctx.gripLength / ctx.device.jawWidth);
    const level: RiskLevel =
      engagement >= 0.75 ? "SAFE" : engagement >= 0.5 ? "LIKELY_SAFE" : "REVIEW";
    factors.push({
      id: "engagement",
      label: "Jaw engagement",
      level,
      observed: `${(engagement * 100).toFixed(0)}% of ${ctx.device.jawWidth.toFixed(2)}" jaw width`,
      expected: "≥ 75%",
      reason:
        level === "SAFE"
          ? "Clamping load is well distributed across the jaw face."
          : "Limited jaw contact concentrates clamping load and reduces resistance to rotation about Z.",
      suggestions:
        level === "SAFE" ? [] : ["Use narrower jaws sized to the part", "Add a fixed stop against rotation"],
    });
  }

  /* ---- Projection / rigidity ---- */
  if (ctx.stockProjection != null && ctx.gripDepth != null && ctx.gripDepth > 0) {
    const ratio = ctx.stockProjection / ctx.gripDepth;
    const level: RiskLevel = ratio <= 1.5 ? "SAFE" : ratio <= 3 ? "REVIEW" : "HIGH_RISK";
    factors.push({
      id: "projection",
      label: "Stock projection",
      level,
      observed: `${ctx.stockProjection.toFixed(3)}" proud of jaws (${ratio.toFixed(1)}:1 vs grip)`,
      expected: "≤ 1.5:1 projection to grip",
      reason:
        level === "SAFE"
          ? "Workpiece is well supported relative to the cut height."
          : "A long unsupported projection acts as a cantilever and is a common source of chatter and taper.",
      suggestions:
        level === "SAFE"
          ? []
          : [
              "Reduce projection by repositioning in the vise",
              "Support the free end with a toe clamp or riser",
              "Take lighter finishing passes on the upper region",
            ],
    });
  }

  /* ---- Thin wall deformation ---- */
  const thinWall = detectThinWalls(ctx.features, ctx.stock);
  if (thinWall) {
    factors.push({
      id: "thin-wall",
      label: "Thin wall deformation",
      level: "REVIEW",
      observed: thinWall,
      reason:
        "Direct jaw pressure on a thin section can deform the part while clamped, so it measures correct in the vise and springs out of tolerance when released.",
      suggestions: [
        "Clamp on a sacrificial or thicker region",
        "Reduce clamping torque and add a locating stop",
        "Machine soft jaws that support the full wall profile",
      ],
    });
  }

  /* ---- Tool and holder clearance ---- */
  if (ctx.device && ctx.roughingTool && ctx.stockProjection != null) {
    const holderClear = ctx.stockProjection - ctx.roughingTool.stickout;
    if (holderClear > 0) {
      factors.push({
        id: "holder-clearance",
        label: "Holder clearance",
        level: "HIGH_RISK",
        observed: `Tool stickout ${ctx.roughingTool.stickout.toFixed(2)}" vs ${ctx.stockProjection.toFixed(2)}" of cut depth below the holder`,
        expected: `Stickout ≥ ${(ctx.stockProjection + 0.1).toFixed(2)}"`,
        reason: "The holder body will contact the workpiece or jaws before the tool reaches depth.",
        suggestions: [
          "Increase tool stickout",
          "Use a longer-reach or necked tool",
          "Split the cut across two setups",
        ],
      });
    }
  }

  /* ---- Datum and probe access ---- */
  if (ctx.device && ctx.gripDepth != null) {
    const datumFeatures = ctx.features.filter((f) => f.functionalRole === "DATUM_FACE");
    if (datumFeatures.length === 0) {
      factors.push({
        id: "datum",
        label: "Datum accessibility",
        level: "REVIEW",
        observed: "No feature is designated as a datum face",
        reason:
          "Without an explicit datum, work offsets and inspection results cannot be traced to the same reference.",
        suggestions: ["Assign a datum face on the part", "Define the work offset origin explicitly"],
      });
    }
  }

  const level: RiskLevel = missing.length > 0 && factors.every((f) => f.level === "UNKNOWN")
    ? "UNKNOWN"
    : worst(factors.map((f) => f.level));

  return {
    level,
    factors,
    missingInputs: missing,
    gripDepth: ctx.gripDepth,
    gripLength: ctx.gripLength,
    engagementPercent: engagement === null ? null : Number((engagement * 100).toFixed(0)),
    stockProjection: ctx.stockProjection,
    estimatedCuttingForce: force,
    forceEstimate,
    holdingMargin: margin.verdict === "INDETERMINATE" ? null : margin,
  };
}

function detectThinWalls(features: Feature[], stock: Stock): string | null {
  for (const f of features) {
    if (f.kind === "RECT_POCKET") {
      const wallX = (stock.x - f.width) / 2;
      const wallY = (stock.y - f.length) / 2;
      const thinnest = Math.min(wallX, wallY);
      if (thinnest > 0 && thinnest < f.depth / 4) {
        return `${thinnest.toFixed(3)}" wall beside a ${f.depth.toFixed(3)}" deep pocket (${f.label})`;
      }
    }
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* SOFT JAW GENERATOR                                                  */
/* ------------------------------------------------------------------ */

export interface SoftJawRequest {
  device: WorkholdingDevice;
  blank: JawBlank;
  /** Finished part footprint the jaws must seat. */
  partWidth: number;
  partLength: number;
  partHeight: number;
  /** Desired depth of the machined step that captures the part. */
  desiredGrip: number;
  /** Extra material left around the part profile, per side. */
  jawAllowance: number;
  /** Clearance below the part so it seats on the step, not the pocket floor. */
  clearance: number;
  /** Whether a fixed stop is machined into one jaw for repeatability. */
  includeStop: boolean;
  clampingDirection: "X" | "Y";
  cornerRadius: number;
}

export interface SoftJawStep {
  index: number;
  title: string;
  detail: string;
}

export interface JawGeometry {
  side: "LEFT" | "RIGHT";
  blankWidth: number;
  blankHeight: number;
  blankThickness: number;
  /** Machined step that the part sits on. */
  stepDepth: number;
  stepHeight: number;
  /** Profile pocket cut into the jaw face. */
  seatWidth: number;
  seatDepth: number;
  seatCornerRadius: number;
  stopLocation: number | null;
  reliefRadius: number;
}

export interface SoftJawResult {
  ok: boolean;
  errors: string[];
  warnings: string[];
  left: JawGeometry | null;
  right: JawGeometry | null;
  /** Grip actually achieved by this jaw design. */
  achievedGrip: number;
  process: SoftJawStep[];
  /** Operations the jaw machining itself requires. */
  jawOperations: { operation: string; tool: string; note: string }[];
}

/**
 * Generates a conceptual soft jaw pair. Geometry is parametric and simplified —
 * a rectangular seat with a corner relief — but the data model carries every
 * field a full profile generator will need, so the toolpath side can be swapped
 * without changing callers.
 */
export function generateSoftJaws(req: SoftJawRequest): SoftJawResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  const across = req.clampingDirection === "X" ? req.partWidth : req.partLength;
  const along = req.clampingDirection === "X" ? req.partLength : req.partWidth;

  if (req.desiredGrip <= 0) errors.push("Desired grip must be greater than zero");
  if (req.desiredGrip >= req.partHeight)
    errors.push(
      `Desired grip ${req.desiredGrip.toFixed(3)}" leaves no material above the jaws (part is ${req.partHeight.toFixed(3)}" tall)`,
    );
  if (req.desiredGrip > req.blank.height)
    errors.push(`Desired grip exceeds the ${req.blank.height.toFixed(2)}" jaw blank height`);
  if (along > req.blank.width)
    warnings.push(
      `Part is ${along.toFixed(2)}" along the jaw but the blank is only ${req.blank.width.toFixed(2)}" wide — the part will overhang the jaw ends`,
    );
  if (across > req.device.maxOpening)
    errors.push(
      `Part width ${across.toFixed(2)}" exceeds the ${req.device.maxOpening.toFixed(2)}" maximum vise opening`,
    );

  // Corner relief must be at least the seat corner radius so the part seats
  // flat instead of riding on an un-machined corner.
  const reliefRadius = Math.max(req.cornerRadius + 0.03, 0.09);

  const seatWidth = along + 2 * req.jawAllowance;
  const stepDepth = req.desiredGrip;

  const geom = (side: "LEFT" | "RIGHT"): JawGeometry => ({
    side,
    blankWidth: req.blank.width,
    blankHeight: req.blank.height,
    blankThickness: req.blank.thickness,
    stepDepth,
    stepHeight: req.blank.height - stepDepth,
    seatWidth,
    seatDepth: Math.max(0.05, req.blank.thickness / 3),
    seatCornerRadius: reliefRadius,
    stopLocation: req.includeStop && side === "LEFT" ? -seatWidth / 2 : null,
    reliefRadius,
  });

  const ok = errors.length === 0;

  const process: SoftJawStep[] = [
    { index: 1, title: "Install jaw blanks", detail: `Mount ${req.blank.material.replace(/_/g, " ").toLowerCase()} blanks on the ${req.device.description}. Torque to the vise manufacturer's specification.` },
    { index: 2, title: "Establish zero", detail: "Indicate the fixed jaw and set the work offset at the vise centerline, top of jaws." },
    { index: 3, title: "Face jaw blanks", detail: "Clamp a spacer between the jaws and face both blanks in one pass so the faces are coplanar and square to the table." },
    { index: 4, title: "Machine the seat", detail: `Cut the ${seatWidth.toFixed(3)}" wide seat, ${stepDepth.toFixed(3)}" step with R${reliefRadius.toFixed(3)} corner relief.` },
    { index: 5, title: "Deburr", detail: "Break all edges on the seat and step. A burr on the seat is the most common cause of a part sitting proud." },
    { index: 6, title: "Load component", detail: `Seat the part on the ${stepDepth.toFixed(3)}" step with ${req.clearance.toFixed(3)}" clearance below.` },
    { index: 7, title: "Probe part", detail: "Probe the part to confirm position before cutting. Do not rely on jaw geometry alone for the work offset." },
    { index: 8, title: "Run job", detail: "Run the operation. Re-verify the first article before continuing the lot." },
  ];

  const jawOperations = [
    { operation: "Face", tool: "T1 — 2\" face mill", note: "Both jaws clamped on a spacer, single pass" },
    { operation: "2D Pocket", tool: `T3 — 3/8" flat end mill`, note: `Seat pocket, ${stepDepth.toFixed(3)}" deep` },
    { operation: "2D Contour", tool: `T4 — 1/4" flat end mill`, note: `R${reliefRadius.toFixed(3)} corner relief` },
    { operation: "Chamfer", tool: "T7 — chamfer mill", note: "0.010 × 45° break on seat edges" },
  ];

  return {
    ok,
    errors,
    warnings,
    left: ok ? geom("LEFT") : null,
    right: ok ? geom("RIGHT") : null,
    achievedGrip: ok ? stepDepth : 0,
    process,
    jawOperations,
  };
}
