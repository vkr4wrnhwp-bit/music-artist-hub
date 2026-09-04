import { PrismaClient } from "../src/generated/prisma";
import bcrypt from "bcryptjs";

/**
 * Demo shop and TEST PART 001.
 *
 * Everything seeded here is labelled as reference/demo data. Machine specs in
 * particular are marked `isReferenceProfile` so the UI never presents them as
 * manufacturer-verified for a real machine on a real floor.
 */

// Same provider selection as the application: SQLite locally, Postgres in a
// deployment. Chosen from the connection string so there is nothing extra to
// configure on either side.
const url = process.env.DATABASE_URL ?? "file:./prisma/dev.db";

function createClient(): PrismaClient {
  if (url.startsWith("postgres://") || url.startsWith("postgresql://")) {
    const { PrismaPg } = require("@prisma/adapter-pg") as typeof import("@prisma/adapter-pg");
    return new PrismaClient({ adapter: new PrismaPg({ connectionString: url }) });
  }
  if (/^(libsql|wss?|https?):\/\//.test(url)) {
    const { PrismaLibSql } = require("@prisma/adapter-libsql") as typeof import("@prisma/adapter-libsql");
    return new PrismaClient({
      adapter: new PrismaLibSql({ url, authToken: process.env.DATABASE_AUTH_TOKEN }),
    });
  }
  const { PrismaBetterSqlite3 } = require("@prisma/adapter-better-sqlite3") as typeof import("@prisma/adapter-better-sqlite3");
  return new PrismaClient({ adapter: new PrismaBetterSqlite3({ url }) });
}

const db = createClient();

const json = (v: unknown) => JSON.stringify(v);

