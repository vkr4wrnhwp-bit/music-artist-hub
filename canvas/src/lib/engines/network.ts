import type { Feature, Stock } from "@/lib/domain/features";
import type { PartIntent } from "@/lib/domain/part-intent";

/**
 * MANUFACTURING NETWORK — ARCHITECTED NOW, NOT RELEASED
 *
 * The network layer is the long-term reason CANVAS is valuable, and it is also
 * the single easiest thing to get catastrophically wrong. A shop's part
 * geometry is its livelihood. So the privacy model is built first and the
 * matching is built on top of it, never the other way round.
 *
 * Rules enforced here:
 *   - PRIVATE is the default and nothing leaves the organisation.
 *   - A fingerprint is lossy by construction: bands, families and classes,
 *     never dimensions, never names, never text, never geometry.
 *   - Identity is never attached to a fingerprint. Introductions happen only
 *     through an explicit, per-request consent step.
 *
 * See /docs/NETWORK_PRIVACY.md.
 */

export const SHARING_LEVELS = ["PRIVATE", "ANONYMOUS_LEARNING", "NETWORK_MATCH", "MARKETPLACE"] as const;
export type SharingLevel = (typeof SHARING_LEVELS)[number];

export const SHARING_DESCRIPTION: Record<SharingLevel, string> = {
  PRIVATE: "Nothing about this part leaves your organisation. This is the default.",
  ANONYMOUS_LEARNING:
    "Anonymised manufacturing outcomes — what held, what chattered, what scrapped — contribute to CANVAS's models. No geometry, no dimensions, no identity.",
  NETWORK_MATCH:
    "An anonymous fingerprint may be compared against other opted-in shops to surface supplier or demand matches. Identity is only revealed if you accept an introduction.",
  MARKETPLACE: "This part may be listed for quoting by network suppliers. Requires explicit per-part opt-in.",
};

/** Coarse bands. Anything finer starts to reconstruct the actual part. */
export type Band = "XS" | "S" | "M" | "L" | "XL";

export interface ManufacturingFingerprint {
  /** Never contains an org id, part name, or any free text. */
  geometryFamily: "PRISMATIC_PLATE" | "PRISMATIC_BLOCK" | "ROTATIONAL" | "THIN_WALL" | "COMPLEX";
  processFamily: "MILL_3AXIS" | "MILL_MULTIAXIS" | "TURN" | "TURN_MILL" | "FABRICATION" | "ADDITIVE";
  materialFamily: string;
  envelopeBand: Band;
  featureTypes: string[];
  bearingInterfaces: number;
  fastenerInterfaces: number;
  toleranceClass: "COARSE" | "STANDARD" | "PRECISION" | "HIGH_PRECISION";
  surfaceFinishClass: "AS_MACHINED" | "FINE" | "GROUND" | "POLISHED";
  quantityBand: "ONE_OFF" | "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH";
  machineClass: "BENCHTOP" | "STANDARD_VMC" | "LARGE_VMC" | "HMC" | "MULTIAXIS";
  complexity: Band;
  workholdingClass: "VISE" | "SOFT_JAWS" | "FIXTURE_PLATE" | "DOVETAIL" | "CUSTOM" | "VACUUM";
  operationSequence: string[];
  /** Number of setups. A useful matching signal that reveals nothing. */
  setupCount: number;
}

export interface FingerprintInput {
  intent: PartIntent;
  stock: Stock | null;
  features: Feature[];
  setupCount: number;
  workholdingType: string | null;
  machineTravelX: number | null;
  operationTypes: string[];
}

function envelopeBand(stock: Stock | null): Band {
  if (!stock) return "M";
  const max = Math.max(stock.x, stock.y, stock.z);
  if (max <= 2) return "XS";
  if (max <= 6) return "S";
  if (max <= 14) return "M";
  if (max <= 30) return "L";
  return "XL";
}

function quantityBand(q: number | null): ManufacturingFingerprint["quantityBand"] {
  if (q === null) return "ONE_OFF";
  if (q <= 1) return "ONE_OFF";
  if (q <= 25) return "LOW";
  if (q <= 250) return "MEDIUM";
  if (q <= 5000) return "HIGH";
  return "VERY_HIGH";
}

function toleranceClass(t: number | null): ManufacturingFingerprint["toleranceClass"] {
  if (t === null) return "STANDARD";
  if (t >= 0.01) return "COARSE";
  if (t >= 0.003) return "STANDARD";
  if (t >= 0.0005) return "PRECISION";
  return "HIGH_PRECISION";
}

function geometryFamily(stock: Stock | null, features: Feature[]): ManufacturingFingerprint["geometryFamily"] {
  if (!stock) return "COMPLEX";
  if (stock.form === "ROUND") return "ROTATIONAL";
  const thin = stock.z <= Math.min(stock.x, stock.y) * 0.25;
  if (features.length > 20) return "COMPLEX";
  return thin ? "PRISMATIC_PLATE" : "PRISMATIC_BLOCK";
}

/**
 * Builds the anonymous fingerprint. Note what is absent: no part name, no
 * customer, no dimension, no tolerance value, no feature label, no notes.
 */
