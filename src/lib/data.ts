import "server-only";
import { db } from "./db";
import type { PartIntent } from "./domain/part-intent";
import { emptyPartIntent, reconcileIntentWithStock } from "./domain/part-intent";
import type { Feature, Stock } from "./domain/features";
import type { MachineProfile, Tool, WorkholdingDevice, MetrologyDevice, MaterialProfile } from "./domain/shop";

/**
 * Organisation-scoped data access.
 *
 * Every function here takes `organizationId` as its first argument and every
 * query filters on it. Callers get that id from the session, never from a
 * request parameter, so a crafted part id cannot reach another shop's data.
 */

const parseJson = <T,>(raw: string | null | undefined, fallback: T): T => {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
};

/* ------------------------------------------------------------------ */
/* Shop resources                                                      */
/* ------------------------------------------------------------------ */

export async function getMachines(organizationId: string): Promise<MachineProfile[]> {
  const rows = await db.machine.findMany({ where: { organizationId }, orderBy: { createdAt: "asc" } });
  return rows.map((m) => ({
    id: m.id,
    manufacturer: m.manufacturer,
    model: m.model,
    controller: m.controller as MachineProfile["controller"],
    machineType: m.machineType as MachineProfile["machineType"],
    axisCount: m.axisCount,
    travelsX: m.travelsX,
    travelsY: m.travelsY,
    travelsZ: m.travelsZ,
    tableX: m.tableX,
    tableY: m.tableY,
    maxSpindleRPM: m.maxSpindleRPM,
    maxSpindlePower: m.maxSpindlePower,
    maxSpindleTorque: m.maxSpindleTorque,
    maxFeed: m.maxFeed,
    maxRapid: m.maxRapid,
    axisAccel: m.axisAccel ?? null,
    toolChangerCapacity: m.toolChangerCapacity,
    maxToolDiameter: m.maxToolDiameter,
    maxToolLength: m.maxToolLength,
    maxToolWeight: m.maxToolWeight,
    coolantTypes: parseJson<string[]>(m.coolantTypes, []),
    throughSpindleCoolant: m.throughSpindleCoolant,
    probe: m.probe,
    toolSetter: m.toolSetter,
    fourthAxis: m.fourthAxis,
    fifthAxis: m.fifthAxis,
    supportedPostProcessor: m.supportedPostProcessor,
    isReferenceProfile: m.isReferenceProfile,
    notes: m.notes ?? undefined,
  }));
}

export async function getTools(organizationId: string): Promise<Tool[]> {
  const rows = await db.tool.findMany({
    where: { organizationId },
    orderBy: { toolNumber: "asc" },
    include: { holder: true },
  });
  return rows.map((t) => ({
    id: t.id,
    toolNumber: t.toolNumber,
    toolClass: t.toolClass as Tool["toolClass"],
    manufacturer: t.manufacturer ?? undefined,
    product: t.product ?? undefined,
    description: t.description,
    diameter: t.diameter,
    cornerRadius: t.cornerRadius,
    flutes: t.flutes,
    material: t.material as Tool["material"],
    coating: t.coating ?? undefined,
    fluteLength: t.fluteLength,
    overallLength: t.overallLength,
    stickout: t.stickout,
    holder: t.holder?.description ?? "Not assigned",
    holderNoseDiameter: t.holder?.noseDiameter ?? 0,
    holderTaperAngle: t.holder?.taperAngleDegrees,
    maxRPM: t.maxRPM,
    recommendedMaterials: parseJson<string[]>(t.recommendedMaterials, []),
    chiploadMin: t.chiploadMin,
    chiploadMax: t.chiploadMax,
    sfmMin: t.sfmMin,
    sfmMax: t.sfmMax,
    coolant: t.coolant,
    lifeRemaining: t.lifeRemaining,
    notes: t.notes ?? undefined,
    condition: t.condition as Tool["condition"],
    actualStickout: t.actualStickout ?? undefined,
    measuredRunout: t.measuredRunout ?? undefined,
    helixAngle: t.helixAngle ?? undefined,
    regrindCount: t.regrindCount,
    previousMaterial: t.previousMaterial ?? undefined,
    lastUsedAt: t.lastUsedAt ?? undefined,
    shopNotes: t.shopNotes ?? undefined,
  }));
}

export async function getWorkholding(organizationId: string): Promise<WorkholdingDevice[]> {
  const rows = await db.workholdingDevice.findMany({ where: { organizationId } });
  return rows.map((w) => ({
    id: w.id,
    type: w.type as WorkholdingDevice["type"],
    manufacturer: w.manufacturer ?? undefined,
    model: w.model ?? undefined,
    description: w.description,
    jawWidth: w.jawWidth,
    jawHeight: w.jawHeight,
    maxOpening: w.maxOpening,
    clampForce: w.clampForce ?? undefined,
    fixtureHeight: w.fixtureHeight,
    mountingGeometry: w.mountingGeometry ?? undefined,
    hasCadRepresentation: w.hasCadRepresentation,
    notes: w.notes ?? undefined,
  }));
}

