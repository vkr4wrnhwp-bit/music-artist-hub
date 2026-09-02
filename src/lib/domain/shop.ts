import type { ToolCondition } from "@/lib/engines/cutting-force";

/**
 * Shop resource models — machines, tooling, workholding, materials and
 * metrology. These are the hard constraints CANVAS validates against. Nothing
 * in here is ever invented by the AI layer: if a machine or tool is not in the
 * shop, the planner treats it as unavailable rather than assuming it exists.
 */

/* ------------------------------------------------------------------ */
/* Machines                                                            */
/* ------------------------------------------------------------------ */

export const MACHINE_TYPES = [
  "VMC_3AXIS",
  "VMC_4AXIS",
  "VMC_5AXIS",
  "HMC",
  "LATHE",
  "MILL_TURN",
  "ROUTER",
  "WIRE_EDM",
  "SINKER_EDM",
  "LASER",
  "WATERJET",
  "PRESS_BRAKE",
  "ADDITIVE_METAL",
  "ADDITIVE_POLYMER",
] as const;
export type MachineType = (typeof MACHINE_TYPES)[number];

export const CONTROLLERS = [
  "HAAS_NGC",
  "HAAS_CLASSIC",
  "FANUC",
  "SIEMENS_840D",
  "HEIDENHAIN_TNC",
  "PATHPILOT",
  "GRBL",
  "MAZATROL",
  "OKUMA_OSP",
  "OTHER",
] as const;
export type Controller = (typeof CONTROLLERS)[number];

export interface MachineProfile {
  id: string;
  manufacturer: string;
  model: string;
  controller: Controller;
  machineType: MachineType;
  axisCount: number;
  travelsX: number;
  travelsY: number;
  travelsZ: number;
  tableX: number;
  tableY: number;
  maxSpindleRPM: number;
  /** Peak spindle power, hp. */
  maxSpindlePower: number;
  /** Peak spindle torque, lb-ft. */
  maxSpindleTorque: number;
  maxFeed: number;
  maxRapid: number;
  /** Axis acceleration, in/s². Null when not recorded — never defaulted. */
  axisAccel: number | null;
  toolChangerCapacity: number;
  maxToolDiameter: number;
  maxToolLength: number;
  maxToolWeight: number;
  coolantTypes: string[];
  throughSpindleCoolant: boolean;
  probe: boolean;
  toolSetter: boolean;
  fourthAxis: boolean;
  fifthAxis: boolean;
  supportedPostProcessor: string;
  /** Marks demo/reference profiles so the UI never presents them as verified. */
  isReferenceProfile: boolean;
  notes?: string;
}

export interface EnvelopeCheck {
  fits: boolean;
  reasons: string[];
  clearanceX: number;
  clearanceY: number;
  clearanceZ: number;
}

/**
 * Envelope check accounts for the workholding stack — a 4" tall part in a 5"
 * vise on a machine with 20" of Z travel is not automatically fine.
 */
export function checkEnvelope(
  machine: MachineProfile,
  stock: { x: number; y: number; z: number },
  fixtureHeight = 0,
  toolStackHeight = 0,
): EnvelopeCheck {
  const reasons: string[] = [];
  const clearanceX = machine.travelsX - stock.x;
  const clearanceY = machine.travelsY - stock.y;
  const requiredZ = stock.z + fixtureHeight + toolStackHeight;
  const clearanceZ = machine.travelsZ - requiredZ;

  if (clearanceX < 0) reasons.push(`Stock X ${stock.x}" exceeds ${machine.travelsX}" X travel`);
  if (clearanceY < 0) reasons.push(`Stock Y ${stock.y}" exceeds ${machine.travelsY}" Y travel`);
  if (clearanceZ < 0)
    reasons.push(
      `Stock + fixture + tool stack ${requiredZ.toFixed(2)}" exceeds ${machine.travelsZ}" Z travel`,
    );
  if (stock.x > machine.tableX || stock.y > machine.tableY)
    reasons.push("Stock footprint exceeds table dimensions");

  return { fits: reasons.length === 0, reasons, clearanceX, clearanceY, clearanceZ };
}

/* ------------------------------------------------------------------ */
/* Tooling                                                             */
/* ------------------------------------------------------------------ */

export const TOOL_CLASSES = [
  "FACE_MILL",
  "FLAT_END_MILL",
  "BALL_END_MILL",
  "BULL_NOSE",
  "DRILL",
  "CENTER_DRILL",
  "SPOT_DRILL",
  "REAMER",
  "BORING_TOOL",
  "THREAD_MILL",
  "TAP",
  "CHAMFER_MILL",
  "COUNTERSINK",
  "DOVETAIL",
  "ENGRAVER",
  "SLITTING_SAW",
  "SHELL_MILL",
] as const;
export type ToolClass = (typeof TOOL_CLASSES)[number];

