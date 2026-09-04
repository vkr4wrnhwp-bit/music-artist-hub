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
  /**
   * Instrument class the method names. Carried separately from the sentence
   * because the capability engine judges the class, and parsing it back out of
   * prose would be a second vocabulary that could drift from the first.
   */
  inspectionDeviceType?: string;
  /**
   * A person's stated reason this feature is not cut by the program — a
   * fillet, a hand-broken chamfer, a vendor operation. Read by the coverage
   * gate, which repeats it rather than swallowing it. See engines/coverage.ts.
   */
  notMachinedReason?: string;
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

/**
 * Features flagged critical. Nothing else.
 *
 * The body used to be `f.critical || f.functionalRole !== "NONE"`, which is not
 * what the name says. That set is critical features UNION everything carrying
 * any role at all — including CLEARANCE and COSMETIC, the two roles that exist
 * precisely to say nothing hangs on this. It put the demo part's clearance
 * relief in the same bucket as a ±0.0005"/-0 bearing seat.
 *
 * It never had a caller, so nothing was ever wrong on screen. What made it
 * worth fixing is the shape of the trap: the readiness engine derives the same
 * idea inline as `f.critical`, so an author who imported this helper expecting
 * agreement would have got a superset, and the "Critical tolerance strategy"
 * gate would have demoted from PASS to REVIEW on the strength of a clearance
 * pocket having no inspection method. On a part where `isCriticalApplication`
 * holds, that REVIEW is blocking — so the mislabelled predicate could have
 * blocked NC export on a part with no critical features on it at all.
 *
 * Two things this deliberately is not:
 *
 * It is not a general "features that matter" set. Criticality is a severity
 * flag; a functional role is a statement of what a feature is for. They are
 * different axes and welding them with an OR produces a set with no name a
 * machinist would use. Whoever wants the role question wants a different
 * predicate — the feature index asks it as `functionalRole === "NONE"`.
 *
 * It is not yet the single definition. `f.critical` is still derived inline in
 * the readiness gate, the NC preflight, the inspection page and the part
 * detail page. They all agree today. Consolidating them onto this helper is
 * worth doing, but it is not a free tidy-up: this would become a shared symbol
 * whose next edit moves a gate that blocks executable NC, so it needs every
 * caller routed through it at once — not one, with the others left inline.
 *
 * If you do wire it into `readiness.ts`, replace the local const rather than
 * importing alongside it. The local shadows the import, so the inline filter
 * survives while the import sits unused, and `criticalFeatures.length === 0`
 * then reads the function's arity — 1, never 0 — which type-checks clean and
 * silently kills the NOT_ATTEMPTED branch.
 */
export function criticalFeatures(features: Feature[]): Feature[] {
  return features.filter((f) => f.critical);
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
