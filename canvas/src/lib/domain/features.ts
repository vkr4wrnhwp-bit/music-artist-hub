import { z } from "zod";

/**
 * PHASE 1 GEOMETRY MODEL
 *
 * This is deliberately NOT a B-rep kernel. Phase 1 covers the prismatic /
 * 2.5D feature space that a 3-axis mill can actually produce reliably, stored
 * as parametric objects so that both the viewport and the CAM engine read the
 * same numbers. When a real kernel is introduced it slots in behind
 * `evaluatePart()` — see /docs/CAM_ENGINE.md.
 *
 * Convention: Z+ is up, part origin is at the datum defined by the setup,
 * Z=0 at the finished top face unless the feature states otherwise.
 */

export const FEATURE_KINDS = [
  "FACE",
  "RECT_POCKET",
  "CIRC_POCKET",
  "SLOT",
  "DRILLED_HOLE",
  "TAPPED_HOLE",
  "COUNTERBORE",
  "COUNTERSINK",
  "BORE",
  "CHAMFER",
  "FILLET",
  "OUTSIDE_CONTOUR",
  "ENGRAVING",
  "BOSS",
  "STEP",
] as const;
export type FeatureKind = (typeof FEATURE_KINDS)[number];

/**
 * Functional role is separate from geometry on purpose. A 1.5748" bore is
 * geometry; "40 mm bearing seat" is responsibility. CAM and the process
 * advisor are only allowed to relax geometry that carries no role.
 */
export const FUNCTIONAL_ROLES = [
  "NONE",
  "BEARING_SEAT",
  "SEAL_SURFACE",
  "SHAFT_JOURNAL",
  "LOCATING_SHOULDER",
  "PRESS_FIT",
  "SLIP_FIT",
  "THREAD",
  "MOUNTING_HOLE",
  "DOWEL_HOLE",
  "DATUM_FACE",
  "INSPECTION_SURFACE",
  "FLUID_PASSAGE",
  "COSMETIC",
  "STRUCTURAL_RIB",
  "FIXTURE_PAD",
  "CLEARANCE",
] as const;
export type FunctionalRole = (typeof FUNCTIONAL_ROLES)[number];

export interface Tolerance {
  plus: number;
  minus: number;
}

export interface FeatureBase {
  id: string;
  kind: FeatureKind;
  label: string;
  /** Which setup this feature is reachable from, if already assigned. */
  setupId?: string;
  functionalRole: FunctionalRole;
  critical: boolean;
  tolerance?: Tolerance;
  /** Ra in microinches. */
  surfaceFinish?: number;
  inspectionMethod?: string;
  notes?: string;
}

export interface FaceFeature extends FeatureBase {
  kind: "FACE";
  depth: number; // material removed off the top
}

export interface RectPocketFeature extends FeatureBase {
  kind: "RECT_POCKET";
  centerX: number;
  centerY: number;
  width: number; // X
  length: number; // Y
  depth: number;
  cornerRadius: number;
  bottomRadius: number;
  /** Z of the pocket mouth. 0 = top face. */
  top: number;
}

export interface CircPocketFeature extends FeatureBase {
  kind: "CIRC_POCKET" | "BORE";
  centerX: number;
  centerY: number;
  diameter: number;
  depth: number;
  bottomRadius: number;
  top: number;
  through: boolean;
}

export interface SlotFeature extends FeatureBase {
  kind: "SLOT";
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  width: number;
  depth: number;
  top: number;
}

export interface HoleFeature extends FeatureBase {
  kind: "DRILLED_HOLE" | "TAPPED_HOLE" | "COUNTERBORE" | "COUNTERSINK";
  centerX: number;
  centerY: number;
  diameter: number;
  depth: number;
  through: boolean;
  top: number;
  /** Thread designation for TAPPED_HOLE, e.g. "1/4-20 UNC" or "M6x1.0". */
  thread?: string;
  /** Counterbore / countersink head geometry. */
  headDiameter?: number;
  headDepth?: number;
  countersinkAngle?: number;
}

export interface ChamferFeature extends FeatureBase {
  kind: "CHAMFER";
  width: number;
  angle: number;
  /** Edge set the chamfer applies to. */
  applyTo: "OUTSIDE_TOP" | "OUTSIDE_BOTTOM" | "HOLES" | "POCKET";
  targetFeatureId?: string;
}

export interface FilletFeature extends FeatureBase {
  kind: "FILLET";
  radius: number;
  applyTo: "OUTSIDE_VERTICAL" | "POCKET_CORNERS";
  targetFeatureId?: string;
}

export interface ContourFeature extends FeatureBase {
  kind: "OUTSIDE_CONTOUR";
  width: number; // X extent of finished part
  length: number; // Y extent
  cornerRadius: number;
  depth: number; // full height cut
}

export interface EngravingFeature extends FeatureBase {
  kind: "ENGRAVING";
  text: string;
  centerX: number;
  centerY: number;
  height: number;
  depth: number;
  top: number;
}

export interface BossFeature extends FeatureBase {
  kind: "BOSS";
  centerX: number;
  centerY: number;
  diameter: number;
  height: number;
}

