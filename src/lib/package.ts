import "server-only";
import { db } from "./db";
import { getMachines, getMaterials, getTools, getWorkholding, getMetrology, loadRevision, getSetups, getShopSettings, parseJson } from "./data";
import type { LoadedRevision } from "./data";
import { RISK_ORDER } from "./engines/workholding";
import { assessWorkholding, type WorkholdingAssessment } from "./engines/workholding";
import type { JawSurface } from "./engines/holding-margin";
import type { ToolCondition } from "./engines/cutting-force";
import { evaluateReadiness, type ReadinessReport } from "./engines/readiness";
import { generateToolpath, totalCycleTime } from "./engines/cam/engine";
import type { Toolpath, ToolpathError, MachiningContext, OperationRequest } from "./engines/cam/types";
import { computeCost, quantityBreaks, DEFAULT_ASSUMPTIONS, type CostAssumptions, type CostResult } from "./engines/cost";
import { selectPrimaryMachine, selectMaterial } from "./package-selectors";
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

  /*
   * The machine this part is actually assigned to, or null.
   *
   * This used to fall back to machines[0] when no setup named one, so the
   * machine-envelope gate validated against whichever machine happened to be
   * first in the shop's list and every toolpath took its spindle and feed
   * limits from it. readiness.ts already handles a null machine correctly —
   * "No machine is selected, so travel and spindle limits cannot be
   * validated" — and the fallback was talking over it.
   */
  const primaryMachine = selectPrimaryMachine(setups, machines);

  const primaryWorkholding = setups.find((s) => s.workholdingId)
    ? workholdingDevices.find((w) => w.id === setups.find((s) => s.workholdingId)!.workholdingId) ?? null
    : null;

  const assignedToolIds = new Set(setups.flatMap((s) => s.operations.map((o) => o.toolId)).filter(Boolean) as string[]);
  const assignedTools = tools.filter((t) => assignedToolIds.has(t.id));

  /*
   * The part's material, or null when the shop has no record of it.
   *
   * This used to fall back to materials[0]. Every consumer below is written
   * honestly — `material?.specificEnergy ?? null`, `material?.family` — and
   * the fallback defeated all of it by making `material` non-null with the
   * WRONG material. A part specified in Titanium 6Al-4V, with no titanium in
   * the shop's table, was force-modelled at aluminium's specific energy of
   * 0.3 against titanium's 1.6: a five-fold understatement of cutting load,
   * feeding the holding margin that decides whether the part stays in the
   * vise.
   *
   * With null, cutting force returns ok:false and names the missing
   * coefficients, the holding margin goes INDETERMINATE, and the workholding
   * gate reports what it does not know. The cost engine's defaults are a
   * different thing and stay: they are declared in the assumptions drawer for
   * the user to see and change, which is what that engine is built around.
   */
  const material = selectMaterial(materials, revision.intent.material.value);

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

  /*
   * Tool loading, per setup.
   *
   * Per setup because Setup.machineId is per setup — a part can be roughed on
   * one machine and finished on another, and checking every tool against one
   * "primary" machine reports correctly-loaded tools as missing the moment a
   * part spans two. Note this deliberately reads setup.machineId rather than
   * primaryMachine, which falls back to machines[0] when nothing is assigned
   * and would have the gate checking tooling against a machine nobody chose.
   *
   * Occupancy is queried, never derived: a tool is in a pocket because
   * somebody recorded putting it there. No rows means the changer has not
   * been mapped, which the gate treats as unknown rather than as absent.
   */
  const carouselMachineIds = [...new Set(setups.map((s) => s.machineId).filter(Boolean) as string[])];
  const loadedRows = carouselMachineIds.length
    ? await db.tool.findMany({
        where: { organizationId, machineId: { in: carouselMachineIds }, pocket: { not: null } },
        select: { toolNumber: true, machineId: true },
      })
    : [];
  const loadedByMachineId = new Map<string, number[]>();
  for (const r of loadedRows) {
    if (!r.machineId) continue;
    loadedByMachineId.set(r.machineId, [...(loadedByMachineId.get(r.machineId) ?? []), r.toolNumber]);
  }

  const toolLoading = setups.map((s) => {
    const m = s.machineId ? machines.find((x) => x.id === s.machineId) ?? null : null;
    const required = [
      ...new Set(
        s.operations
          .map((o) => tools.find((t) => t.id === o.toolId)?.toolNumber)
          .filter((n): n is number => typeof n === "number"),
      ),
    ];
    return {
      setupName: s.name,
      machineLabel: m ? `${m.manufacturer} ${m.model}` : null,
      requiredToolNumbers: required,
      loadedToolNumbers: s.machineId ? loadedByMachineId.get(s.machineId) ?? null : null,
    };
  });

  const readiness = evaluateReadiness({
    intent: revision.intent,
    stock: revision.stock,
    features: revision.features,
    machine: primaryMachine,
    tools: assignedTools,
    workholding: primaryWorkholding,
    workholdingAssessment: worstAssessment,
    hasInspectionPlan: Boolean(plan),
    toolLoading,
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

// One ordering, defined in the engine that owns the vocabulary. This was an
// inline copy and it disagreed with nothing only by luck.
const rank = (level: string) => RISK_ORDER[level as keyof typeof RISK_ORDER] ?? 0;
