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
    { toolNumber: 5, toolClass: "SPOT_DRILL", description: '1/2" 90° spot drill', diameter: 0.5, flutes: 2, material: "CARBIDE", coating: "TiN", fluteLength: 0.4, overallLength: 2.5, stickout: 1, holderId: cat40.id, maxRPM: 6000, chiploadMin: 0.002, chiploadMax: 0.004, sfmMin: 250, sfmMax: 400, costPerTool: 30, expectedLifeMinutes: 400 },
    { toolNumber: 6, toolClass: "DRILL", description: '#7 (0.201") carbide drill', diameter: 0.201, flutes: 2, material: "CARBIDE", coating: "TiAlN", fluteLength: 1.5, overallLength: 3, stickout: 1.9, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.003, chiploadMax: 0.006, sfmMin: 250, sfmMax: 400, costPerTool: 24, expectedLifeMinutes: 180 },
    { toolNumber: 7, toolClass: "CHAMFER_MILL", description: '1/2" 90° chamfer mill', diameter: 0.5, flutes: 4, material: "CARBIDE", coating: "TiAlN", fluteLength: 0.5, overallLength: 2.5, stickout: 1.1, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 500, sfmMax: 900, costPerTool: 38, expectedLifeMinutes: 300 },
    { toolNumber: 8, toolClass: "ENGRAVER", description: '1/8" 60° engraving tool', diameter: 0.125, flutes: 1, material: "CARBIDE", fluteLength: 0.25, overallLength: 2, stickout: 0.8, holderId: cat40.id, maxRPM: 8100, chiploadMin: 0.0005, chiploadMax: 0.0015, sfmMin: 300, sfmMax: 600, costPerTool: 18, expectedLifeMinutes: 300 },
    { toolNumber: 9, toolClass: "BORING_TOOL", description: '1.0"–2.0" adjustable boring head', diameter: 1.5748, flutes: 1, material: "CARBIDE", fluteLength: 0.75, overallLength: 4, stickout: 2.2, holderId: cat40.id, maxRPM: 2000, chiploadMin: 0.001, chiploadMax: 0.003, sfmMin: 400, sfmMax: 700, costPerTool: 260, expectedLifeMinutes: 600 },
    { toolNumber: 10, toolClass: "TAP", description: "1/4-20 spiral point tap", diameter: 0.25, flutes: 3, material: "HSS", coating: "TiN", fluteLength: 1, overallLength: 2.5, stickout: 1.5, holderId: cat40.id, maxRPM: 4000, chiploadMin: 0.001, chiploadMax: 0.002, sfmMin: 30, sfmMax: 60, costPerTool: 14, expectedLifeMinutes: 500 },
  ];

  for (const t of tools) {
    await db.tool.create({
      data: {
        organizationId: org.id,
        cornerRadius: 0,
        recommendedMaterials: json(["Aluminum 6061", "Aluminum 7075", "Brass 360"]),
        coolant: "FLOOD",
        lifeRemaining: 1,
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
  ];
  for (const d of metrology) await db.metrologyDevice.create({ data: { organizationId: org.id, ...d } });

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
      // Grip is deliberately marginal here: this is what makes the demo's
      // workholding assessment produce a real HIGH RISK finding rather than a
      // rubber stamp.
      gripDepth: 0.08,
      gripLength: 3.875,
      stockProjection: 0.545,
      parallelHeight: 0.5,
      notes:
        "Requires soft jaws — the finished profile has no square stock left to grip and the remaining wall is thin.",
    },
  });

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
