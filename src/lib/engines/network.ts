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

/**
 * Coarse bands. Anything finer starts to reconstruct the actual part.
 *
 * UNKNOWN is a band in its own right. A part with no stock recorded used to
 * be fingerprinted as "M", and one with no quantity as "ONE_OFF" — a made-up
 * band is both a false statement about the shop's part and a false match
 * against somebody else's.
 */
export type Band = "XS" | "S" | "M" | "L" | "XL" | "UNKNOWN";

/**
 * The closed vocabularies a fingerprint may contain. Every string field is
 * mapped into one of these before it leaves; nothing user-typed is ever
 * passed through, however harmless it looks.
 */
export const MATERIAL_FAMILIES = [
  "ALUMINUM", "STEEL", "STAINLESS", "TITANIUM", "BRASS", "BRONZE",
  "COPPER", "MAGNESIUM", "NICKEL_ALLOY", "CAST_IRON", "PLASTIC", "COMPOSITE",
  "OTHER", "UNKNOWN",
] as const;
export type MaterialFamily = (typeof MATERIAL_FAMILIES)[number];

export const WORKHOLDING_CLASSES = [
  "VISE", "SOFT_JAWS", "FIXTURE_PLATE", "DOVETAIL", "CUSTOM", "VACUUM",
] as const;

/** Operation identifiers a fingerprint may carry. Anything else is dropped. */
export const FINGERPRINT_OPERATIONS = [
  "FACE", "POCKET_2D", "ADAPTIVE_2D", "DRILL", "PECK_DRILL", "BORE", "TAP",
  "CONTOUR_2D", "CHAMFER", "ENGRAVE", "SOFT_JAW_POCKET",
] as const;

/**
 * Maps whatever a shop typed into the material field onto a family.
 *
 * This used to be `material.split(/\s+/)[0].toUpperCase()` — the first
 * whitespace-delimited token of free text, passed straight into the
 * fingerprint. "Boeing-spec Ti-6Al-4V ELI" left the organisation as
 * "BOEING-SPEC". The file's own rules say a fingerprint carries "never
 * names, never text", and material was the one field that was unbounded user
 * input.
 *
 * Anything unrecognised becomes OTHER. A family CANVAS cannot name is not a
 * reason to disclose the shop's words for it.
 */
export function materialFamilyOf(raw: string | null): MaterialFamily {
  if (!raw || !raw.trim()) return "UNKNOWN";
  const t = raw.toUpperCase();

  if (/\bTI\b|TITANIUM|6AL-4V|TI-6AL/.test(t)) return "TITANIUM";
  if (/STAINLESS|\b(3[01][0-9]|316L|17-4|15-5|416|420|440C)\b|\bSS\b/.test(t)) return "STAINLESS";
  if (/INCONEL|HASTELLOY|MONEL|WASPALOY|NICKEL|\b625\b|\b718\b/.test(t)) return "NICKEL_ALLOY";
  if (/CAST[\s-]?IRON|DUCTILE|GREY IRON|GRAY IRON/.test(t)) return "CAST_IRON";
  if (/ALUMIN|\b[67]0[0-9]{2}\b|\b20[0-9]{2}-T|\bMIC-?6\b/.test(t)) return "ALUMINUM";
  if (/STEEL|\b(10[0-9]{2}|11[0-9]{2}|41[0-9]{2}|43[0-9]{2}|86[0-9]{2}|A36)\b|\bO1\b|\bA2\b|\bD2\b/.test(t)) return "STEEL";
  if (/BRASS|\b360\b|\bC36000\b/.test(t)) return "BRASS";
  if (/BRONZE|\bC9[0-9]{4}\b|OILITE/.test(t)) return "BRONZE";
  if (/COPPER|\bC1[0-9]{4}\b/.test(t)) return "COPPER";
  if (/MAGNESIUM|\bAZ[0-9]/.test(t)) return "MAGNESIUM";
  if (/DELRIN|ACETAL|NYLON|UHMW|PEEK|POLYCARB|ABS|PTFE|TEFLON|HDPE|PVC|PLASTIC/.test(t)) return "PLASTIC";
  if (/CARBON FIBRE|CARBON FIBER|\bG10\b|FR4|COMPOSITE|FIBERGLASS|FIBREGLASS/.test(t)) return "COMPOSITE";

  return "OTHER";
}

export interface ManufacturingFingerprint {
  /** Never contains an org id, part name, or any free text. */
  geometryFamily: "PRISMATIC_PLATE" | "PRISMATIC_BLOCK" | "ROTATIONAL" | "THIN_WALL" | "COMPLEX";
  processFamily: "MILL_3AXIS" | "MILL_MULTIAXIS" | "TURN" | "TURN_MILL" | "FABRICATION" | "ADDITIVE";
  materialFamily: MaterialFamily;
  envelopeBand: Band;
  featureTypes: string[];
  bearingInterfaces: number;
  fastenerInterfaces: number;
  toleranceClass: "COARSE" | "STANDARD" | "PRECISION" | "HIGH_PRECISION" | "UNKNOWN";
  surfaceFinishClass: "AS_MACHINED" | "FINE" | "GROUND" | "POLISHED";
  quantityBand: "ONE_OFF" | "LOW" | "MEDIUM" | "HIGH" | "VERY_HIGH" | "UNKNOWN";
  machineClass: "BENCHTOP" | "STANDARD_VMC" | "LARGE_VMC" | "HMC" | "MULTIAXIS" | "UNKNOWN";
  complexity: Band;
  workholdingClass: (typeof WORKHOLDING_CLASSES)[number];
  /** Only identifiers from FINGERPRINT_OPERATIONS. Never an operation label. */
  operationSequence: (typeof FINGERPRINT_OPERATIONS)[number][];
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
  // Was "M". A part whose stock nobody has recorded is not a medium part.
  if (!stock) return "UNKNOWN";
  const max = Math.max(stock.x, stock.y, stock.z);
  if (max <= 2) return "XS";
  if (max <= 6) return "S";
  if (max <= 14) return "M";
  if (max <= 30) return "L";
  return "XL";
}

