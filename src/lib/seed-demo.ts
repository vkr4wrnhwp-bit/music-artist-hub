import "server-only";
import { db } from "./db";
import { hashPassword } from "./auth";

/**
 * Creates the demo shop from inside the running application.
 *
 * The build already seeds, but a build-time seed is fragile: it depends on dev
 * tooling being installed, on the database being reachable at build time, and
 * on the build not having failed earlier for an unrelated reason. When any of
 * that goes wrong the result is an app that renders a sign-in page nobody can
 * get past, with the explanation buried in a log.
 *
 * So the same demo data can be created on demand, and the sign-in page offers
 * it when no accounts exist. Guarded three ways: it is a no-op if any user
 * already exists, it only ever creates the one known demo organisation, and it
 * cannot be used to overwrite anything.
 *
 * This is a deliberately small subset of prisma/seed.ts — enough to sign in
 * and see a configured shop. The full demo part is seeded by the build.
 */

export const DEMO_EMAIL = "demo@canvas.local";
export const DEMO_PASSWORD = "canvas-demo";
const DEMO_SLUG = "canvas-prototype-shop";

export async function demoShopExists(): Promise<boolean> {
  const user = await db.user.findUnique({ where: { email: DEMO_EMAIL }, select: { id: true } });
  return Boolean(user);
}

export async function anyAccountExists(): Promise<boolean> {
  return (await db.user.count()) > 0;
}

export interface SeedOutcome {
  created: boolean;
  reason: string;
}