async function main() {
  // A deployment runs the seed on every build, so it must be safe to re-run.
  // If the demo shop is already there, leave it alone — re-seeding would
  // discard any parts, jobs or measurements added since, which on a shared
  // demo instance means throwing away someone else's work.
  const existing = await db.organization.findUnique({ where: { slug: "canvas-prototype-shop" } });
  if (existing && process.env.CANVAS_FORCE_RESEED !== "1") {
    console.log("CANVAS demo shop already present — leaving it untouched.");
    console.log("  Set CANVAS_FORCE_RESEED=1 to replace it.");
    return;
  }

  console.log("Seeding CANVAS demo shop…");

  await teardownOrganization("canvas-prototype-shop");

  const org = await db.organization.create({
    data: {
      name: "CANVAS Prototype Shop",
      slug: "canvas-prototype-shop",
      industry: "JOB_SHOP",
      businessType: "JOB_SHOP",
      typicalTolerance: 0.005,
      typicalQuantity: "1-25",
      outsourced: json(["Anodising", "Heat treat", "Grinding"]),
      bottlenecks: json(["Second operation setups", "Soft jaw preparation", "Inspection of critical bores"]),
      onboardingDone: true,
      defaultSharing: "PRIVATE",
    },
  });

  await db.user.create({
    data: {
      email: "demo@canvas.local",
      name: "Demo Operator",
      passwordHash: await bcrypt.hash("canvas-demo", 12),
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

  /* ---------------- Machine ---------------- */

  const machine = await db.machine.create({
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
      // Representative value for the fictional reference profile, like every
      // other number on this machine — not a datasheet figure.
      axisAccel: 15,
      toolChangerCapacity: 20,
      maxToolDiameter: 3.5,
      maxToolLength: 12,
      maxToolWeight: 12,
      coolantTypes: json(["FLOOD", "AIR"]),
      throughSpindleCoolant: false,
      probe: true,
      toolSetter: true,
      fourthAxis: false,
      fifthAxis: false,
      supportedPostProcessor: "haas-ngc-dev",
      isReferenceProfile: true,
      notes:
        "Reference specifications for development. Confirm every value against your own machine's documentation before running a program.",
    },
  });

  /* ---------------- Tool holder + tool crib ---------------- */

  const cat40 = await db.toolHolder.create({
    data: { description: "CAT40 ER32 collet chuck", taper: "CAT40", noseDiameter: 1.85, gaugeLength: 4 },
  });
  const shellHolder = await db.toolHolder.create({
    data: { description: "CAT40 shell mill arbor", taper: "CAT40", noseDiameter: 2.5, gaugeLength: 3 },
  });

  const tools = [
    { toolNumber: 1, toolClass: "FACE_MILL", description: '2" face mill, 4 insert', diameter: 2, flutes: 4, material: "CARBIDE", coating: "TiAlN", fluteLength: 0.3, overallLength: 3, stickout: 1.5, holderId: shellHolder.id, maxRPM: 6000, chiploadMin: 0.004, chiploadMax: 0.008, sfmMin: 600, sfmMax: 1200, costPerTool: 180, expectedLifeMinutes: 600 },
    { toolNumber: 2, toolClass: "FLAT_END_MILL", description: '1/2" 3-flute carbide end mill', diameter: 0.5, flutes: 3, material: "CARBIDE", coating: "ZrN", fluteLength: 1.25, overallLength: 3, stickout: 1.6, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.002, chiploadMax: 0.005, sfmMin: 600, sfmMax: 1000, costPerTool: 42, expectedLifeMinutes: 240 },
    { toolNumber: 3, toolClass: "FLAT_END_MILL", description: '3/8" 3-flute carbide end mill', diameter: 0.375, flutes: 3, material: "CARBIDE", coating: "ZrN", fluteLength: 1, overallLength: 2.5, stickout: 1.35, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.0015, chiploadMax: 0.004, sfmMin: 600, sfmMax: 1000, costPerTool: 34, expectedLifeMinutes: 240 },
    { toolNumber: 4, toolClass: "FLAT_END_MILL", description: '1/4" 3-flute carbide end mill', diameter: 0.25, flutes: 3, material: "CARBIDE", coating: "ZrN", fluteLength: 0.75, overallLength: 2.5, stickout: 1.05, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.001, chiploadMax: 0.0025, sfmMin: 600, sfmMax: 1000, costPerTool: 26, expectedLifeMinutes: 200 },
    { toolNumber: 5, toolClass: "SPOT_DRILL", description: '1/2" 90° spot drill', diameter: 0.5, pointAngle: 90, tipDiameter: 0, flutes: 2, material: "CARBIDE", coating: "TiN", fluteLength: 0.4, overallLength: 2.5, stickout: 1, holderId: cat40.id, maxRPM: 6000, chiploadMin: 0.002, chiploadMax: 0.004, sfmMin: 250, sfmMax: 400, costPerTool: 30, expectedLifeMinutes: 400 },
    { toolNumber: 6, toolClass: "DRILL", description: '#7 (0.201") carbide drill', diameter: 0.201, pointAngle: 118, tipDiameter: 0, flutes: 2, material: "CARBIDE", coating: "TiAlN", fluteLength: 1.5, overallLength: 3, stickout: 1.9, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.003, chiploadMax: 0.006, sfmMin: 250, sfmMax: 400, costPerTool: 24, expectedLifeMinutes: 180 },
    { toolNumber: 7, toolClass: "CHAMFER_MILL", description: '1/2" 90° chamfer mill', diameter: 0.5, pointAngle: 90, tipDiameter: 0.02, flutes: 4, material: "CARBIDE", coating: "TiAlN", fluteLength: 0.5, overallLength: 2.5, stickout: 1.1, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 500, sfmMax: 900, costPerTool: 38, expectedLifeMinutes: 300 },
    { toolNumber: 8, toolClass: "ENGRAVER", description: '1/8" 60° engraving tool', diameter: 0.125, flutes: 1, material: "CARBIDE", fluteLength: 0.25, overallLength: 2, stickout: 0.8, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.0005, chiploadMax: 0.0015, sfmMin: 300, sfmMax: 600, costPerTool: 18, expectedLifeMinutes: 300 },
    { toolNumber: 9, toolClass: "BORING_TOOL", description: '1.0"–2.0" adjustable boring head', diameter: 1.5748, flutes: 1, material: "CARBIDE", fluteLength: 0.75, overallLength: 4, stickout: 2.2, holderId: cat40.id, maxRPM: 2000, chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 400, sfmMax: 700, costPerTool: 260, expectedLifeMinutes: 600 },
    { toolNumber: 10, toolClass: "TAP", description: "1/4-20 spiral point tap", diameter: 0.25, threadDesignation: "1/4-20 UNC", tapLeadThreads: 4, flutes: 3, material: "HSS", coating: "TiN", fluteLength: 1, overallLength: 2.5, stickout: 1.5, holderId: cat40.id, maxRPM: 4000, chiploadMin: 0.001, chiploadMax: 0.002, sfmMin: 30, sfmMax: 60, costPerTool: 14, expectedLifeMinutes: 500 },
  ];

  /**
   * Which tools are loaded in the VF-2's changer, by tool number.
   *
   * Deliberately partial. Seven of the ten are in the machine and three are
   * in the crib, because that is what a real changer looks like on a Tuesday
   * — and a demo where every tool happens to be loaded would teach the
   * opposite of what the carousel exists to show. Tool 9 (the boring head)
   * and tool 10 (the tap) are the ones a shop swaps in for the job, so they
   * are the ones left out.
   */
  const POCKETS: Record<number, number> = { 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7 };

  for (const t of tools) {
    const pocket = POCKETS[t.toolNumber] ?? null;
    await db.tool.create({
      data: {
        organizationId: org.id,
        cornerRadius: 0,
        recommendedMaterials: json(["Aluminum 6061", "Aluminum 7075", "Brass 360"]),
        coolant: "FLOOD",
        lifeRemaining: 1,
        machineId: pocket === null ? null : machine.id,
        pocket,
        ...t,
      },
    });
  }

  /* ---------------- Workholding ---------------- */

  const vise = await db.workholdingDevice.create({
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
      mountingGeometry: "Standard 6\" vise base, keyed to table slots",
      hasCadRepresentation: false,
      notes: "Reference dimensions. Measure your own vise before relying on fixture clearance numbers.",
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

  /* ---------------- Soft jaw drawer ---------------- */

  // A real drawer: jaws cut for previous jobs at round sizes, which is exactly
  // what makes them reusable. The 6" round is the one the demo part can borrow.
  const jawSets = [
    { name: "Round soft jaws — 6.000", profile: "ROUND", nominalSize: 6, stepDepth: 0.25, jawHeight: 2, timesUsed: 4, minutesToCut: 38, notes: "Cut for the pump housing job. Shims down to about 4.5\" comfortably." },
    { name: "Round soft jaws — 3.000", profile: "ROUND", nominalSize: 3, stepDepth: 0.2, jawHeight: 2, timesUsed: 7, minutesToCut: 32, notes: "The most-used set in the drawer." },
    { name: "Rectangular soft jaws — 4.000 × 6.000", profile: "RECTANGULAR", nominalSize: 4, nominalLength: 6, stepDepth: 0.15, jawHeight: 2, timesUsed: 2, minutesToCut: 40, notes: "Cut for a plate job. Step is shallow — check grip before reusing." },
  ];
  for (const j of jawSets) {
    await db.jawSet.create({
      data: {
        organizationId: org.id,
        material: "ALUMINUM_6061",
        viseDescription: '6" machinist vise',
        ...j,
      },
    });
  }

  /* ---------------- Materials ---------------- */

  const materials = [
    { name: "Aluminum 6061", family: "ALUMINUM", condition: "T6", density: 0.098, hardness: 95, yieldStrength: 40, tensileStrength: 45, machinabilityRating: 190, sfmCarbideMin: 600, sfmCarbideMax: 1200, specificEnergy: 0.3, costPerPound: 4.25, weldable: true, castable: false },
    { name: "Aluminum 7075", family: "ALUMINUM", condition: "T651", density: 0.102, hardness: 150, yieldStrength: 73, tensileStrength: 83, machinabilityRating: 140, sfmCarbideMin: 500, sfmCarbideMax: 1000, specificEnergy: 0.35, costPerPound: 8.9, weldable: false, castable: false },
    { name: "Steel 1018", family: "STEEL", condition: "Cold rolled", density: 0.284, hardness: 126, yieldStrength: 54, tensileStrength: 64, machinabilityRating: 78, sfmCarbideMin: 300, sfmCarbideMax: 600, specificEnergy: 1.0, costPerPound: 1.1, weldable: true, castable: true },
    { name: "Steel 4140", family: "STEEL", condition: "Pre-hard 28-32 HRC", density: 0.284, hardness: 300, yieldStrength: 95, tensileStrength: 148, machinabilityRating: 55, sfmCarbideMin: 250, sfmCarbideMax: 450, specificEnergy: 1.3, costPerPound: 2.4, weldable: false, castable: true },
    { name: "Stainless 304", family: "STAINLESS", condition: "Annealed", density: 0.289, hardness: 170, yieldStrength: 31, tensileStrength: 85, machinabilityRating: 45, sfmCarbideMin: 200, sfmCarbideMax: 400, specificEnergy: 1.4, costPerPound: 4.8, weldable: true, castable: true },
    { name: "Titanium 6Al-4V", family: "TITANIUM", condition: "Annealed", density: 0.16, hardness: 334, yieldStrength: 128, tensileStrength: 138, machinabilityRating: 22, sfmCarbideMin: 100, sfmCarbideMax: 250, specificEnergy: 1.6, costPerPound: 32, weldable: true, castable: true },
  ];
  for (const m of materials) await db.material.create({ data: { organizationId: org.id, ...m } });

  /* ---------------- Metrology ---------------- */

  const metrology = [
    { deviceType: "DIGITAL_CALIPER", description: '0–6" digital calipers', rangeMin: 0, rangeMax: 6, resolution: 0.0005, uncertainty: 0.002, calibrated: true },
    { deviceType: "MICROMETER", description: '0–1" outside micrometer', rangeMin: 0, rangeMax: 1, resolution: 0.0001, uncertainty: 0.0002, calibrated: true },
    { deviceType: "MICROMETER", description: '1–2" outside micrometer', rangeMin: 1, rangeMax: 2, resolution: 0.0001, uncertainty: 0.0002, calibrated: true },
    { deviceType: "BORE_GAUGE", description: '1–2" dial bore gauge', rangeMin: 1, rangeMax: 2, resolution: 0.0001, uncertainty: 0.0002, calibrated: true },
    { deviceType: "HEIGHT_GAUGE", description: '0–12" height gauge', rangeMin: 0, rangeMax: 12, resolution: 0.001, uncertainty: 0.001, calibrated: true },
    { deviceType: "SURFACE_PLATE", description: '18 × 24" granite surface plate, Grade B', resolution: 0.0001, uncertainty: 0.0001, calibrated: true },
    { deviceType: "DIAL_INDICATOR", description: '0.001" dial indicator', resolution: 0.001, uncertainty: 0.001, calibrated: true },
    { deviceType: "MACHINE_PROBE", description: "Spindle probe on the VF-2", resolution: 0.0001, uncertainty: 0.0005, calibrated: true },
    // Shop-grade structured light, at the uncertainty it actually achieves
    // on a bench in shop conditions — not the brochure figure. This is what
    // makes the scan import usable in the demo, and its number is what the
    // import attaches to every scanned dimension.
    { deviceType: "STRUCTURED_LIGHT_SCANNER", description: "Benchtop structured-light scanner", resolution: 0.001, uncertainty: 0.002, calibrated: false },
  ];
  for (const d of metrology) await db.metrologyDevice.create({ data: { organizationId: org.id, ...d } });

  /*
   * ADDITIVE — a shop-floor FDM machine and a resin printer.
   *
   * Deliberately ordinary machines with the numbers a shop would actually
   * measure, not aspirational ones: the advisor's whole job is to say what
   * these can and cannot do, and seeding a machine that holds ±0.0005 would
   * make every answer agreeable and useless.
   *
   * `achievableTolerance` is what the shop observed on a printed coupon. PETG
   * keeps under half its in-plane strength through the layers, which is the
   * figure the anisotropy check exists to surface; the SLA resin has no creep
   * data on file, which is the honest state for most shops.
   */
  const printers = [
    {
      manufacturer: "Prusa", model: "MK4", technology: "FDM",
      buildX: 9.84, buildY: 8.3, buildZ: 8.6,
      achievableTolerance: 0.008, achievableRa: 500, minLayerHeight: 0.002, nozzleDiameter: 0.0157,
      notes: "Tolerance measured on a printed coupon, not the manufacturer's figure.",
    },
    {
      manufacturer: "Formlabs", model: "Form 3+", technology: "SLA",
      buildX: 5.7, buildY: 5.7, buildZ: 7.3,
      achievableTolerance: 0.003, achievableRa: 80, minLayerHeight: 0.001, nozzleDiameter: null,
      notes: null,
    },
  ];
  for (const p of printers) await db.printer.create({ data: { organizationId: org.id, ...p } });

  const printMaterials = [
    { name: "PETG — Prusament", technology: "FDM", tensileXY: 7100, tensileZ: 3250, maxServiceTempF: 160, creepDataOnFile: false, densityLbIn3: 0.0459, costPerPound: 12.5, notes: "Z strength measured in house on printed coupons." },
    { name: "PLA", technology: "FDM", tensileXY: 8000, tensileZ: 3000, maxServiceTempF: 130, creepDataOnFile: false, densityLbIn3: 0.0448, costPerPound: 9, notes: null },
    { name: "Nylon-CF", technology: "FDM", tensileXY: 10500, tensileZ: null, maxServiceTempF: 290, creepDataOnFile: false, densityLbIn3: 0.0426, costPerPound: 42, notes: "No Z figure measured yet — do not assume it matches the in-plane number." },
    { name: "Tough 2000 resin", technology: "SLA", tensileXY: 6400, tensileZ: 6100, maxServiceTempF: 145, creepDataOnFile: false, densityLbIn3: 0.0430, costPerPound: 68, notes: null },
  ];
  for (const m of printMaterials) await db.printMaterial.create({ data: { organizationId: org.id, ...m } });

  /* ================================================================ */
  /* TEST PART 001 — CANVAS Bearing Support                           */
  /* ================================================================ */

  const part = await db.part.create({
    data: {
      organizationId: org.id,
      name: "CANVAS Bearing Support",
      partNumber: "CNV-001",
      description:
        "Demonstration component. Carries a 40 mm bearing outer race, locates on two dowels and mounts on four 1/4-20 fasteners.",
      sharing: "PRIVATE",
      isDemo: true,
    },
  });

  // Provenance-wrapped intent. Note what is NOT confirmed: the responsibility
  // fields are deliberately left for the user to answer, because that
  // interview is the point of the demo.
  const intent = {
    partName: p("CANVAS Bearing Support", "USER", "VERIFIED", true),
    description: p("Bearing support plate for a 40 mm bearing", "USER", "VERIFIED", true),
    units: p("IN", "USER", "VERIFIED", true),
    material: p("Aluminum 6061", "USER", "VERIFIED", true),
    materialCondition: p("T6511", "USER", "VERIFIED", true),
    stock: p({ form: "RECTANGULAR", x: 6, y: 4, z: 0.75 }, "USER", "VERIFIED", true),
    finishedEnvelope: p({ x: 5.875, y: 3.875, z: 0.625 }, "CALCULATED", "MEDIUM", false),
    quantity: p(10, "USER", "VERIFIED", true),
    features: p(
      ["Outside profile", "40 mm bearing bore", "4 × 1/4-20 mounting holes", "2 × 1/4 dowel holes", "Relief pocket", "Outside chamfer"],
      "USER",
      "VERIFIED",
      true,
    ),
    criticalDimensions: p(
      [
        { id: "cd1", label: "Bearing bore", nominal: 1.5748, plus: 0.0005, minus: 0, inspectionMethod: "1–2\" bore gauge + micrometer" },
        { id: "cd2", label: "Dowel hole spacing", nominal: 4.0, plus: 0.001, minus: 0.001, inspectionMethod: "Height gauge on surface plate" },
      ],
      "USER",
      "VERIFIED",
      true,
    ),
    generalTolerance: p(0.005, "USER", "VERIFIED", true),
    criticalTolerances: p([], "USER", "HIGH", true),
    surfaceFinish: p("125 Ra general, 63 Ra in the bore", "USER", "VERIFIED", true),
    application: p("Supports a bearing on a light-duty test rig", "USER", "HIGH", true),
    loadBearing: nullField("Not yet answered — required before process advice"),
    safetyCritical: nullField("Not yet answered"),
    failureConsequence: nullField("Not yet assessed"),
    loadingType: nullField("Not yet answered"),
    environment: nullField("Not yet answered"),
    temperatureRange: nullField(),
    regulatoryRequirements: nullField(),
    inspectionRequirements: p(["First article on all critical dimensions", "100% bore inspection"], "USER", "VERIFIED", true),
    productionIntent: p("PROTOTYPE", "USER", "VERIFIED", true),
    annualVolume: nullField("Not stated"),
    notes: p("Bore is a metric bearing interface. Do not round it to an inch value.", "USER", "VERIFIED", true),
    unknowns: [
      "Part responsibility profile not completed",
      "Annual volume unknown — process comparison cannot run",
    ],
    confidence: 0.72,
  };

  const rev = await db.partRevision.create({
    data: {
      partId: part.id,
      revision: "A",
      status: "DRAFT",
      units: "IN",
      intentJson: json(intent),
      stockJson: json({ form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061", condition: "T6511" }),
      notes: "Seeded demonstration revision.",
    },
  });

  await db.partResponsibilityProfile.create({
    data: {
      partRevisionId: rev.id,
      loadBearing: null,
      safetyCritical: null,
      failureConsequence: null,
      productionIntent: "PROTOTYPE",
      inspectionRequirements: json(["First article on all critical dimensions", "100% bore inspection"]),
    },
  });

  /* ---------------- Features ---------------- */

  const featureDefs: {
    kind: string;
    label: string;
    functionalRole: string;
    critical: boolean;
    parameters: Record<string, unknown>;
    tolerancePlus?: number;
    toleranceMinus?: number;
    surfaceFinish?: number;
    inspectionMethod?: string;
    notes?: string;
  }[] = [
    { kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", critical: true, parameters: { depth: 0.0625 }, tolerancePlus: 0.002, toleranceMinus: 0.002, surfaceFinish: 125, inspectionMethod: "Micrometer", notes: "Datum A." },
    { kind: "OUTSIDE_CONTOUR", label: "Outside profile", functionalRole: "NONE", critical: false, parameters: { width: 5.875, length: 3.875, cornerRadius: 0.25, depth: 0.625 }, tolerancePlus: 0.005, toleranceMinus: 0.005 },
    {
      kind: "BORE",
      label: "40 mm bearing bore",
      functionalRole: "BEARING_SEAT",
      critical: true,
      parameters: { centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.625, bottomRadius: 0, top: 0, through: true },
      tolerancePlus: 0.0005,
      toleranceMinus: 0,
      surfaceFinish: 63,
      inspectionMethod: '1–2" bore gauge + micrometer',
      notes: "40 mm nominal. This is a metric bearing interface — do not substitute an inch value.",
    },
    { kind: "RECT_POCKET", label: "Relief pocket", functionalRole: "CLEARANCE", critical: false, parameters: { centerX: 0, centerY: 0, width: 3, length: 2, depth: 0.125, cornerRadius: 0.25, bottomRadius: 0, top: 0 }, tolerancePlus: 0.01, toleranceMinus: 0.01 },
    ...[
      { x: -2.25, y: -1.375 },
      { x: 2.25, y: -1.375 },
      { x: 2.25, y: 1.375 },
      { x: -2.25, y: 1.375 },
    ].map((pos, i) => ({
      kind: "TAPPED_HOLE",
      label: `1/4-20 mounting hole ${i + 1}`,
      functionalRole: "MOUNTING_HOLE",
      critical: false,
      parameters: { centerX: pos.x, centerY: pos.y, diameter: 0.201, depth: 0.625, through: true, top: 0, thread: "1/4-20 UNC" },
      tolerancePlus: 0.01,
      toleranceMinus: 0.01,
      inspectionMethod: "Thread gauge",
    })),
    ...[
      { x: -2, y: 0 },
      { x: 2, y: 0 },
    ].map((pos, i) => ({
      kind: "DRILLED_HOLE",
      label: `1/4 dowel hole ${i + 1}`,
      functionalRole: "DOWEL_HOLE",
      critical: true,
      parameters: { centerX: pos.x, centerY: pos.y, diameter: 0.2495, depth: 0.625, through: true, top: 0 },
      tolerancePlus: 0.0005,
      toleranceMinus: 0,
      inspectionMethod: "Pin gauge + height gauge",
      notes: "Locating dowels. Spacing is a critical dimension.",
    })),
    { kind: "CHAMFER", label: "Outside chamfer", functionalRole: "NONE", critical: false, parameters: { width: 0.03, angle: 45, applyTo: "OUTSIDE_TOP" } },
  ];

  const features: { id: string; label: string }[] = [];
  for (const [i, f] of featureDefs.entries()) {
    features.push(
      await db.feature.create({
        data: {
          partRevisionId: rev.id,
          kind: f.kind,
          label: f.label,
          functionalRole: f.functionalRole,
          critical: f.critical,
          parametersJson: json(f.parameters),
          tolerancePlus: f.tolerancePlus,
          toleranceMinus: f.toleranceMinus,
          surfaceFinish: f.surfaceFinish,
          inspectionMethod: f.inspectionMethod,
          notes: f.notes,
          orderIndex: i,
        },
      }),
    );
  }

  const byLabel = (l: string) => features.find((f) => f.label === l)!;
  const toolByNumber = async (n: number) =>
    (await db.tool.findFirst({ where: { organizationId: org.id, toolNumber: n } }))!;

  /* ---------------- Setups ---------------- */

  const setup1 = await db.setup.create({
    data: {
      partRevisionId: rev.id,
      sequence: 1,
      name: "SETUP 1 — Top face, bore, holes",
      orientation: "TOP",
      machineId: machine.id,
      workholdingId: vise.id,
      workOffset: "G54",
      datumNote: "Datum A = top face. X0Y0 at the bore centre, established by probing the stock.",
      gripDepth: 0.375,
      gripLength: 4,
      stockProjection: 0.375,
      parallelHeight: 1.0,
      notes: "Stock held on the as-sawn outside. Everything reachable from the top is completed here.",
    },
  });

  const setup2 = await db.setup.create({
    data: {
      partRevisionId: rev.id,
      sequence: 2,
      name: "SETUP 2 — Flip, finish bottom and profile",
      orientation: "BOTTOM",
      machineId: machine.id,
      workholdingId: vise.id,
      workOffset: "G55",
      datumNote: "Located on the machined top face from Setup 1, seated in soft jaws.",
      // This setup used to grip 0.080" in plain jaws and assessed HIGH RISK —
      // 6.8:1 projection, the exact failure recorded in the shop's job
      // history ("part shifted during the profile pass"). The resolution is
      // the one CANVAS itself recommends: machined soft jaws. A 0.250" step
      // grips the finished profile, leaves the 0.625" part standing 0.375"
      // proud — 1.5:1, the model's supported limit — and the machined step is
      // a positive stop, so the load path is steel, not friction alone. The
      // jaw pair is recorded below, same as the soft-jaws flow records it.
      gripDepth: 0.25,
      gripLength: 3.875,
      stockProjection: 0.375,
      parallelHeight: 0.5,
      jawSurface: "SOFT_MACHINED",
      notes:
        "Machined soft jaws — the finished profile has no square stock left to grip. Part seats on the 0.250 step against the stop.",
    },
  });

  // The soft jaw pair for Setup 2, with the geometry the generator produces
  // for a 0.250" grip on this profile (R0.25 corners → R0.28 relief).
  const jawBlankRow = await db.jawBlank.findFirst({ where: { organizationId: org.id } });
  for (const side of ["LEFT", "RIGHT"] as const) {
    await db.jaw.create({
      data: {
        setupId: setup2.id,
        deviceId: vise.id,
        blankId: jawBlankRow?.id,
        side,
        stepDepth: 0.25,
        stepHeight: 1.75,
        seatWidth: 3.895,
        seatDepth: 0.333,
        seatCornerRadius: 0.28,
        stopLocation: side === "LEFT" ? -1.9475 : null,
        reliefRadius: 0.28,
        clampingDirection: "X",
        processJson: JSON.stringify([
          "Face jaw blanks clamped on a spacer",
          "Cut 3.895 seat, 0.250 step, R0.280 relief",
          "Deburr, seat part, probe before cutting",
        ]),
      },
    });
  }

  /* ---------------- Operations ---------------- */

  const ops: { setupId: string; label: string; type: string; featureLabel: string | null; toolNumber: number; topZ: number; finalZ: number; sequence: number }[] = [
    { setupId: setup1.id, label: "Face top", type: "FACE", featureLabel: "Face top", toolNumber: 1, topZ: 0.0625, finalZ: 0, sequence: 1 },
    { setupId: setup1.id, label: "Rough relief pocket", type: "POCKET_2D", featureLabel: "Relief pocket", toolNumber: 3, topZ: 0, finalZ: -0.125, sequence: 2 },
    { setupId: setup1.id, label: "Spot drill holes", type: "DRILL", featureLabel: "1/4-20 mounting hole 1", toolNumber: 5, topZ: 0, finalZ: -0.08, sequence: 3 },
    { setupId: setup1.id, label: "Drill 1/4-20 tap holes", type: "PECK_DRILL", featureLabel: "1/4-20 mounting hole 1", toolNumber: 6, topZ: 0, finalZ: -0.7, sequence: 4 },
    { setupId: setup1.id, label: "Rough bearing bore", type: "POCKET_2D", featureLabel: "40 mm bearing bore", toolNumber: 2, topZ: 0, finalZ: -0.7, sequence: 5 },
    { setupId: setup1.id, label: "Finish bore to 40 mm", type: "BORE", featureLabel: "40 mm bearing bore", toolNumber: 9, topZ: 0, finalZ: -0.7, sequence: 6 },
    { setupId: setup1.id, label: "Chamfer top edges", type: "CHAMFER", featureLabel: "Outside chamfer", toolNumber: 7, topZ: 0, finalZ: -0.03, sequence: 7 },
    // The tap holes were drilled at sequence 4 and, until this operation
    // existed, never tapped — the plan shipped the part with four plain
    // 0.201" holes. Tapping runs after the chamfer so the countersink leads
    // the tap in.
    { setupId: setup1.id, label: "Tap 1/4-20 mounting holes", type: "TAP", featureLabel: "1/4-20 mounting hole 1", toolNumber: 10, topZ: 0, finalZ: -0.7, sequence: 8 },
    { setupId: setup2.id, label: "Face bottom to thickness", type: "FACE", featureLabel: "Face top", toolNumber: 1, topZ: 0.0625, finalZ: 0, sequence: 1 },
    { setupId: setup2.id, label: "Finish outside profile", type: "CONTOUR_2D", featureLabel: "Outside profile", toolNumber: 2, topZ: 0, finalZ: -0.625, sequence: 2 },
  ];

  for (const o of ops) {
    const tool = await toolByNumber(o.toolNumber);
    await db.operation.create({
      data: {
        setupId: o.setupId,
        featureId: o.featureLabel ? byLabel(o.featureLabel).id : null,
        toolId: tool.id,
        sequence: o.sequence,
        type: o.type,
        label: o.label,
        topZ: o.topZ,
        finalZ: o.finalZ,
        clearanceZ: 0.1,
        retractZ: 1,
        isPlaceholder: o.type === "ADAPTIVE_2D",
      },
    });
  }

  /* ---------------- Inspection plan ---------------- */

  /* ---------------- Datum reference frame ---------------- */
  // Datum A matches the setup note ("Datum A = top face") and the drawing's
  // "Datum A." note on the face feature — a human decision, so accepted.
  // B is CANVAS's proposal off the bore centreline and stays PROPOSED:
  // datums are never established by inference alone.
  await db.datum.createMany({
    data: [
      {
        partRevisionId: rev.id,
        letter: "A",
        system: "DESIGN",
        featureId: byLabel("Face top").id,
        description: "Top face — primary plane, seats on the parallels",
        geometryType: "PLANE",
        acceptedByUser: true,
        acceptedAt: new Date(),
        source: "USER",
      },
      {
        partRevisionId: rev.id,
        letter: "B",
        system: "DESIGN",
        featureId: byLabel("40 mm bearing bore").id,
        description: "Bearing bore centreline — secondary axis",
        geometryType: "AXIS",
        proposedReason:
          "The bore is the only critical toleranced feature that constrains X and Y; the mounting pattern is dimensioned from its centre.",
        acceptedByUser: false,
        source: "SYSTEM",
      },
    ],
  });

  const plan = await db.inspectionPlan.create({
    data: { partRevisionId: rev.id, name: "First article — Rev A", samplingPlan: "FIRST_ARTICLE" },
  });

  await db.inspectionItem.createMany({
    data: [
      { planId: plan.id, featureId: byLabel("40 mm bearing bore").id, label: "Bearing bore diameter", nominal: 1.5748, plusTol: 0.0005, minusTol: 0, method: "Bore gauge + micrometer", deviceType: "BORE_GAUGE", sequence: 1 },
      { planId: plan.id, featureId: byLabel("1/4 dowel hole 1").id, label: "Dowel hole spacing", nominal: 4.0, plusTol: 0.001, minusTol: 0.001, method: "Height gauge on surface plate", deviceType: "HEIGHT_GAUGE", sequence: 2 },
      { planId: plan.id, featureId: byLabel("Face top").id, label: "Overall thickness", nominal: 0.625, plusTol: 0.002, minusTol: 0.002, method: "Micrometer", deviceType: "MICROMETER", sequence: 3 },
      { planId: plan.id, featureId: byLabel("Outside profile").id, label: "Overall length", nominal: 5.875, plusTol: 0.005, minusTol: 0.005, method: "Calipers", deviceType: "DIGITAL_CALIPER", sequence: 4 },
    ],
  });

  /* ---------------- Reverse engineering demo session ---------------- */

  const bore = await db.metrologyDevice.findFirst({ where: { organizationId: org.id, deviceType: "BORE_GAUGE" } });

  const session = await db.measurementSession.create({
    data: {
      partRevisionId: rev.id,
      name: "Reverse engineering — original bearing support",
      mode: "REVERSE_ENGINEER",
      status: "IN_PROGRESS",
      operator: "Demo Operator",
      temperatureF: 68,
      notes: "Measurements taken from the worn original component.",
    },
  });

  // The demo measurement that exercises nominal reasoning: 1.5744 measured on
  // what is almost certainly a 40 mm (1.5748") bearing seat. Left PENDING so
  // the user makes the call, which is the entire point.
  await db.measurement.create({
    data: {
      sessionId: session.id,
      featureId: byLabel("40 mm bearing bore").id,
      deviceId: bore?.id,
      label: "Bearing bore diameter",
      measuredValue: 1.5744,
      units: "IN",
      uncertainty: 0.0002,
      repeatCount: 3,
      context: "BORE",
      resolution: "PENDING",
    },
  });

  await db.measurement.create({
    data: {
      sessionId: session.id,
      featureId: byLabel("Face top").id,
      label: "Overall thickness",
      measuredValue: 0.6247,
      units: "IN",
      uncertainty: 0.0002,
      repeatCount: 3,
      context: "THICKNESS",
      resolution: "PENDING",
    },
  });

  /* ---------------- A completed job with a real outcome ---------------- */

  const job = await db.job.create({
    data: {
      organizationId: org.id,
      partId: part.id,
      revision: "A",
      jobNumber: "J-1042",
      quantity: 10,
      status: "COMPLETE",
      startedAt: new Date(Date.now() - 6 * 864e5),
      completedAt: new Date(Date.now() - 5 * 864e5),
      actualCycleMinutes: 14.2,
      actualSetupHours: 2.1,
      scrapCount: 1,
      notes: "First run of Rev A.",
    },
  });

  await db.jobOutcome.create({
    data: {
      jobId: job.id,
      code: "PART_MOVED",
      cause: "Insufficient grip depth",
      correctiveAction: "Machine soft jaws with a 0.150\" seat for the second operation and reduce roughing engagement to 30%.",
      partsAffected: 1,
      notes: "Part shifted during the profile pass in Setup 2. This is the failure the workholding model now flags up front.",
      recordedBy: "Demo Operator",
    },
  });

  await db.manufacturingDNA.create({
    data: {
      partId: part.id,
      revision: "A",
      jobId: job.id,
      snapshotJson: json({ setups: 2, machine: "Haas VF-2", workholding: '6" vise', tools: [1, 2, 3, 5, 6, 7, 9] }),
      actualResultsJson: json({ cycleMinutes: 14.2, setupHours: 2.1, scrap: 1, outcome: "PART_MOVED" }),
      costActual: 41.8,
    },
  });

  /* ================================================================ */
  /* TRAINING SHOP — Basic Plate                                      */
  /* ================================================================ */
  // A practice part, isolated from production: `training: true` makes the
  // NC export mint refuse it server-side. It arrives with geometry and no
  // stock, no setups, no plan — the point is to walk the whole sequence.
  const trainingPart = await db.part.create({
    data: {
      organizationId: org.id,
      name: "Training — Basic Plate",
      partNumber: "TRAIN-001",
      description:
        "Training project. Practise stock, setup, workholding, toolpaths, simulation and gates. No production NC export.",
      sharing: "PRIVATE",
      isDemo: true,
      training: true,
    },
  });
  const trainingIntent = {
    partName: p("Training — Basic Plate", "USER", "VERIFIED", true),
    description: p("Practice plate: face, pocket, two holes, chamfer.", "USER", "VERIFIED", true),
    units: p("IN", "USER", "VERIFIED", true),
    material: p("Aluminum 6061", "USER", "VERIFIED", true),
    materialCondition: nullField("Choose during the lesson"),
    stock: nullField("Defining stock is the first lesson"),
    finishedEnvelope: p({ x: 4, y: 3, z: 0.5 }, "CALCULATED", "MEDIUM", false),
    quantity: p(1, "USER", "VERIFIED", true),
    features: p(["Face top", "Practice pocket", "2 × corner holes", "Break edges"], "USER", "VERIFIED", true),
    criticalDimensions: p([], "USER", "HIGH", true),
    generalTolerance: p(0.005, "USER", "VERIFIED", true),
    criticalTolerances: p([], "USER", "HIGH", true),
    surfaceFinish: nullField(),
    application: p("Training project — nothing rides on it, which is the point", "USER", "VERIFIED", true),
    loadBearing: p(false, "USER", "VERIFIED", true),
    safetyCritical: p(false, "USER", "VERIFIED", true),
    failureConsequence: p("NONE", "USER", "VERIFIED", true),
    loadingType: nullField(),
    environment: nullField(),
    temperatureRange: nullField(),
    regulatoryRequirements: nullField(),
    inspectionRequirements: p([], "USER", "VERIFIED", true),
    productionIntent: p("PROTOTYPE", "USER", "VERIFIED", true),
    annualVolume: p(1, "USER", "VERIFIED", true),
    notes: p("Training project. NC export is refused server-side.", "USER", "VERIFIED", true),
    unknowns: [],
    confidence: 0.9,
  };
  const trainRev = await db.partRevision.create({
    data: {
      partId: trainingPart.id,
      revision: "A",
      status: "DRAFT",
      units: "IN",
      intentJson: json(trainingIntent),
      stockJson: null,
      notes: "Training revision — define stock and plan it yourself; the Guide will walk you through it.",
    },
  });
  await db.partResponsibilityProfile.create({ data: { partRevisionId: trainRev.id, productionIntent: "PROTOTYPE" } });
  const trainingFeatures = [
    { kind: "FACE", label: "Face top", functionalRole: "DATUM_FACE", critical: false, parameters: { depth: 0.05 }, orderIndex: 0 },
    { kind: "RECT_POCKET", label: "Practice pocket", functionalRole: "CLEARANCE", critical: false, parameters: { centerX: 0, centerY: 0, width: 2, length: 1.5, depth: 0.25, cornerRadius: 0.25, bottomRadius: 0, top: 0 }, orderIndex: 1 },
    { kind: "DRILLED_HOLE", label: "Corner hole 1", functionalRole: "MOUNTING_HOLE", critical: false, parameters: { centerX: -1.5, centerY: -1, diameter: 0.257, depth: 0.5, through: true, top: 0 }, orderIndex: 2 },
    { kind: "DRILLED_HOLE", label: "Corner hole 2", functionalRole: "MOUNTING_HOLE", critical: false, parameters: { centerX: 1.5, centerY: 1, diameter: 0.257, depth: 0.5, through: true, top: 0 }, orderIndex: 3 },
    { kind: "CHAMFER", label: "Break edges", functionalRole: "NONE", critical: false, parameters: { width: 0.02, angle: 45, applyTo: "OUTSIDE_TOP" }, orderIndex: 4 },
  ];
  for (const f of trainingFeatures) {
    await db.feature.create({
      data: {
        partRevisionId: trainRev.id,
        kind: f.kind,
        label: f.label,
        functionalRole: f.functionalRole,
        critical: f.critical,
        parametersJson: json(f.parameters),
        orderIndex: f.orderIndex,
      },
    });
  }

  /* ================================================================ */
  /* TURNING — demo lathe shop + CANVAS Demo Shaft                    */
  /* ================================================================ */
  const lathe = await db.latheMachine.create({
    data: {
      organizationId: org.id,
      manufacturer: "Generic",
      model: "2-Axis CNC Lathe (reference profile)",
      controller: "FANUC_STYLE",
      maxSwing: 16,
      maxTurningDiameter: 10,
      maxTurningLength: 20,
      spindleBore: 2.3,
      barCapacity: 2.0,
      chuckSize: 8,
      maxRPM: 4000,
      maxSpindlePower: 20,
      maxSpindleTorque: 120,
      xTravel: 8,
      zTravel: 22,
      turretStations: 12,
      hasTailstock: true,
      hasPartsCatcher: false,
      coolantTypes: json(["FLOOD"]),
      isReferenceProfile: true,
      notes: "Reference specifications for development. Confirm against your machine before running anything.",
    },
  });

  const chuck = await db.latheWorkholding.create({
    data: {
      organizationId: org.id,
      type: "THREE_JAW_CHUCK",
      description: '8" 3-jaw hydraulic chuck',
      chuckDiameter: 8,
      maxRPM: 4200,
      maxClampForceLbf: null, // deliberately unrecorded: the grip analysis must say so
      jawType: "TWO_PIECE",
      jawMaterial: "HARD",
      jawStroke: 0.24, // recorded from the chuck manual — sizes the soft-jaw preload ring
      serrated: true,
      minGripLength: 0.25,
      maxGripLength: 1.5,
      boreThroughDiameter: 2.06,
      notes: "Clamp force not recorded — measure the hydraulic setting; the grip gate stays honest until then.",
    },
  });
  await db.latheWorkholding.create({
    data: {
      organizationId: org.id, type: "SOFT_JAWS", description: "Aluminum soft jaw set (blanks)",
      jawMaterial: "SOFT_MACHINED", serrated: false, notes: "Bore to the grip diameter per setup.",
    },
  });
  await db.latheWorkholding.create({
    data: {
      organizationId: org.id, type: "COLLET", description: "5C-style collet system", colletType: "5C",
      colletRange: '1/16" – 1-1/16"', maxRPM: 5000, boreThroughDiameter: 1.06,
    },
  });

  const turningTools = [
    { station: "0101", toolClass: "OD_ROUGHING", description: "OD rough — CNMG 432", insertShape: "C", insertGrade: "P25", noseRadius: 0.031, handedness: "RH", surfaceSpeedMin: 400, surfaceSpeedMax: 900, feedPerRevMin: 0.008, feedPerRevMax: 0.02, maxDepthOfCut: 0.15 },
    { station: "0202", toolClass: "OD_FINISHING", description: "OD finish — VNMG 331", insertShape: "V", insertGrade: "P10", noseRadius: 0.015, handedness: "RH", surfaceSpeedMin: 500, surfaceSpeedMax: 1100, feedPerRevMin: 0.003, feedPerRevMax: 0.008 },
    { station: "0303", toolClass: "FACING", description: "Face tool — CNMG 432", insertShape: "C", noseRadius: 0.031, handedness: "RH", surfaceSpeedMin: 400, surfaceSpeedMax: 900, feedPerRevMin: 0.006, feedPerRevMax: 0.015 },
    { station: "0404", toolClass: "BORING_BAR", description: '5/8" steel boring bar — CCMT', barDiameter: 0.625, minBoreDiameter: 0.8, stickout: 3.0, surfaceSpeedMin: 350, surfaceSpeedMax: 800, feedPerRevMin: 0.004, feedPerRevMax: 0.01 },
    { station: "0505", toolClass: "GROOVING", description: '0.118" grooving insert', grooveWidth: 0.118, maxDepthOfCut: 0.25, surfaceSpeedMin: 300, surfaceSpeedMax: 600, feedPerRevMin: 0.002, feedPerRevMax: 0.005 },
    { station: "0606", toolClass: "THREADING", description: "60° external threading insert", surfaceSpeedMin: 200, surfaceSpeedMax: 400 },
    { station: "0707", toolClass: "PARTING", description: '0.125" cutoff blade', grooveWidth: 0.125, surfaceSpeedMin: 250, surfaceSpeedMax: 500, feedPerRevMin: 0.002, feedPerRevMax: 0.004 },
    { station: "0808", toolClass: "CENTER_DRILL", description: "#3 center drill", feedPerRevMin: 0.002, feedPerRevMax: 0.005 },
    { station: "0909", toolClass: "DRILL", description: '3/4" indexable drill', barDiameter: 0.75, feedPerRevMin: 0.004, feedPerRevMax: 0.01 },
  ];
  for (const t of turningTools) await db.turningTool.create({ data: { organizationId: org.id, ...t } });

  const shaftPart = await db.part.create({
    data: {
      organizationId: org.id,
      name: "CANVAS Demo Shaft",
      partNumber: "CNV-T001",
      description: "Turned demonstration shaft: bearing journal (metric nominal reasoning demo), shoulder, snap-ring groove, external thread, center drill, cutoff.",
      sharing: "PRIVATE",
      isDemo: true,
    },
  });
  const shaftIntent = {
    partName: p2("CANVAS Demo Shaft"), description: p2("Turned demo shaft"), units: p2("IN"),
    material: p2("Steel 4140"), materialCondition: nullField("Condition not stated"),
    stock: p2({ form: "ROUND", diameter: 2.0, length: 6.0 }),
    finishedEnvelope: p("{}", "CALCULATED", "LOW", false), quantity: p2(5),
    features: p2(["Front face", "Bearing journal", "Shoulder", "Snap-ring groove", "3/4-16 thread", "Center drill", "Cutoff"]),
    criticalDimensions: p2([]), generalTolerance: p2(0.005), criticalTolerances: p2([]),
    surfaceFinish: nullField(), application: p2("Demonstration shaft for the turning workspace"),
    loadBearing: nullField("Not yet answered"), safetyCritical: nullField("Not yet answered"),
    failureConsequence: nullField(), loadingType: nullField(), environment: nullField(),
    temperatureRange: nullField(), regulatoryRequirements: nullField(),
    inspectionRequirements: p2([]), productionIntent: p2("PROTOTYPE"), annualVolume: nullField(),
    notes: p2("Journal measures 1.5744 in — the nominal-reasoning demo suggests 40 mm and never applies it silently."),
    unknowns: [], confidence: 0.7,
  };
  const shaftRev = await db.partRevision.create({
    data: { partId: shaftPart.id, revision: "A", status: "DRAFT", units: "IN", intentJson: json(shaftIntent), stockJson: null },
  });
  await db.partResponsibilityProfile.create({ data: { partRevisionId: shaftRev.id, productionIntent: "PROTOTYPE" } });

  const shaftProfile = {
    units: "IN",
    zZeroReference: "Front face after facing",
    stockDiameter: 2.0,
    stockLength: 6.0,
    barStock: true,
    segments: [
      { id: "s1", kind: "FACE", label: "Front face", zStart: 0, zEnd: 0.001, diameterStart: 2.0, diameterEnd: 0, internal: false, functionalRole: "DATUM_FACE", critical: false, source: "USER", confirmedByUser: true },
      { id: "s2", kind: "CYLINDER", label: "Thread OD", zStart: 0, zEnd: 0.75, diameterStart: 0.75, diameterEnd: 0.75, internal: false, thread: "3/4-16 UNF-2A", functionalRole: "THREAD_EXTERNAL", critical: false, source: "MEASURED", confirmedByUser: false },
      { id: "s2t", kind: "THREAD", label: "3/4-16 UNF thread", zStart: 0, zEnd: 0.65, diameterStart: 0.75, diameterEnd: 0.75, internal: false, thread: "3/4-16 UNF-2A", functionalRole: "THREAD_EXTERNAL", critical: false, source: "MEASURED", confirmedByUser: false },
      { id: "s3", kind: "CYLINDER", label: "Bearing journal", zStart: 0.75, zEnd: 1.95, diameterStart: 1.5744, diameterEnd: 1.5744, internal: false, tolerancePlus: 0.0, toleranceMinus: 0.0005, surfaceFinish: 32, functionalRole: "BEARING_JOURNAL", critical: true, matingComponent: "6208-series bearing inner race", source: "MEASURED", confirmedByUser: false },
      { id: "s4", kind: "GROOVE", label: "Snap-ring groove", zStart: 1.95, zEnd: 2.068, diameterStart: 1.5744, diameterEnd: 1.472, internal: false, functionalRole: "SNAP_RING_GROOVE", critical: false, source: "MEASURED", confirmedByUser: false },
      { id: "s5", kind: "CYLINDER", label: "Body OD", zStart: 2.068, zEnd: 4.6, diameterStart: 1.85, diameterEnd: 1.85, internal: false, functionalRole: "STRUCTURAL_SHAFT_SECTION", critical: false, source: "MEASURED", confirmedByUser: false },
      { id: "s6", kind: "SHOULDER", label: "Locating shoulder", zStart: 2.068, zEnd: 2.068, diameterStart: 1.5744, diameterEnd: 1.85, internal: false, functionalRole: "LOCATING_SHOULDER", critical: true, source: "MEASURED", confirmedByUser: false },
      { id: "s7", kind: "CUTOFF", label: "Cutoff", zStart: 4.6, zEnd: 4.6, diameterStart: 1.85, diameterEnd: 0, internal: false, functionalRole: "PART_OFF_FACE", critical: false, source: "CALCULATED", confirmedByUser: false },
    ],
  };
  const shaftPlan = [
    { operationNumber: 10, type: "FACE", label: "Face front", toolStation: "0303", targetSegmentId: "s1", startZ: 0.05, endZ: 0, startDiameter: 2.0, endDiameter: 0, params: { feedPerRev: 0.008, surfaceSpeed: 600, rpm: 3000, cssEnabled: true, doc: 0.05, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
    { operationNumber: 20, type: "OD_ROUGH", label: "OD rough to Ø1.87 envelope", toolStation: "0101", targetSegmentId: "s5", startZ: 0, endZ: 4.6, startDiameter: 2.0, endDiameter: 1.87, params: { feedPerRev: 0.012, surfaceSpeed: 550, rpm: 3000, cssEnabled: true, doc: 0.08, finishAllowance: 0.01, springPasses: 0, coolant: "FLOOD" } },
    { operationNumber: 30, type: "OD_FINISH", label: "Finish bearing journal", toolStation: "0202", targetSegmentId: "s3", startZ: 0.75, endZ: 1.95, startDiameter: 1.6, endDiameter: 1.5744, params: { feedPerRev: 0.004, surfaceSpeed: 700, rpm: 3200, cssEnabled: true, doc: 0.01, finishAllowance: 0, springPasses: 1, coolant: "FLOOD" } },
    { operationNumber: 40, type: "GROOVE_OD", label: "Snap-ring groove", toolStation: "0505", targetSegmentId: "s4", startZ: 1.95, endZ: 2.068, startDiameter: 1.5744, endDiameter: 1.472, params: { feedPerRev: 0.003, surfaceSpeed: null, rpm: 900, cssEnabled: false, doc: 0.05, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
    { operationNumber: 50, type: "CENTER_DRILL", label: "Center drill tail end", toolStation: "0808", targetSegmentId: null, startZ: 4.6, endZ: 4.35, startDiameter: 0, endDiameter: 0, params: { feedPerRev: 0.003, surfaceSpeed: null, rpm: 1500, cssEnabled: false, doc: 0.1, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
    // Break the thread entry before single-pointing it — the chamfer both
    // starts the die/nut square and exercises the chamfer engine, whose
    // uncompensated-nose-radius warning the workspace shows on selection.
    { operationNumber: 55, type: "CHAMFER", label: "Chamfer thread entry 1/32 x 45", toolStation: "0202", targetSegmentId: "s2", startZ: 0, endZ: 0.031, startDiameter: 0.688, endDiameter: 0.75, params: { feedPerRev: 0.004, surfaceSpeed: 700, rpm: 3200, cssEnabled: true, doc: 0.01, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
    { operationNumber: 60, type: "THREAD_OD", label: "Thread 3/4-16 UNF", toolStation: "0606", targetSegmentId: "s2t", startZ: 0, endZ: 0.65, startDiameter: 0.75, endDiameter: 0.75, params: { feedPerRev: 0.0625, surfaceSpeed: null, rpm: 800, cssEnabled: false, doc: 0.012, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
    { operationNumber: 70, type: "PART_OFF", label: "Part off at Z4.600", toolStation: "0707", targetSegmentId: "s7", startZ: 4.6, endZ: 4.6, startDiameter: 1.85, endDiameter: 0, params: { feedPerRev: 0.003, surfaceSpeed: null, rpm: 700, cssEnabled: false, doc: 0.05, finishAllowance: 0, springPasses: 0, coolant: "FLOOD" } },
  ];
  await db.rotationalPart.create({
    data: {
      partRevisionId: shaftRev.id,
      organizationId: org.id,
      profileJson: json(shaftProfile),
      planJson: json(shaftPlan),
      latheMachineId: lathe.id,
      workholdingId: chuck.id,
      gripLength: 1.0,
      stickout: 4.7,
      clampForceLbf: null,
      tailstockActive: false,
      maxRpmClamp: 3000,
    },
  });

  console.log(`Seeded organisation ${org.name}`);
  console.log("  Sign in: demo@canvas.local / canvas-demo");
  console.log(`  Part: ${part.name} (${part.partNumber}) Rev A — ${features.length} features, 2 setups`);
}

/**
 * Removes an organisation and everything under it, in dependency order.
 *
 * A plain cascade from Organization does not work, and the reason is worth
 * recording: Setup points at both PartRevision (cascade) and Machine (set
 * null). Deleting the organisation triggers both paths, and PostgreSQL may run
 * the SET NULL update against Setup rows whose PartRevision the other path has
 * already deleted — which re-validates the cascade FK and fails. Deleting the
 * dependent rows first removes the ambiguity entirely, and is provider
 * independent besides.
 */
async function teardownOrganization(slug: string) {
  const org = await db.organization.findUnique({ where: { slug }, select: { id: true } });
  if (!org) return;

  await db.operation.deleteMany({ where: { setup: { partRevision: { part: { organizationId: org.id } } } } });
  await db.jaw.deleteMany({ where: { setup: { partRevision: { part: { organizationId: org.id } } } } });
  await db.simulation.deleteMany({ where: { setup: { partRevision: { part: { organizationId: org.id } } } } });
  await db.setup.deleteMany({ where: { partRevision: { part: { organizationId: org.id } } } });
  await db.measurement.deleteMany({ where: { session: { partRevision: { part: { organizationId: org.id } } } } });
  await db.organization.delete({ where: { id: org.id } });
}

/* Provenance helpers, mirrored from src/lib/provenance.ts. */
function p2(value: unknown) {
  return p(value, "USER", "VERIFIED", true);
}
function p(value: unknown, source: string, confidence: string, confirmedByUser: boolean) {
  return { value, source, confidence, confirmedByUser };
}
function nullField(note?: string) {
  return { value: null, source: "DEFAULT", confidence: "UNKNOWN", confirmedByUser: false, note };
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => db.$disconnect());