export async function getMaterials(organizationId: string): Promise<(MaterialProfile & { specificEnergy: number })[]> {
  const rows = await db.material.findMany({ where: { organizationId }, orderBy: { name: "asc" } });
  return rows.map((m) => ({
    id: m.id,
    name: m.name,
    family: m.family as MaterialProfile["family"],
    condition: m.condition,
    density: m.density,
    hardness: m.hardness ?? undefined,
    yieldStrength: m.yieldStrength ?? undefined,
    tensileStrength: m.tensileStrength ?? undefined,
    machinabilityRating: m.machinabilityRating,
    sfmCarbideMin: m.sfmCarbideMin,
    sfmCarbideMax: m.sfmCarbideMax,
    specificEnergy: m.specificEnergy,
    costPerPound: m.costPerPound,
    weldable: m.weldable,
    castable: m.castable,
    notes: m.notes ?? undefined,
  }));
}

export async function getMetrology(organizationId: string): Promise<MetrologyDevice[]> {
  const rows = await db.metrologyDevice.findMany({ where: { organizationId } });
  return rows.map((d) => ({
    id: d.id,
    deviceType: d.deviceType as MetrologyDevice["deviceType"],
    description: d.description,
    rangeMin: d.rangeMin ?? undefined,
    rangeMax: d.rangeMax ?? undefined,
    resolution: d.resolution,
    uncertainty: d.uncertainty,
    calibrated: d.calibrated,
    calibrationDue: d.calibrationDue?.toISOString(),
  }));
}

/* ------------------------------------------------------------------ */
/* Parts                                                               */
/* ------------------------------------------------------------------ */

export async function getParts(organizationId: string) {
  return db.part.findMany({
    where: { organizationId },
    orderBy: { updatedAt: "desc" },
    include: {
      revisions: { orderBy: { revision: "desc" }, take: 1, include: { _count: { select: { features: true, setups: true } } } },
    },
  });
}

export interface LoadedRevision {
  partId: string;
  partName: string;
  partNumber: string | null;
  sharing: string;
  revisionId: string;
  revision: string;
  status: string;
  /** When the revision was released to the floor, and by whom. Null until it is. */
  releasedAt: Date | null;
  releasedBy: string | null;
  units: "IN" | "MM";
  intent: PartIntent;
  stock: Stock | null;
  features: Feature[];
  featureRows: { id: string; kind: string; label: string; functionalRole: string; critical: boolean }[];
}

/**
 * Loads a part revision with its intent and features rehydrated into domain
 * objects. Returns null when the part does not belong to the organisation —
 * indistinguishable from "does not exist", which is the correct behaviour.
 */
export async function loadRevision(
  organizationId: string,
  partId: string,
  revision?: string,
): Promise<LoadedRevision | null> {
  const part = await db.part.findFirst({
    where: { id: partId, organizationId },
    include: {
      revisions: {
        where: revision ? { revision } : undefined,
        orderBy: { revision: "desc" },
        take: 1,
        include: { features: { orderBy: { orderIndex: "asc" } } },
      },
    },
  });
  if (!part || part.revisions.length === 0) return null;
  const rev = part.revisions[0];

  const stock = parseJson<Stock | null>(rev.stockJson, null);
  // The stock a machinist defined is the answer to the intent's material and
  // stock questions. Reconciled on the way out, in one place, so the gate and
  // the part page cannot disagree about whether stock exists.
  const intent = reconcileIntentWithStock(
    { ...emptyPartIntent(part.name), ...parseJson<Partial<PartIntent>>(rev.intentJson, {}) } as PartIntent,
    stock,
  );

  const features: Feature[] = rev.features.map((f) => ({
    id: f.id,
    kind: f.kind,
    label: f.label,
    functionalRole: f.functionalRole,
    critical: f.critical,
    tolerance:
      f.tolerancePlus != null || f.toleranceMinus != null
        ? { plus: f.tolerancePlus ?? 0, minus: f.toleranceMinus ?? 0 }
        : undefined,
    surfaceFinish: f.surfaceFinish ?? undefined,
    inspectionMethod: f.inspectionMethod ?? undefined,
    notes: f.notes ?? undefined,
    ...parseJson<Record<string, unknown>>(f.parametersJson, {}),
  })) as Feature[];

  return {
    releasedAt: rev.releasedAt,
    releasedBy: rev.releasedBy,
    partId: part.id,
    partName: part.name,
    partNumber: part.partNumber,
    sharing: part.sharing,
    revisionId: rev.id,
    revision: rev.revision,
    status: rev.status,
    units: rev.units as "IN" | "MM",
    intent,
    stock,
    features,
    featureRows: rev.features.map((f) => ({
      id: f.id,
      kind: f.kind,
      label: f.label,
      functionalRole: f.functionalRole,
      critical: f.critical,
    })),
  };
}

export async function getSetups(revisionId: string) {
  return db.setup.findMany({
    where: { partRevisionId: revisionId },
    orderBy: { sequence: "asc" },
    include: {
      machine: true,
      workholding: true,
      operations: { orderBy: { sequence: "asc" }, include: { tool: true, feature: true } },
      jaws: true,
    },
  });
}

export async function getShopSettings(organizationId: string) {
  const shop = await db.shop.findFirst({ where: { organizationId } });
  return (
    shop ?? {
      id: "",
      organizationId,
      name: "Default",
      location: null,
      shiftHours: 8,
      machineRate: 75,
      operatorRate: 38,
      inspectionRate: 45,
      overheadRate: 0.18,
      marginRate: 0.32,
    }
  );
}

export { parseJson };