export interface Tool {
  id: string;
  toolNumber: number;
  toolClass: ToolClass;
  manufacturer?: string;
  product?: string;
  description: string;
  diameter: number;
  cornerRadius: number;
  flutes: number;
  material: "HSS" | "COBALT" | "CARBIDE" | "CERAMIC" | "DIAMOND";
  coating?: string;
  fluteLength: number;
  overallLength: number;
  stickout: number;
  holder: string;
  /** Holder body diameter at the nose — used for holder clearance checks. */
  holderNoseDiameter: number;
  holderTaperAngle?: number;
  maxRPM: number;
  recommendedMaterials: string[];
  /** in/tooth, per material class. */
  chiploadMin: number;
  chiploadMax: number;
  /** SFM. */
  sfmMin: number;
  sfmMax: number;
  coolant: string;
  /** 0–1 remaining life estimate. */
  lifeRemaining: number;
  notes?: string;

  /* ---- Tool reality: what is in the holder, not what the catalogue said ---- */

  /** NEW | GOOD | WORN | REGRIND | UNKNOWN. Feeds the cutting force model. */
  condition: ToolCondition;
  /** Stickout as actually set, when it has been measured. */
  actualStickout?: number;
  /** Measured runout, inches. */
  measuredRunout?: number;
  helixAngle?: number;
  regrindCount: number;
  /** Last material this cutter was run in — relevant to contamination and wear. */
  previousMaterial?: string;
  lastUsedAt?: Date;
  /** Shop-specific observations. SHOP_KNOWLEDGE, never universal fact. */
  shopNotes?: string;
}

/** Effective cutting reach below the holder nose. */
export function toolReach(tool: Tool): number {
  return tool.stickout;
}

/**
 * The reach rule itself, separated from the Tool record.
 *
 * An uploaded NC program has a stickout figure from the crib and a depth read
 * off the program, and no Tool object. review.ts already hand-copies the
 * 0.100" clearance with a comment saying it must match this file; a third
 * copy in the NC layer would be a third chance to drift.
 */
export function reachesDepth(stickout: number, depth: number, clearance = REACH_CLEARANCE): boolean {
  return stickout >= depth + clearance;
}

/** Clearance between the deepest cut and the end of the stickout, inches. */
export const REACH_CLEARANCE = 0.1;

export function canReach(tool: Tool, depth: number, clearance = REACH_CLEARANCE): boolean {
  return reachesDepth(toolReach(tool), depth, clearance);
}

/** A tool can produce an internal corner only if its radius fits inside it. */
export function fitsInternalCorner(tool: Tool, cornerRadius: number): boolean {
  return tool.diameter / 2 <= cornerRadius + 1e-6;
}

/* ------------------------------------------------------------------ */
/* Workholding                                                         */
/* ------------------------------------------------------------------ */

export const WORKHOLDING_TYPES = [
  "VISE",
  "SOFT_JAWS",
  "HARD_JAWS",
  "DOVETAIL_FIXTURE",
  "FIXTURE_PLATE",
  "TOE_CLAMPS",
  "STRAP_CLAMPS",
  "VACUUM",
  "MAGNETIC",
  "CUSTOM_FIXTURE",
  "CHUCK",
  "PALLET",
] as const;
export type WorkholdingType = (typeof WORKHOLDING_TYPES)[number];

export interface WorkholdingDevice {
  id: string;
  type: WorkholdingType;
  manufacturer?: string;
  model?: string;
  description: string;
  jawWidth: number;
  jawHeight: number;
  maxOpening: number;
  /** lbf at nominal handle torque, if the manufacturer publishes it. */
  clampForce?: number;
  /** Height from table to top of jaws — feeds the Z envelope check. */
  fixtureHeight: number;
  mountingGeometry?: string;
  hasCadRepresentation: boolean;
  notes?: string;
}

export interface JawBlank {
  id: string;
  material: "ALUMINUM_6061" | "STEEL_1018" | "CAST_IRON";
  width: number;
  height: number;
  thickness: number;
  boltPattern: string;
}

/* ------------------------------------------------------------------ */
/* Materials                                                           */
/* ------------------------------------------------------------------ */

export interface MaterialProfile {
  id: string;
  name: string;
  family: "ALUMINUM" | "STEEL" | "STAINLESS" | "TITANIUM" | "BRASS" | "PLASTIC" | "COMPOSITE" | "OTHER";
  condition: string;
  /** lb/in³ */
  density: number;
  /** Brinell */
  hardness?: number;
  /** ksi */
  yieldStrength?: number;
  tensileStrength?: number;
  machinabilityRating: number; // % of B1112 free-machining steel
  /** SFM window for carbide tooling. */
  sfmCarbideMin: number;
  sfmCarbideMax: number;
  /** $/lb, shop's own purchase price. */
  costPerPound: number;
  weldable: boolean;
  castable: boolean;
  notes?: string;
}

