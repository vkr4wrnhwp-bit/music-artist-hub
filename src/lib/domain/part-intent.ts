import { z } from "zod";
import type { Provenanced } from "@/lib/provenance";
import { unknown, userValue } from "@/lib/provenance";

/**
 * The PART INTENT MODEL is the structured contract between "a human described
 * something" and "CANVAS is allowed to plan manufacturing". Natural language
 * never flows past this boundary — an intake prompt, a drawing, or a photo is
 * always reduced to this object first, and every field carries provenance so
 * the planner can refuse to act on guesses.
 */

export const UNITS = ["IN", "MM"] as const;
export type Units = (typeof UNITS)[number];

export const PRODUCTION_INTENT = ["PROTOTYPE", "BRIDGE", "PRODUCTION", "REPAIR", "SPARE"] as const;
export type ProductionIntent = (typeof PRODUCTION_INTENT)[number];

export const FAILURE_CONSEQUENCE = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type FailureConsequence = (typeof FAILURE_CONSEQUENCE)[number];

export const LOADING_TYPES = [
  "STATIC",
  "CYCLIC",
  "SHOCK",
  "IMPACT",
  "VIBRATION",
  "TORSION",
  "BENDING",
  "PRESSURE",
  "THERMAL_CYCLING",
] as const;
export type LoadingType = (typeof LOADING_TYPES)[number];

export const ENVIRONMENTS = [
  "INDOOR_DRY",
  "OUTDOOR",
  "MARINE",
  "HIGH_TEMP",
  "CRYOGENIC",
  "CHEMICAL",
  "FOOD_CONTACT",
  "VACUUM",
  "ABRASIVE",
] as const;
export type Environment = (typeof ENVIRONMENTS)[number];

export interface Envelope {
  x: number;
  y: number;
  z: number;
}

export interface StockDefinition {
  form: "RECTANGULAR" | "ROUND" | "TUBE" | "NEAR_NET" | "CASTING" | "FORGING";
  x?: number;
  y?: number;
  z?: number;
  diameter?: number;
  length?: number;
}

export interface CriticalDimension {
  id: string;
  label: string;
  nominal: number;
  plus: number;
  minus: number;
  featureId?: string;
  inspectionMethod?: string;
}

/**
 * Every property is Provenanced. That is the whole point — a part intent with
 * 20 AI-inferred fields and 0 confirmations is a legitimate object, it just
 * cannot pass a manufacturing gate.
 */
export interface PartIntent {
  partName: Provenanced<string>;
  description: Provenanced<string>;
  units: Provenanced<Units>;
  material: Provenanced<string>;
  materialCondition: Provenanced<string>;
  stock: Provenanced<StockDefinition>;
  finishedEnvelope: Provenanced<Envelope>;
  quantity: Provenanced<number>;
  features: Provenanced<string[]>;
  criticalDimensions: Provenanced<CriticalDimension[]>;
  generalTolerance: Provenanced<number>;
  criticalTolerances: Provenanced<CriticalDimension[]>;
  surfaceFinish: Provenanced<string>;
  application: Provenanced<string>;
  loadBearing: Provenanced<boolean>;
  safetyCritical: Provenanced<boolean>;
  failureConsequence: Provenanced<FailureConsequence>;
  loadingType: Provenanced<LoadingType[]>;
  environment: Provenanced<Environment[]>;
  temperatureRange: Provenanced<{ min: number; max: number }>;
  regulatoryRequirements: Provenanced<string[]>;
  inspectionRequirements: Provenanced<string[]>;
  productionIntent: Provenanced<ProductionIntent>;
  annualVolume: Provenanced<number>;
  notes: Provenanced<string>;
  /** Named gaps CANVAS knows it has. Drives the ENGINEERING INPUT REQUIRED panel. */
  unknowns: string[];
  /** Coarse 0–1 completeness of the intake, not a safety score. */
  confidence: number;
}

export function emptyPartIntent(name = "Untitled Part"): PartIntent {
  return {
    partName: userValue(name),
    description: unknown("No description captured"),
    units: userValue<Units>("IN"),
    material: unknown("Material not specified"),
    materialCondition: unknown(),
    stock: unknown("Stock not defined"),
    finishedEnvelope: unknown(),
    quantity: unknown(),
    features: unknown(),
    criticalDimensions: unknown(),
    generalTolerance: unknown(),
    criticalTolerances: unknown(),
    surfaceFinish: unknown(),
    application: unknown(),
    loadBearing: unknown(),
    safetyCritical: unknown(),
    failureConsequence: unknown(),
    loadingType: unknown(),
    environment: unknown(),
    temperatureRange: unknown(),
    regulatoryRequirements: unknown(),
    inspectionRequirements: unknown(),
    productionIntent: unknown(),
    annualVolume: unknown(),
    notes: unknown(),
    unknowns: [],
    confidence: 0,
  };
}