function quantityBand(q: number | null): ManufacturingFingerprint["quantityBand"] {
  // Was "ONE_OFF". An unrecorded quantity is not a one-off, and stating it as
  // one both misdescribes the shop's job and matches it against the wrong
  // people.
  if (q === null) return "UNKNOWN";
  if (q <= 1) return "ONE_OFF";
  if (q <= 25) return "LOW";
  if (q <= 250) return "MEDIUM";
  if (q <= 5000) return "HIGH";
  return "VERY_HIGH";
}

function toleranceClass(t: number | null): ManufacturingFingerprint["toleranceClass"] {
  if (t === null) return "UNKNOWN";
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

  const materialFamily = materialFamilyOf(intent.material.value);

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
      // Was "STANDARD_VMC" when travel was unrecorded — a claim about the
      // shop's machine that nobody made.
      input.machineTravelX === null
        ? "UNKNOWN"
        : input.machineTravelX < 16
          ? "BENCHTOP"
          : input.machineTravelX < 40
            ? "STANDARD_VMC"
            : "LARGE_VMC",
    complexity,
    // Both of these were passed straight through. workholdingType was cast
    // into a closed union without being checked, so "Kurt 6in with
    // ACME-Aerospace custom jaws" left the organisation verbatim; and
    // operationTypes is a string[] the caller fills, so an operation LABEL
    // rather than a type — "Rough the ACME-Aerospace rotor pocket" — left
    // with it. An unrecognised value is never disclosed as itself.
    workholdingClass: WORKHOLDING_CLASSES.includes(input.workholdingType as never)
      ? (input.workholdingType as (typeof WORKHOLDING_CLASSES)[number])
      : "CUSTOM",
    operationSequence: input.operationTypes.filter((t): t is (typeof FINGERPRINT_OPERATIONS)[number] =>
      FINGERPRINT_OPERATIONS.includes(t as never),
    ),
    setupCount: input.setupCount,
  };
}

/**
 * Audit helper. Every field a fingerprint carries is enumerated here so the
 * privacy page can show the user exactly what would leave — and so a reviewer
 * can spot a field that should never have been added.
 *
 * It used to be a hand-written list, and it had drifted: surfaceFinishClass
 * and operationSequence were both in the fingerprint and absent from the
 * table. A user consenting on the strength of that page was consenting to
 * thirteen fields while fifteen left — and operationSequence was, at the
 * time, capable of carrying an operation label in free text.
 *
 * So the table is now derived FROM the fingerprint rather than written
 * alongside it. A field with no entry in FIELD_DISCLOSURE does not silently
 * vanish; it appears as UNCLASSIFIED and reads as the review item it is.
 */
const FIELD_DISCLOSURE: Record<keyof ManufacturingFingerprint, { label: string; risk: "NONE" | "LOW" }> = {
  geometryFamily: { label: "Geometry family", risk: "NONE" },
  processFamily: { label: "Process family", risk: "NONE" },
  materialFamily: { label: "Material family", risk: "NONE" },
  envelopeBand: { label: "Envelope band", risk: "LOW" },
  featureTypes: { label: "Feature types", risk: "LOW" },
  bearingInterfaces: { label: "Bearing interfaces", risk: "NONE" },
  fastenerInterfaces: { label: "Fastener interfaces", risk: "NONE" },
  toleranceClass: { label: "Tolerance class", risk: "NONE" },
  surfaceFinishClass: { label: "Surface finish class", risk: "NONE" },
  quantityBand: { label: "Quantity band", risk: "LOW" },
  machineClass: { label: "Machine class", risk: "NONE" },
  complexity: { label: "Complexity band", risk: "NONE" },
  workholdingClass: { label: "Workholding class", risk: "NONE" },
  operationSequence: { label: "Operation sequence", risk: "LOW" },
  setupCount: { label: "Setup count", risk: "NONE" },
};

export interface DisclosureRow {
  field: string;
  value: string;
  risk: "NONE" | "LOW" | "UNCLASSIFIED";
}

export function describeFingerprintDisclosure(fp: ManufacturingFingerprint): DisclosureRow[] {
  return (Object.keys(fp) as (keyof ManufacturingFingerprint)[]).map((key) => {
    const known = FIELD_DISCLOSURE[key];
    const raw = fp[key];
    const value = Array.isArray(raw) ? raw.join(", ") || "\u2014" : String(raw);
    return known
      ? { field: known.label, value, risk: known.risk }
      : { field: `${key} — NOT CLASSIFIED, review before this ships`, value, risk: "UNCLASSIFIED" as const };
  });
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