export function buildFingerprint(input: FingerprintInput): ManufacturingFingerprint {
  const { intent, stock, features } = input;

  const bearingInterfaces = features.filter((f) => f.functionalRole === "BEARING_SEAT" || f.functionalRole === "SHAFT_JOURNAL").length;
  const fastenerInterfaces = features.filter((f) => f.functionalRole === "MOUNTING_HOLE" || f.functionalRole === "THREAD").length;

  const materialFamily = (intent.material.value ?? "UNKNOWN").split(/\s+/)[0].toUpperCase();

  const complexityScore = features.length + input.setupCount * 3 + bearingInterfaces * 2;
  const complexity: Band = complexityScore <= 5 ? "XS" : complexityScore <= 12 ? "S" : complexityScore <= 25 ? "M" : complexityScore <= 45 ? "L" : "XL";

  return {
    geometryFamily: geometryFamily(stock, features),
    processFamily: "MILL_3AXIS",
    materialFamily,
    envelopeBand: envelopeBand(stock),
    featureTypes: [...new Set(features.map((f) => f.kind))].sort(),
    bearingInterfaces,
    fastenerInterfaces,
    toleranceClass: toleranceClass(intent.generalTolerance.value),
    surfaceFinishClass: "AS_MACHINED",
    quantityBand: quantityBand(intent.annualVolume.value ?? intent.quantity.value),
    machineClass:
      input.machineTravelX === null ? "STANDARD_VMC" : input.machineTravelX < 16 ? "BENCHTOP" : input.machineTravelX < 40 ? "STANDARD_VMC" : "LARGE_VMC",
    complexity,
    workholdingClass: (input.workholdingType as ManufacturingFingerprint["workholdingClass"]) ?? "VISE",
    operationSequence: input.operationTypes,
    setupCount: input.setupCount,
  };
}

/**
 * Audit helper. Every field a fingerprint carries is enumerated here so the
 * privacy page can show the user exactly what would leave — and so a reviewer
 * can spot a field that should never have been added.
 */
export function describeFingerprintDisclosure(fp: ManufacturingFingerprint): { field: string; value: string; risk: "NONE" | "LOW" }[] {
  return [
    { field: "Geometry family", value: fp.geometryFamily, risk: "NONE" },
    { field: "Process family", value: fp.processFamily, risk: "NONE" },
    { field: "Material family", value: fp.materialFamily, risk: "NONE" },
    { field: "Envelope band", value: fp.envelopeBand, risk: "LOW" },
    { field: "Feature types", value: fp.featureTypes.join(", ") || "—", risk: "LOW" },
    { field: "Bearing interfaces", value: String(fp.bearingInterfaces), risk: "NONE" },
    { field: "Fastener interfaces", value: String(fp.fastenerInterfaces), risk: "NONE" },
    { field: "Tolerance class", value: fp.toleranceClass, risk: "NONE" },
    { field: "Quantity band", value: fp.quantityBand, risk: "LOW" },
    { field: "Machine class", value: fp.machineClass, risk: "NONE" },
    { field: "Complexity band", value: fp.complexity, risk: "NONE" },
    { field: "Workholding class", value: fp.workholdingClass, risk: "NONE" },
    { field: "Setup count", value: String(fp.setupCount), risk: "NONE" },
  ];
}

/* ------------------------------------------------------------------ */
/* Job outcomes — the collective intelligence input                    */
/* ------------------------------------------------------------------ */

export const JOB_OUTCOMES = [
  "SUCCESS",
  "PART_MOVED",
  "CHATTER",
  "TOOL_BREAK",
  "POOR_FINISH",
  "OUT_OF_TOLERANCE",
  "WORKHOLDING_FAILURE",
  "WARPED",
  "COLLISION",
  "OTHER",
] as const;
export type JobOutcomeCode = (typeof JOB_OUTCOMES)[number];

export const OUTCOME_LABEL: Record<JobOutcomeCode, string> = {
  SUCCESS: "Success",
  PART_MOVED: "Part moved in the fixture",
  CHATTER: "Chatter",
  TOOL_BREAK: "Tool breakage",
  POOR_FINISH: "Poor surface finish",
  OUT_OF_TOLERANCE: "Out of tolerance",
  WORKHOLDING_FAILURE: "Workholding failure",
  WARPED: "Part warped",
  COLLISION: "Collision",
  OTHER: "Other",
};

export interface JobOutcomeRecord {
  code: JobOutcomeCode;
  operationId: string | null;
  toolNumber: number | null;
  /** Structured cause, chosen from a list rather than typed free-form. */
  cause: string;
  correctiveAction: string;
  partsAffected: number;
  notes: string;
}

/** Cause options presented per outcome, so the data stays analysable. */
export const OUTCOME_CAUSES: Record<JobOutcomeCode, string[]> = {
  SUCCESS: ["—"],
  PART_MOVED: ["Insufficient grip depth", "Clamping force too low", "Cutting load too high", "Burr under part", "Coolant on jaw faces"],
  CHATTER: ["Excessive stickout", "Radial engagement too high", "Speed in a resonant band", "Insufficient part support", "Worn tool"],
  TOOL_BREAK: ["Feed too high", "Chip evacuation failure", "Recut of chips", "Tool worn past life", "Programming error"],
  POOR_FINISH: ["Feed too high for the finish pass", "Worn tool", "Chatter", "Insufficient stock left for finishing", "Built-up edge"],
  OUT_OF_TOLERANCE: ["Tool deflection", "Thermal growth", "Incorrect offset", "Part deformation under clamping", "Measurement error"],
  WORKHOLDING_FAILURE: ["Fixture deflection", "Clamp interference", "Jaw wear", "Bolt loosening"],
  WARPED: ["Residual stress in the stock", "Uneven material removal", "Clamping distortion", "Thermal effects"],
  COLLISION: ["Incorrect work offset", "Incorrect tool length", "Rapid through the fixture", "Untested program"],
  OTHER: ["—"],
};