/** Fields the planner refuses to proceed without, regardless of criticality. */
const BASELINE_REQUIRED: (keyof PartIntent)[] = [
  "material",
  "stock",
  "finishedEnvelope",
  "quantity",
  "generalTolerance",
];

/** Additional fields required once the part carries real consequence. */
const CRITICAL_REQUIRED: (keyof PartIntent)[] = [
  "loadingType",
  "environment",
  "inspectionRequirements",
  "materialCondition",
  "surfaceFinish",
];

export function isCriticalApplication(intent: PartIntent): boolean {
  const fc = intent.failureConsequence.value;
  return (
    intent.safetyCritical.value === true ||
    intent.loadBearing.value === true ||
    fc === "HIGH" ||
    fc === "CRITICAL"
  );
}

/**
 * Returns the human-readable list of gaps blocking a manufacturing plan.
 * An empty array does not mean "safe" — it means "intake is complete enough
 * to start planning".
 */
export function missingEngineeringInput(intent: PartIntent): string[] {
  const required = isCriticalApplication(intent)
    ? [...BASELINE_REQUIRED, ...CRITICAL_REQUIRED]
    : BASELINE_REQUIRED;

  const gaps: string[] = [];
  for (const key of required) {
    const field = intent[key] as Provenanced<unknown>;
    if (!field || field.value === null || field.value === undefined) {
      gaps.push(FIELD_LABELS[key] ?? String(key));
    }
  }
  if (intent.failureConsequence.value === null) {
    gaps.push("Failure consequence not assessed");
  }
  return [...gaps, ...intent.unknowns];
}

export function intakeCompleteness(intent: PartIntent): number {
  const keys = Object.keys(intent).filter(
    (k) => k !== "unknowns" && k !== "confidence",
  ) as (keyof PartIntent)[];
  const filled = keys.filter((k) => (intent[k] as Provenanced<unknown>)?.value != null).length;
  return keys.length === 0 ? 0 : filled / keys.length;
}

export const FIELD_LABELS: Partial<Record<keyof PartIntent, string>> = {
  partName: "Part name",
  description: "Description",
  units: "Units",
  material: "Material",
  materialCondition: "Material condition / temper",
  stock: "Stock definition",
  finishedEnvelope: "Finished envelope",
  quantity: "Quantity",
  features: "Feature list",
  criticalDimensions: "Critical dimensions",
  generalTolerance: "General tolerance",
  criticalTolerances: "Critical tolerances",
  surfaceFinish: "Surface finish",
  application: "Application",
  loadBearing: "Load bearing",
  safetyCritical: "Safety critical",
  failureConsequence: "Failure consequence",
  loadingType: "Loading type",
  environment: "Service environment",
  temperatureRange: "Temperature range",
  regulatoryRequirements: "Regulatory requirements",
  inspectionRequirements: "Inspection requirements",
  productionIntent: "Production intent",
  annualVolume: "Annual volume",
  notes: "Notes",
};

/* ------------------------------------------------------------------ */
/* Validation schema used at the AI boundary                          */
/* ------------------------------------------------------------------ */

export const partIntentExtractionSchema = z.object({
  partName: z.string().optional(),
  description: z.string().optional(),
  units: z.enum(UNITS).optional(),
  material: z.string().optional(),
  materialCondition: z.string().optional(),
  stock: z
    .object({
      form: z.enum(["RECTANGULAR", "ROUND", "TUBE", "NEAR_NET", "CASTING", "FORGING"]),
      x: z.number().optional(),
      y: z.number().optional(),
      z: z.number().optional(),
      diameter: z.number().optional(),
      length: z.number().optional(),
    })
    .optional(),
  finishedEnvelope: z.object({ x: z.number(), y: z.number(), z: z.number() }).optional(),
  quantity: z.number().int().positive().optional(),
  generalTolerance: z.number().positive().optional(),
  surfaceFinish: z.string().optional(),
  features: z.array(z.string()).optional(),
  notes: z.string().optional(),
  unknowns: z.array(z.string()).default([]),
  confidence: z.number().min(0).max(1).default(0.5),
});

export type PartIntentExtraction = z.infer<typeof partIntentExtractionSchema>;
