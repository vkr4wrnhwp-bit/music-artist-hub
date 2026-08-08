import "server-only";
import { db } from "./db";
import { getMachines, getMaterials, getTools, getWorkholding, getMetrology, loadRevision, getSetups, getShopSettings, parseJson } from "./data";
import type { LoadedRevision } from "./data";
import { assessWorkholding, type WorkholdingAssessment } from "./engines/workholding";
import type { JawSurface } from "./engines/holding-margin";
import type { ToolCondition } from "./engines/cutting-force";
import { evaluateReadiness, type ReadinessReport } from "./engines/readiness";
import { generateToolpath, totalCycleTime } from "./engines/cam/engine";
import type { Toolpath, ToolpathError, MachiningContext, OperationRequest } from "./engines/cam/types";
import { computeCost, quantityBreaks, DEFAULT_ASSUMPTIONS, type CostAssumptions, type CostResult } from "./engines/cost";
import { analyzeProcesses, type ProcessAnalysis } from "./engines/process-advisor";
import type { MachineProfile, Tool, WorkholdingDevice } from "./domain/shop";

/**
 * Assembles the complete manufacturing package for a revision.
 *
 * This is the composition point where geometry, shop resources and every
 * engine meet. It is deliberately one function: readiness depends on
 * workholding, workholding depends on the roughing operation, cost depends on
 * cycle time which depends on the toolpaths. Computing these separately in
 * different places is how a UI ends up showing a cost that does not match the
 * program it is sitting next to.
 */

export interface ManufacturingPackage {
  revision: LoadedRevision;
  setups: Awaited<ReturnType<typeof getSetups>>;
  machines: MachineProfile[];
  tools: Tool[];
  workholdingDevices: WorkholdingDevice[];
  assignedTools: Tool[];
  primaryMachine: MachineProfile | null;
  primaryWorkholding: WorkholdingDevice | null;
  workholdingBySetup: Record<string, WorkholdingAssessment>;
  toolpaths: Toolpath[];
  toolpathErrors: ToolpathError[];
  cycleMinutes: number;
  readiness: ReadinessReport;
  cost: CostResult;
  costAssumptions: CostAssumptions;
  breaks: CostResult[];
  process: ProcessAnalysis;
  hasInspectionPlan: boolean;
  approved: boolean;
  ncGenerated: boolean;
  simulationRun: boolean;
}

