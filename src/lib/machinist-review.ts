import "server-only";
import type { Feature, Stock } from "./domain/features";
import type { MachineProfile, Tool, WorkholdingDevice } from "./domain/shop";
import type { MachinistPlan, PlanInput } from "./engines/machinist";
import { planAllApproaches } from "./engines/machinist";
import { generateToolpath, totalCycleTime } from "./engines/cam/engine";
import type { MachiningContext, OperationRequest, Toolpath } from "./engines/cam/types";
import { assessWorkholding, RISK_ORDER, type RiskLevel } from "./engines/workholding";
import { computeCost, type CostAssumptions } from "./engines/cost";

/**
 * Scores each machinist's plan with the same deterministic engines the rest of
 * CANVAS uses — the CAM engine for cycle time, the workholding model for risk,
 * the cost engine for money. The comparison between approaches is therefore
 * arithmetic on the actual plans, not an opinion about them, which is the only
 * reason it is worth putting in front of someone who owns the shop.
 */

export interface ScoredPlan {
  plan: MachinistPlan;
  setupCount: number;
  /** Distinct tools the plan needs. See ScoredPlanSummary.distinctTools. */
  distinctTools: number;
  operationCount: number;
  cycleMinutes: number;
  /** Worst workholding risk across the plan's setups. */
  risk: RiskLevel;
  riskDetail: string;
  unitCost: number;
  unitPrice: number;
  /** Operations the engine refused to produce motion for. */
  errors: string[];
  /** Operations with an interface but no toolpath engine in Phase 1. */
  placeholders: number;
  requiresSoftJaws: boolean;
}

export interface ReviewInput {
  stock: Stock;
  features: Feature[];
  machine: MachineProfile;
  tools: Tool[];
  workholding: WorkholdingDevice | null;
  finishedHeight: number;
  materialSfmMin: number;
  materialSfmMax: number;
  materialName: string;
  specificEnergy: number | null;
  costAssumptions: CostAssumptions;
  quantity: number;
}

/* RISK_ORDER is imported from the engine that owns RiskLevel. It used to be a
   third copy of the same table, and `safest` below takes the MINIMUM of it —
   so while UNKNOWN outranked HIGH_RISK, a plan known to be high risk was
   nominated as safer than one whose risk could not be computed. */

export function reviewApproaches(input: ReviewInput): ScoredPlan[] {
  const planInput: PlanInput = {
    stock: input.stock,
    features: input.features,
    machine: input.machine,
    tools: input.tools,
    workholding: input.workholding,
    finishedHeight: input.finishedHeight,
  };

  return planAllApproaches(planInput).map((plan) => score(plan, input));
}

function score(plan: MachinistPlan, input: ReviewInput): ScoredPlan {
  const toolpaths: Toolpath[] = [];
  const errors: string[] = [];

  for (const setup of plan.setups) {
    for (const op of setup.operations) {
      const tool = input.tools.find((t) => t.id === op.toolId);
      if (!tool) {
        errors.push(`${op.label}: no tool assigned`);
        continue;
      }
      const ctx: MachiningContext = {
        tool,
        materialSfmMin: input.materialSfmMin,
        materialSfmMax: input.materialSfmMax,
        materialName: input.materialName,
        rapidRate: input.machine.maxRapid,
        maxSpindleRPM: input.machine.maxSpindleRPM,
        maxFeed: input.machine.maxFeed,
      };
      const request: OperationRequest = {
        id: `${plan.pattern}-${setup.sequence}-${op.sequence}`,
        type: op.type,
        label: op.label,
        featureId: op.featureId,
        toolId: tool.id,
        setupId: String(setup.sequence),
        // The approach's engagement and finishing allowance are what actually
        // separate the plans once the engine gets hold of them.
        overrides: { stepover: op.stepover, stockToLeave: op.stockToLeave },
        topZ: op.topZ,
        finalZ: op.finalZ,
        clearanceZ: 0.1,
        retractZ: 1,
      };
      const feature = input.features.find((f) => f.id === op.featureId) ?? null;
      const result = generateToolpath(request, feature, ctx, input.stock);
      if (result.ok) toolpaths.push(result.toolpath);
      else errors.push(`${op.label}: ${result.error.reason}`);
    }
  }

  const cycleMinutes = totalCycleTime(toolpaths);
  const placeholders = toolpaths.filter((t) => t.isPlaceholder).length;

  /* ---- Workholding risk, per setup, worst wins ---- */

  let worst: RiskLevel = "SAFE";
  let riskDetail = "All setups assessed safe.";

  for (const setup of plan.setups) {
    const setupTools = setup.operations
      .map((o) => input.tools.find((t) => t.id === o.toolId))
      .filter((t): t is Tool => Boolean(t) && ["FLAT_END_MILL", "BULL_NOSE"].includes(t!.toolClass));
    const roughingTool = setupTools.length ? setupTools.reduce((a, b) => (a.diameter > b.diameter ? a : b)) : null;
    const heaviest = setup.operations.reduce((max, o) => Math.max(max, o.stepover), 0);

    const assessment = assessWorkholding({
      stock: input.stock,
      gripDepth: setup.gripDepth,
      gripLength: setup.gripLength,
      stockProjection: setup.stockProjection,
      parallelHeight: null,
      device: input.workholding,
      features: input.features,
      roughingTool,
      radialEngagement: roughingTool ? heaviest : null,
      axialDepthOfCut: roughingTool ? roughingTool.diameter * 0.5 : null,
      specificEnergy: input.specificEnergy,
    });

    if (RISK_ORDER[assessment.level] > RISK_ORDER[worst]) {
      worst = assessment.level;
      const factor = assessment.factors.find((f) => f.level === assessment.level);
      riskDetail = factor ? `${setup.name}: ${factor.reason}` : `${setup.name}: ${assessment.level}`;
    }
  }

  /* ---- Cost, using this plan's own cycle time and setup count ---- */

  const assumptions: CostAssumptions = {
    ...input.costAssumptions,
    cycleMinutes: cycleMinutes || input.costAssumptions.cycleMinutes,
    // Each setup is real fixturing time, and the plans differ on how many.
    setupHours: plan.setups.length * 0.75 + (plan.setups.some((s) => s.requiresSoftJaws) ? 0.5 : 0),
  };
  const cost = computeCost(input.quantity, assumptions);

  // Distinct tools, not tool changes — the two differ whenever a tool is
  // used, put away and picked up again. Named for what it counts.
  const distinctTools = new Set(
    plan.setups.flatMap((s) => s.operations.map((o) => o.toolNumber)).filter((n) => n !== null),
  ).size;

  return {
    plan,
    setupCount: plan.setups.length,
    distinctTools,
    operationCount: plan.setups.reduce((n, s) => n + s.operations.length, 0),
    cycleMinutes,
    risk: worst,
    riskDetail,
    unitCost: cost.unitCost,
    unitPrice: cost.unitPrice,
    errors,
    placeholders,
    requiresSoftJaws: plan.setups.some((s) => s.requiresSoftJaws),
  };
}

export { comparePlans, type PlanComparison } from "./plan-comparison";