export interface StepFeature extends FeatureBase {
  kind: "STEP";
  side: "XMIN" | "XMAX" | "YMIN" | "YMAX";
  width: number;
  depth: number;
}

export type Feature =
  | FaceFeature
  | RectPocketFeature
  | CircPocketFeature
  | SlotFeature
  | HoleFeature
  | ChamferFeature
  | FilletFeature
  | ContourFeature
  | EngravingFeature
  | BossFeature
  | StepFeature;

/* ------------------------------------------------------------------ */
/* Stock                                                               */
/* ------------------------------------------------------------------ */

export interface Stock {
  form: "RECTANGULAR" | "ROUND";
  x: number;
  y: number;
  z: number;
  diameter?: number;
  material: string;
  condition?: string;
}

export interface PartGeometry {
  units: "IN" | "MM";
  stock: Stock;
  features: Feature[];
}

/* ------------------------------------------------------------------ */
/* Derived queries used by CAM, workholding and readiness              */
/* ------------------------------------------------------------------ */

/** Smallest internal corner radius anywhere in the part. Drives tool choice. */
export function minimumInternalRadius(features: Feature[]): number | null {
  const radii: number[] = [];
  for (const f of features) {
    if (f.kind === "RECT_POCKET") radii.push(f.cornerRadius);
    if (f.kind === "CIRC_POCKET" || f.kind === "BORE") radii.push(f.diameter / 2);
    if (f.kind === "SLOT") radii.push(f.width / 2);
  }
  return radii.length ? Math.min(...radii) : null;
}

/** Deepest cut from the top face — drives tool stickout and reach checks. */
export function maximumDepth(features: Feature[], stock: Stock): number {
  let max = 0;
  for (const f of features) {
    if ("depth" in f && typeof f.depth === "number") {
      const through = "through" in f && f.through;
      max = Math.max(max, through ? stock.z : f.depth);
    }
  }
  return max;
}

export function criticalFeatures(features: Feature[]): Feature[] {
  return features.filter((f) => f.critical || f.functionalRole !== "NONE");
}

export function featureSummary(f: Feature): string {
  switch (f.kind) {
    case "FACE":
      return `Face ${fmt(f.depth)} deep`;
    case "RECT_POCKET":
      return `${fmt(f.width)} × ${fmt(f.length)} × ${fmt(f.depth)} deep, R${fmt(f.cornerRadius)}`;
    case "CIRC_POCKET":
    case "BORE":
      return `⌀${fmt(f.diameter)} × ${f.through ? "thru" : `${fmt(f.depth)} deep`}`;
    case "SLOT":
      return `${fmt(f.width)} wide × ${fmt(f.depth)} deep`;
    case "DRILLED_HOLE":
      return `⌀${fmt(f.diameter)} ${f.through ? "thru" : `× ${fmt(f.depth)} deep`}`;
    case "TAPPED_HOLE":
      return `${f.thread ?? "tapped"} ${f.through ? "thru" : `× ${fmt(f.depth)} deep`}`;
    case "COUNTERBORE":
      return `⌀${fmt(f.diameter)} c'bore ⌀${fmt(f.headDiameter ?? 0)} × ${fmt(f.headDepth ?? 0)}`;
    case "COUNTERSINK":
      return `⌀${fmt(f.diameter)} csk ⌀${fmt(f.headDiameter ?? 0)} × ${f.countersinkAngle ?? 82}°`;
    case "CHAMFER":
      return `${fmt(f.width)} × ${f.angle}° chamfer`;
    case "FILLET":
      return `R${fmt(f.radius)}`;
    case "OUTSIDE_CONTOUR":
      return `${fmt(f.width)} × ${fmt(f.length)}, R${fmt(f.cornerRadius)} corners`;
    case "ENGRAVING":
      return `"${f.text}" ${fmt(f.depth)} deep`;
    case "BOSS":
      return `⌀${fmt(f.diameter)} × ${fmt(f.height)} tall`;
    case "STEP":
      return `${fmt(f.width)} × ${fmt(f.depth)} step on ${f.side}`;
  }
}

export const fmt = (n: number, places = 4): string =>
  Number.isFinite(n) ? n.toFixed(places).replace(/0+$/, "").replace(/\.$/, ".000") : "—";

export const fmtTol = (t?: Tolerance): string =>
  t ? (t.plus === t.minus ? `±${t.plus.toFixed(4)}` : `+${t.plus.toFixed(4)}/-${t.minus.toFixed(4)}`) : "";

/* ------------------------------------------------------------------ */
/* Schema for the AI boundary — features suggested by a model must     */
/* validate before they are ever allowed into a part.                  */
/* ------------------------------------------------------------------ */

export const featureSuggestionSchema = z.object({
  kind: z.enum(FEATURE_KINDS),
  label: z.string(),
  functionalRole: z.enum(FUNCTIONAL_ROLES).default("NONE"),
  critical: z.boolean().default(false),
  parameters: z.record(z.string(), z.union([z.number(), z.string(), z.boolean()])),
  rationale: z.string().optional(),
});

export type FeatureSuggestion = z.infer<typeof featureSuggestionSchema>;