export async function createDemoShop(): Promise<SeedOutcome> {
  // Refuse if the instance is already in use. This endpoint must never be a
  // way to add an account to a deployment that has real data in it.
  if (await anyAccountExists()) {
    return { created: false, reason: "Accounts already exist on this instance." };
  }

  const org = await db.organization.upsert({
    where: { slug: DEMO_SLUG },
    update: {},
    create: {
      name: "CANVAS Prototype Shop",
      slug: DEMO_SLUG,
      industry: "JOB_SHOP",
      businessType: "JOB_SHOP",
      typicalTolerance: 0.005,
      typicalQuantity: "1-25",
      outsourced: JSON.stringify(["Anodising", "Heat treat", "Grinding"]),
      bottlenecks: JSON.stringify(["Second operation setups", "Soft jaw preparation"]),
      onboardingDone: true,
      defaultSharing: "PRIVATE",
    },
  });

  await db.user.create({
    data: {
      email: DEMO_EMAIL,
      name: "Demo Operator",
      passwordHash: await hashPassword(DEMO_PASSWORD),
      role: "OWNER",
      organizationId: org.id,
    },
  });

  await db.shop.create({
    data: {
      organizationId: org.id,
      name: "Main floor",
      machineRate: 75,
      operatorRate: 38,
      inspectionRate: 45,
      overheadRate: 0.18,
      marginRate: 0.32,
    },
  });

  await db.machine.create({
    data: {
      organizationId: org.id,
      manufacturer: "Haas",
      model: "VF-2 (reference profile)",
      controller: "HAAS_NGC",
      machineType: "VMC_3AXIS",
      axisCount: 3,
      travelsX: 30,
      travelsY: 16,
      travelsZ: 20,
      tableX: 36,
      tableY: 14,
      maxSpindleRPM: 8100,
      maxSpindlePower: 30,
      maxSpindleTorque: 90,
      maxFeed: 500,
      maxRapid: 1000,
      toolChangerCapacity: 20,
      maxToolDiameter: 3.5,
      maxToolLength: 12,
      maxToolWeight: 12,
      coolantTypes: JSON.stringify(["FLOOD", "AIR"]),
      probe: true,
      toolSetter: true,
      supportedPostProcessor: "haas-ngc-dev",
      isReferenceProfile: true,
      notes: "Reference specifications. Confirm against your own machine before running a program.",
    },
  });

  await db.workholdingDevice.create({
    data: {
      organizationId: org.id,
      type: "VISE",
      manufacturer: "Kurt",
      model: "DX6 (reference)",
      description: '6" machinist vise',
      jawWidth: 6,
      jawHeight: 1.75,
      maxOpening: 9,
      clampForce: 6000,
      fixtureHeight: 5.25,
      notes: "Reference dimensions. Measure your own vise before relying on fixture clearances.",
    },
  });

  await db.jawBlank.create({
    data: {
      organizationId: org.id,
      material: "ALUMINUM_6061",
      width: 6,
      height: 2,
      thickness: 1,
      boltPattern: 'Two 3/8-16 on 4" centres',
      quantityOnHand: 6,
    },
  });

  const tools = [
    { toolNumber: 1, toolClass: "FACE_MILL", description: '2" face mill, 4 insert', diameter: 2, flutes: 4, fluteLength: 0.3, overallLength: 3, stickout: 1.5, maxRPM: 6000, chiploadMin: 0.004, chiploadMax: 0.008, sfmMin: 600, sfmMax: 1200, costPerTool: 180, expectedLifeMinutes: 600 },
    { toolNumber: 2, toolClass: "FLAT_END_MILL", description: '1/2" 3-flute carbide end mill', diameter: 0.5, flutes: 3, fluteLength: 1.25, overallLength: 3, stickout: 1.6, maxRPM: 8100, chiploadMin: 0.002, chiploadMax: 0.005, sfmMin: 600, sfmMax: 1000, costPerTool: 42, expectedLifeMinutes: 240 },
    { toolNumber: 3, toolClass: "FLAT_END_MILL", description: '3/8" 3-flute carbide end mill', diameter: 0.375, flutes: 3, fluteLength: 1, overallLength: 2.5, stickout: 1.35, maxRPM: 8100, chiploadMin: 0.0015, chiploadMax: 0.004, sfmMin: 600, sfmMax: 1000, costPerTool: 34, expectedLifeMinutes: 240 },
    { toolNumber: 4, toolClass: "FLAT_END_MILL", description: '1/4" 3-flute carbide end mill', diameter: 0.25, flutes: 3, fluteLength: 0.75, overallLength: 2.5, stickout: 1.05, maxRPM: 8100, chiploadMin: 0.001, chiploadMax: 0.0025, sfmMin: 600, sfmMax: 1000, costPerTool: 26, expectedLifeMinutes: 200 },
    { toolNumber: 5, toolClass: "SPOT_DRILL", description: '1/2" 90° spot drill', diameter: 0.5, pointAngle: 90, tipDiameter: 0, flutes: 2, fluteLength: 0.4, overallLength: 2.5, stickout: 1, maxRPM: 6000, chiploadMin: 0.002, chiploadMax: 0.004, sfmMin: 250, sfmMax: 400, costPerTool: 30, expectedLifeMinutes: 400 },
    { toolNumber: 6, toolClass: "DRILL", description: '#7 (0.201") carbide drill', diameter: 0.201, pointAngle: 118, tipDiameter: 0, flutes: 2, fluteLength: 1.5, overallLength: 3, stickout: 1.9, maxRPM: 8100, chiploadMin: 0.003, chiploadMax: 0.006, sfmMin: 250, sfmMax: 400, costPerTool: 24, expectedLifeMinutes: 180 },
    { toolNumber: 7, toolClass: "CHAMFER_MILL", description: '1/2" 90° chamfer mill', diameter: 0.5, pointAngle: 90, tipDiameter: 0.02, flutes: 4, fluteLength: 0.5, overallLength: 2.5, stickout: 1.1, maxRPM: 8100, chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 500, sfmMax: 900, costPerTool: 38, expectedLifeMinutes: 300 },
  ];

  for (const t of tools) {
    await db.tool.create({
      data: {
        organizationId: org.id,
        material: "CARBIDE",
        cornerRadius: 0,
        recommendedMaterials: JSON.stringify(["Aluminum 6061", "Aluminum 7075"]),
        coolant: "FLOOD",
        lifeRemaining: 1,
        ...t,
      },
    });
  }

  const materials = [
    { name: "Aluminum 6061", family: "ALUMINUM", condition: "T6", density: 0.098, machinabilityRating: 190, sfmCarbideMin: 600, sfmCarbideMax: 1200, specificEnergy: 0.3, costPerPound: 4.25, castable: false },
    { name: "Steel 1018", family: "STEEL", condition: "Cold rolled", density: 0.284, machinabilityRating: 78, sfmCarbideMin: 300, sfmCarbideMax: 600, specificEnergy: 1.0, costPerPound: 1.1, castable: true },
    { name: "Stainless 304", family: "STAINLESS", condition: "Annealed", density: 0.289, machinabilityRating: 45, sfmCarbideMin: 200, sfmCarbideMax: 400, specificEnergy: 1.4, costPerPound: 4.8, castable: true },
  ];
  for (const m of materials) await db.material.create({ data: { organizationId: org.id, weldable: true, ...m } });

  const metrology = [
    { deviceType: "DIGITAL_CALIPER", description: '0–6" digital calipers', resolution: 0.0005, uncertainty: 0.002 },
    { deviceType: "MICROMETER", description: '1–2" outside micrometer', rangeMin: 1, rangeMax: 2, resolution: 0.0001, uncertainty: 0.0002 },
    { deviceType: "BORE_GAUGE", description: '1–2" dial bore gauge', rangeMin: 1, rangeMax: 2, resolution: 0.0001, uncertainty: 0.0002 },
    { deviceType: "HEIGHT_GAUGE", description: '0–12" height gauge', resolution: 0.001, uncertainty: 0.001 },
    { deviceType: "SURFACE_PLATE", description: '18 × 24" granite surface plate', resolution: 0.0001, uncertainty: 0.0001 },
  ];
  for (const d of metrology) await db.metrologyDevice.create({ data: { organizationId: org.id, calibrated: true, ...d } });

  return { created: true, reason: "Demo shop created." };
}