/* ------------------------------------------------------------------ */
/* Metrology                                                           */
/* ------------------------------------------------------------------ */

export const METROLOGY_DEVICES = [
  "TAPE_RULE",
  "DIGITAL_CALIPER",
  "VERNIER_CALIPER",
  "MICROMETER",
  "DEPTH_MICROMETER",
  // Added because inspection-capability.ts already reasoned about one.
  // INSIDE_MICROMETER sat in both MEASURES_INTERNAL_ROUND and
  // MEASURES_INTERNAL_FLAT while being absent from this list, so no shop
  // could ever record one and those two entries could never match anything.
  // The engine was reasoning about an instrument the data model could not
  // hold — which reads as support for inside mics and delivers none.
  "INSIDE_MICROMETER",
  "BORE_GAUGE",
  "TELESCOPING_GAUGE",
  "PIN_GAUGE",
  "GAUGE_BLOCK",
  "HEIGHT_GAUGE",
  "SURFACE_PLATE",
  "DIAL_INDICATOR",
  "TEST_INDICATOR",
  "SINE_BAR",
  "OPTICAL_COMPARATOR",
  "CMM",
  "PORTABLE_CMM",
  "STRUCTURED_LIGHT_SCANNER",
  "LASER_SCANNER",
  "MACHINE_PROBE",
] as const;
export type MetrologyDeviceType = (typeof METROLOGY_DEVICES)[number];

export interface MetrologyDevice {
  id: string;
  deviceType: MetrologyDeviceType;
  description: string;
  rangeMin?: number;
  rangeMax?: number;
  /** Instrument resolution, inches. */
  resolution: number;
  /** Realistic achievable uncertainty in shop conditions, inches. */
  uncertainty: number;
  calibrated: boolean;
  calibrationDue?: string;
}

/**
 * Instruments that produce a 3D mesh, and can therefore be named as the
 * source of a scan import.
 *
 * Typed as MetrologyDeviceType[] so a rename in the vocabulary breaks this
 * rather than silently emptying the scanner list — an import that quietly
 * says "no scanning instrument on file" for a shop that owns one is a
 * confusing dead end, not a safe default.
 */
export const SCANNING_INSTRUMENTS: readonly MetrologyDeviceType[] = [
  "STRUCTURED_LIGHT_SCANNER",
  "LASER_SCANNER",
  "PORTABLE_CMM",
  "CMM",
];

export const isScanningInstrument = (t: string): boolean =>
  (SCANNING_INSTRUMENTS as readonly string[]).includes(t);

export const METROLOGY_LABELS: Record<MetrologyDeviceType, string> = {
  TAPE_RULE: "Tape / steel rule",
  DIGITAL_CALIPER: "Digital calipers",
  VERNIER_CALIPER: "Vernier calipers",
  MICROMETER: "Micrometer",
  DEPTH_MICROMETER: "Depth micrometer",
  INSIDE_MICROMETER: "Inside micrometer",
  BORE_GAUGE: "Bore gauge",
  TELESCOPING_GAUGE: "Telescoping gauge",
  PIN_GAUGE: "Pin gauges",
  GAUGE_BLOCK: "Gauge blocks",
  HEIGHT_GAUGE: "Height gauge",
  SURFACE_PLATE: "Surface plate",
  DIAL_INDICATOR: "Dial indicator",
  TEST_INDICATOR: "Test indicator",
  SINE_BAR: "Sine bar",
  OPTICAL_COMPARATOR: "Optical comparator",
  CMM: "CMM",
  PORTABLE_CMM: "Portable CMM / arm",
  STRUCTURED_LIGHT_SCANNER: "Structured light scanner",
  LASER_SCANNER: "Laser scanner",
  MACHINE_PROBE: "Machine spindle probe",
};

/** Typical achievable uncertainty by device, inches. Used to rank instruments. */
export const DEVICE_UNCERTAINTY: Record<MetrologyDeviceType, number> = {
  TAPE_RULE: 0.03,
  DIGITAL_CALIPER: 0.002,
  VERNIER_CALIPER: 0.003,
  MICROMETER: 0.0002,
  DEPTH_MICROMETER: 0.0005,
  INSIDE_MICROMETER: 0.0003,
  BORE_GAUGE: 0.0002,
  TELESCOPING_GAUGE: 0.001,
  PIN_GAUGE: 0.0002,
  GAUGE_BLOCK: 0.00005,
  HEIGHT_GAUGE: 0.001,
  SURFACE_PLATE: 0.0001,
  DIAL_INDICATOR: 0.001,
  TEST_INDICATOR: 0.0002,
  SINE_BAR: 0.0005,
  OPTICAL_COMPARATOR: 0.0005,
  CMM: 0.0001,
  PORTABLE_CMM: 0.0015,
  STRUCTURED_LIGHT_SCANNER: 0.002,
  LASER_SCANNER: 0.003,
  MACHINE_PROBE: 0.0005,
};