export async function buildPackage(
  organizationId: string,
  partId: string,
  revisionLabel?: string,
): Promise<ManufacturingPackage | null> {
  const revision = await loadRevision(organizationId, partId, revisionLabel);
  if (!revision) return null;

  const [setups, machines, tools, workholdingDevices, materials, metrology, shop, plan, approval, nc, sim] = await Promise.all([
    getSetups(revision.revisionId),
    getMachines(organizationId),
    getTools(organizationId),
    getWorkholding(organizationId),
    getMaterials(organizationId),
    getMetrology(organizationId),
    getShopSettings(organizationId),
    db.inspectionPlan.findFirst({ where: { partRevisionId: revision.revisionId } }),
    db.approval.findFirst({ where: { partRevisionId: revision.revisionId, revokedAt: null } }),
    db.nCProgram.findFirst({ where: { partRevisionId: revision.revisionId }, orderBy: { createdAt: "desc" } }),
    db.simulation.findFirst({ where: { setup: { partRevisionId: revision.revisionId } } }),
  ]);

  const primaryMachine = setups.find((s) => s.machine)?.machine
    ? machines.find((m) => m.id === setups.find((s) => s.machine)!.machineId) ?? null
    : machines[0] ?? null;

  const primaryWorkholding = setups.find((s) => s.workholdingId)
    ? workholdingDevices.find((w) => w.id === setups.find((s) => s.workholdingId)!.workholdingId) ?? null
    : null;

  const assignedToolIds = new Set(setups.flatMap((s) => s.operations.map((o) => o.toolId)).filter(Boolean) as string[]);
  const assignedTools = tools.filter((t) => assignedToolIds.has(t.id));

  const material = materials.find((m) => m.name === revision.intent.material.value) ?? materials[0] ?? null;

  /* ---------------- Toolpaths ---------------- */

  const toolpaths: Toolpath[] = [];
  const toolpathErrors: ToolpathError[] = [];

  if (revision.stock && primaryMachine) {
    for (const setup of setups) {
      for (const op of setup.operations) {
        const tool = tools.find((t) => t.id === op.toolId);
        if (!tool) {
          toolpathErrors.push({
            operationId: op.id,
            reason: `${op.label} has no tool assigned.`,
            recommendations: ["Assign a tool from the crib"],
          });
          continue;
        }
        const ctx: MachiningContext = {
          tool,
          materialSfmMin: material?.sfmCarbideMin ?? 300,
          materialSfmMax: material?.sfmCarbideMax ?? 800,
          materialName: material?.name ?? "Unspecified",
          rapidRate: primaryMachine.maxRapid,
          maxSpindleRPM: primaryMachine.maxSpindleRPM,
          maxFeed: primaryMachine.maxFeed,
        };
        const request: OperationRequest = {
          id: op.id,
          type: op.type as OperationRequest["type"],
          label: op.label,
          featureId: op.featureId,
          toolId: tool.id,
          setupId: setup.id,
          overrides: parseJson(op.overridesJson, {}),
          topZ: op.topZ,
          finalZ: op.finalZ,
          clearanceZ: op.clearanceZ,
          retractZ: op.retractZ,
        };
        const feature = revision.features.find((f) => f.id === op.featureId) ?? null;
        const result = generateToolpath(request, feature, ctx, revision.stock);
        if (result.ok) toolpaths.push(result.toolpath);
        else toolpathErrors.push(result.error);
      }
    }
  }

  const cycleMinutes = totalCycleTime(toolpaths);

  /* ---------------- Workholding, per setup ---------------- */

  const workholdingBySetup: Record<string, WorkholdingAssessment> = {};
  for (const setup of setups) {
    const device = workholdingDevices.find((w) => w.id === setup.workholdingId) ?? null;
    // The grip assessment is about resisting LATERAL load, so the tool that
    // drives it is the largest peripheral cutter — an end mill pushing sideways
    // against the jaws. A face mill loads the part down into the vise and is
    // deliberately excluded: sizing grip off a 2" face mill would flag every
    // facing setup as high risk for a load the jaws never see.
    const setupTools = setup.operations
      .map((o) => tools.find((t) => t.id === o.toolId))
      .filter((t): t is Tool => Boolean(t) && ["FLAT_END_MILL", "BULL_NOSE"].includes(t!.toolClass));
    const roughingTool = setupTools.length ? setupTools.reduce((a, b) => (a.diameter > b.diameter ? a : b)) : null;

    workholdingBySetup[setup.id] = assessWorkholding({
      stock: revision.stock ?? { form: "RECTANGULAR", x: 0, y: 0, z: 0, material: "" },
      gripDepth: setup.gripDepth,
      gripLength: setup.gripLength,
      stockProjection: setup.stockProjection,
      parallelHeight: setup.parallelHeight,
      device,
      features: revision.features,
      roughingTool,
      radialEngagement: roughingTool ? 0.45 : null,
      axialDepthOfCut: roughingTool ? roughingTool.diameter * 0.5 : null,
      specificEnergy: material?.specificEnergy ?? null,
      materialFamily: material?.family,
      clampForce: setup.clampForce ?? device?.clampForce ?? null,
      jawSurface: (setup.jawSurface as JawSurface | null) ?? "UNKNOWN",
      hasPositiveStop: setup.hasPositiveStop || setup.jaws.length > 0,
      toolCondition: (roughingTool?.condition as ToolCondition | undefined) ?? "UNKNOWN",
      loadDirection: setup.loadDirection ?? undefined,
      operationLabel: setup.operations.find((o) => o.type.includes("ROUGH"))?.label ?? undefined,
    });
  }

  const worstAssessment =
    Object.values(workholdingBySetup).sort(
      (a, b) => rank(b.level) - rank(a.level),
    )[0] ?? null;

  /* ---------------- Readiness ---------------- */

  const instruments = metrology.map((d) => ({
    id: d.id,
    deviceType: d.deviceType as string,
    description: d.description,
    resolution: d.resolution,
    uncertainty: d.uncertainty,
    rangeMin: d.rangeMin ?? null,
    rangeMax: d.rangeMax ?? null,
    calibrated: d.calibrated,
  }));

  const readiness = evaluateReadiness({
    intent: revision.intent,
    stock: revision.stock,
    features: revision.features,
    machine: primaryMachine,
    tools: assignedTools,
    workholding: primaryWorkholding,
    workholdingAssessment: worstAssessment,
    hasInspectionPlan: Boolean(plan),
    instruments,
    simulationRun: Boolean(sim),
    ncGenerated: Boolean(nc),
    operatorApproved: Boolean(approval),
  });

  /* ---------------- Cost ---------------- */

  const stockVolume = revision.stock ? revision.stock.x * revision.stock.y * revision.stock.z : DEFAULT_ASSUMPTIONS.stockVolumePerPart;
  const toolCostPerPart = toolpaths.reduce((sum, tp) => {
    const tool = tools.find((t) => t.id === tp.toolId);
    const row = setups.flatMap((s) => s.operations).find((o) => o.id === tp.operationId);
    if (!tool || !row) return sum;
    // Tool cost is consumed life: minutes in cut over expected life.
    const dbTool = row.tool;
    const life = dbTool?.expectedLifeMinutes ?? 240;
    const cost = dbTool?.costPerTool ?? 0;
    return sum + (tp.cycleTimeMinutes / Math.max(life, 1)) * cost;
  }, 0);

  const costAssumptions: CostAssumptions = {
    ...DEFAULT_ASSUMPTIONS,
    materialCostPerPound: material?.costPerPound ?? DEFAULT_ASSUMPTIONS.materialCostPerPound,
    materialDensity: material?.density ?? DEFAULT_ASSUMPTIONS.materialDensity,
    stockVolumePerPart: stockVolume,
    machineRate: shop.machineRate,
    operatorRate: shop.operatorRate,
    inspectionRate: shop.inspectionRate,
    overheadRate: shop.overheadRate,
    marginRate: shop.marginRate,
    cycleMinutes: cycleMinutes || DEFAULT_ASSUMPTIONS.cycleMinutes,
    setupHours: setups.length * 0.75 || DEFAULT_ASSUMPTIONS.setupHours,
    toolCostPerPart: Number(toolCostPerPart.toFixed(3)) || DEFAULT_ASSUMPTIONS.toolCostPerPart,
  };

  const quantity = revision.intent.quantity.value ?? 1;
  const cost = computeCost(quantity, costAssumptions);
  const breaks = quantityBreaks(costAssumptions);

  /* ---------------- Process advisor ---------------- */

  const process = analyzeProcesses({
    intent: revision.intent,
    stock: revision.stock,
    features: revision.features,
    finishedVolume: null,
    machinedUnitCost: cost.unitCost,
  });

  return {
    revision,
    setups,
    machines,
    tools,
    workholdingDevices,
    assignedTools,
    primaryMachine,
    primaryWorkholding,
    workholdingBySetup,
    toolpaths,
    toolpathErrors,
    cycleMinutes,
    readiness,
    cost,
    costAssumptions,
    breaks,
    process,
    hasInspectionPlan: Boolean(plan),
    approved: Boolean(approval),
    ncGenerated: Boolean(nc),
    simulationRun: Boolean(sim),
  };
}

const rank = (level: string) =>
  ({ SAFE: 0, LIKELY_SAFE: 1, REVIEW: 2, HIGH_RISK: 3, UNKNOWN: 4 })[level] ?? 0;
