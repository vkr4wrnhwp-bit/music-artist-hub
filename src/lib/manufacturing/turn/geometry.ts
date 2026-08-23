/**
 * ROTATIONAL GEOMETRY — the X/Z world.
 *
 * A turned part is a profile revolved about the spindle centerline.
 * Convention, locked: X0 is the centerline, Z0 is the machining datum face,
 * Z positive toward the tailstock (stock extends in -Z toward the chuck for
 * a front-worked part; segments are recorded zStart→zEnd with zStart nearer
 * Z0). Diameters are DIAMETERS, never radii — machinists talk in diameter
 * and so does this model.
 *
 * Everything here is pure and deterministic: validation returns named
 * problems instead of throwing, and derived values (max diameter, length)
 * are computed, never stored separately to drift.
 */

export const SEGMENT_KINDS = [
  "CYLINDER",
  "FACE",
  "SHOULDER",
  "TAPER",
  "RADIUS",
  "CHAMFER",
  "GROOVE",
  "THREAD",
  "BORE",
  "ID_STEP",
  "UNDERCUT",
  "CUTOFF",
] as const;
export type SegmentKind = (typeof SEGMENT_KINDS)[number];

export const TURN_FUNCTIONAL_ROLES = [
  "NONE",
  "OD_JOURNAL",
  "ID_BORE",
  "BEARING_JOURNAL",
  "BEARING_BORE",
  "SEAL_SURFACE",
  "THREAD_EXTERNAL",
  "THREAD_INTERNAL",
  "LOCATING_SHOULDER",
  "SNAP_RING_GROOVE",
  "O_RING_GROOVE",
  "RELIEF_GROOVE",
  "PART_OFF_FACE",
  "DATUM_FACE",
  "CENTER_DRILL",
  "COSMETIC_OD",
  "STRUCTURAL_SHAFT_SECTION",
] as const;
export type TurnFunctionalRole = (typeof TURN_FUNCTIONAL_ROLES)[number];

export interface ProfileSegment {
  id: string;
  kind: SegmentKind;
  label: string;
  /** Z of the end nearer Z0 (the front face), inches. */
  zStart: number;
  /** Z of the far end, inches. zEnd > zStart along the part. */
  zEnd: number;
  /** Diameter at zStart. */
  diameterStart: number;
  /** Diameter at zEnd (equal for a cylinder). */
  diameterEnd: number;
  /** Internal geometry (bores, ID steps) is measured the same way, flagged. */
  internal: boolean;
  cornerRadius?: number;
  /**
   * Which way a RADIUS/blend curves. True is a fillet cut INTO the material
   * (the stress-relief radius at the base of a shoulder); false is a round
   * ON the material (a broken corner).
   *
   * This is NOT the same question as `internal`, which says whether the
   * feature is a bore or an OD — an OD shoulder carries a concave fillet
   * every day. Getting the two confused puts the arc on the wrong side of
   * its own endpoints, so the blend engine refuses rather than assuming.
   */
  concave?: boolean;
  chamfer?: number;
  /** Threads carry designation exactly as read, e.g. "3/4-16 UNF-2A". */
  thread?: string;
  tolerancePlus?: number;
  toleranceMinus?: number;
  surfaceFinish?: number;
  functionalRole: TurnFunctionalRole;
  critical: boolean;
  /** What mates here, when known. Function before process. */
  matingComponent?: string;
  /** Value provenance: USER | MEASURED | CALCULATED | AI_INFERRED | IMPORTED. */
  source: string;
  confirmedByUser: boolean;
}

export interface RotationalProfile {
  units: "IN" | "MM";
  /** Where Z0 is, stated: "front face" | "shoulder at ..." etc. */
  zZeroReference: string;
  stockDiameter: number;
  stockLength: number;
  barStock: boolean;
  segments: ProfileSegment[];
}

/** Overall length of the finished profile: furthest zEnd of any external segment. */
export function overallLength(p: RotationalProfile): number {
  const ext = p.segments.filter((s) => !s.internal);
  return ext.length === 0 ? 0 : Math.max(...ext.map((s) => s.zEnd));
}

export function maxDiameter(p: RotationalProfile): number {
  const ext = p.segments.filter((s) => !s.internal);
  return ext.length === 0 ? 0 : Math.max(...ext.map((s) => Math.max(s.diameterStart, s.diameterEnd)));
}

/**
 * Named validation problems. A profile that fails validation is not drawn as
 * though it were fine — the workspace lists these next to the profile.
 */
export function validateProfile(p: RotationalProfile): string[] {
  const problems: string[] = [];
  if (p.stockDiameter <= 0) problems.push("Stock diameter must be positive.");
  if (p.stockLength <= 0) problems.push("Stock length must be positive.");
  const md = maxDiameter(p);
  if (md > p.stockDiameter + 1e-9) {
    problems.push(
      `Finished max diameter ${md.toFixed(4)} exceeds stock diameter ${p.stockDiameter.toFixed(4)} — the stock cannot make this part.`,
    );
  }
  const ol = overallLength(p);
  if (ol > p.stockLength + 1e-9) {
    problems.push(`Finished length ${ol.toFixed(3)} exceeds stock length ${p.stockLength.toFixed(3)}.`);
  }
  for (const s of p.segments) {
    // A FACE, a SHOULDER and a CUTOFF are legitimately zero-length in Z —
    // they are diameter transitions, not axial spans.
    if (s.zEnd < s.zStart || (s.zEnd === s.zStart && !["FACE", "SHOULDER", "CUTOFF"].includes(s.kind))) {
      problems.push(`${s.label}: zEnd must be greater than zStart.`);
    }
    if (s.diameterStart < 0 || s.diameterEnd < 0) problems.push(`${s.label}: negative diameter.`);
    if (s.internal && Math.max(s.diameterStart, s.diameterEnd) >= p.stockDiameter) {
      problems.push(`${s.label}: internal diameter meets or exceeds the OD envelope.`);
    }
    if (s.kind === "THREAD" && !s.thread) {
      problems.push(`${s.label}: a THREAD segment carries its designation or it is not a thread.`);
    }
  }
  return problems;
}

/**
 * The finished profile as an X/Z polyline (z, radius) for drawing — external
 * segments sorted by zStart, gaps closed with shoulder verticals. Radius,
 * because the drawing mirrors about the centerline; every LABEL stays in
 * diameter.
 */
export function profilePolyline(p: RotationalProfile): { z: number; r: number }[] {
  const ext = p.segments
    .filter((s) => !s.internal && s.kind !== "CUTOFF")
    .slice()
    .sort((a, b) => a.zStart - b.zStart);
  const pts: { z: number; r: number }[] = [];
  for (const s of ext) {
    const r0 = s.diameterStart / 2;
    const r1 = s.diameterEnd / 2;
    if (pts.length === 0) pts.push({ z: s.zStart, r: 0 }, { z: s.zStart, r: r0 });
    else if (Math.abs(pts[pts.length - 1].r - r0) > 1e-9) pts.push({ z: s.zStart, r: r0 });
    pts.push({ z: s.zEnd, r: r1 });
  }
  if (pts.length > 0) pts.push({ z: pts[pts.length - 1].z, r: 0 });
  return pts;
}
