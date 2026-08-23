import type { RotationalProfile } from "./geometry";

/**
 * TURNING OPERATIONS — deterministic X/Z motion and honest time.
 *
 * The same rule as the mill engine: an LLM never emits machine motion. The
 * generators here are arithmetic over the profile, the tool and the stock,
 * and they refuse what they cannot do safely rather than guessing. Cycle
 * time states its assumptions — no acceleration model, CSS approximated at
 * the mean diameter of each pass — and is labelled ESTIMATED everywhere it
 * appears.
 */

export const TURN_OPERATION_TYPES = [
  "FACE",
  "OD_ROUGH",
  "OD_FINISH",
  "ID_DRILL",
  "ID_BORE_ROUGH",
  "ID_BORE_FINISH",
  "GROOVE_OD",
  "GROOVE_ID",
  "THREAD_OD",
  "THREAD_ID",
  "CHAMFER",
  "RADIUS_BLEND",
  "PART_OFF",
  "CENTER_DRILL",
  "REAM",
  "TAP",
  "CUSTOM",
] as const;
export type TurnOperationType = (typeof TURN_OPERATION_TYPES)[number];

export interface TurnCutParams {
  /** Feed per revolution, in/rev. */
  feedPerRev: number;
  /** Surface speed target, SFM (CSS) — or null when running fixed RPM. */
  surfaceSpeed: number | null;
  /** Fixed RPM when CSS is off, or the G50 clamp when CSS is on. */
  rpm: number;
  cssEnabled: boolean;
  /** Depth of cut per pass, on radius, inches. */
  doc: number;
  finishAllowance: number;
  springPasses: number;
  coolant: "FLOOD" | "OFF";
}

export interface TurnOperation {
  operationNumber: number;
  type: TurnOperationType;
  label: string;
  toolStation: string; // "T0101" style
  targetSegmentId: string | null;
  startZ: number;
  endZ: number;
  startDiameter: number;
  endDiameter: number;
  params: TurnCutParams;
}

export interface TurnMove {
  kind: "RAPID" | "CUT" | "THREAD_PASS";
  x: number; // DIAMETER, the way a lathe programs X
  z: number;
  feedPerRev: number | null;
}

export interface TurnToolpath {
  operationNumber: number;
  type: TurnOperationType;
  moves: TurnMove[];
  passes: number;
  /** Minutes, ESTIMATED — assumptions listed, never implied exact. */
  estimatedMinutes: number;
  assumptions: string[];
  warnings: string[];
  /**
   * True when the motion is a rigid tapping cycle. The moves stand in for
   * simulation and timing only — the post must emit the canned cycle
   * (M29/G84..G80), which owns the spindle and the reversal, or refuse.
   * TurnMove cannot express a spindle reversal, and feed moves emitted as
   * G1 would strip the thread on the way out.
   */
  rigidTapCycle?: true;
  /**
   * Spindle RPM the engine DECIDED, overriding params.rpm — set when the
   * operation caps or locks the speed (tapping). The post must prefer this:
   * reading params.rpm there would silently undo the cap at the one place
   * it matters.
   */
  spindleRpmOverride?: number;
}

export type TurnToolpathResult = { ok: true; toolpath: TurnToolpath } | { ok: false; reason: string };

const SAFE_X_CLEAR = 0.1; // diameter clearance above the current surface
const SAFE_Z_CLEAR = 0.05;

/**
 * Effective RPM for a pass: CSS at the mean diameter, clamped by the G50 /
 * machine / chuck limit — or the programmed fixed RPM. The clamp is a
 * ceiling; CSS never exceeds it.
 */
export function effectiveRpm(params: TurnCutParams, meanDiameter: number): number {
  if (!params.cssEnabled || params.surfaceSpeed === null) return params.rpm;
  if (meanDiameter <= 1e-6) return params.rpm;
  const cssRpm = (params.surfaceSpeed * 12) / (Math.PI * meanDiameter);
  return Math.min(cssRpm, params.rpm);
}

function passMinutes(cutLength: number, params: TurnCutParams, meanDiameter: number): number {
  const rpm = effectiveRpm(params, meanDiameter);
  if (rpm <= 0 || params.feedPerRev <= 0) return 0;
  return cutLength / (params.feedPerRev * rpm);
}

/** OD roughing: successive parallel passes from stock diameter down. */
export function odRoughToolpath(op: TurnOperation, profile: RotationalProfile): TurnToolpathResult {
  if (op.params.doc <= 0) return { ok: false, reason: "Depth of cut must be positive." };
  const stockD = profile.stockDiameter;
  const targetD = op.endDiameter + 2 * op.params.finishAllowance;
  if (targetD >= stockD) return { ok: false, reason: "Nothing to rough: target diameter meets or exceeds stock." };
  const cutLen = Math.abs(op.endZ - op.startZ);
  if (cutLen <= 0) return { ok: false, reason: "Zero-length cut." };

  const radialTotal = (stockD - targetD) / 2;
  const passes = Math.max(1, Math.ceil(radialTotal / op.params.doc));
  const moves: TurnMove[] = [];
  let minutes = 0;
  for (let i = 1; i <= passes; i++) {
    const d = Math.max(targetD, stockD - 2 * op.params.doc * i);
    moves.push({ kind: "RAPID", x: d, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "CUT", x: d, z: op.endZ, feedPerRev: op.params.feedPerRev });
    // Retract off the shoulder, back out.
    moves.push({ kind: "CUT", x: d + 2 * SAFE_X_CLEAR, z: op.endZ, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "RAPID", x: stockD + 2 * SAFE_X_CLEAR, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    minutes += passMinutes(cutLen, op.params, (d + Math.min(stockD, d + 2 * op.params.doc)) / 2);
  }
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "ESTIMATED: no acceleration model; CSS approximated at each pass's mean diameter.",
        `Finish allowance ${op.params.finishAllowance.toFixed(4)}" left on diameter per side.`,
      ],
      warnings: [],
    },
  };
}

/** One finishing pass along the segment, plus spring passes. */
export function odFinishToolpath(op: TurnOperation): TurnToolpathResult {
  const cutLen = Math.abs(op.endZ - op.startZ);
  if (cutLen <= 0) return { ok: false, reason: "Zero-length cut." };
  const passes = 1 + Math.max(0, op.params.springPasses);
  const moves: TurnMove[] = [];
  let minutes = 0;
  for (let i = 0; i < passes; i++) {
    moves.push({ kind: "RAPID", x: op.endDiameter, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "CUT", x: op.endDiameter, z: op.endZ, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "RAPID", x: op.endDiameter + 2 * SAFE_X_CLEAR, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    minutes += passMinutes(cutLen, op.params, op.endDiameter);
  }
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "ESTIMATED: no acceleration model.",
        op.params.springPasses > 0 ? `${op.params.springPasses} spring pass(es) at full length.` : "No spring passes.",
      ],
      warnings: [],
    },
  };
}

/* ------------------------------------------------------------------ */
/* CHAMFERS AND BLENDS — where the nose radius stops being ignorable   */
/* ------------------------------------------------------------------ */

/**
 * A straight OD or a face gets away with ignoring the insert's nose radius:
 * the nose touches the work at the programmed X (or Z), so the imaginary
 * tool tip the control positions cuts the size you asked for.
 *
 * A TAPER OR AN ARC DOES NOT. The contact point walks around the nose as
 * the cut angle changes, and an uncompensated path leaves the profile off
 * by an amount that scales with the nose radius — on a 1/32" insert that is
 * over ten thou, always in the same direction. This is the entire reason
 * lathe controls have G41/G42.
 *
 * So these two operations refuse without a recorded nose radius, and they
 * say what the uncompensated path will cost. What they do NOT do is invent
 * a compensated path: the post emits G40 and CANVAS does not compute nose
 * radius compensation, so claiming a corrected profile would be a number
 * with nothing behind it. The bound is stated instead, and the machinist
 * decides. See docs/TURNING_OPERATIONS.md.
 */

/** Chord tolerance for approximating a blend arc, inches. Stated, not tuned. */
const BLEND_CHORD_TOLERANCE = 0.0005;

function noseRadiusCheck(noseRadius: number | null | undefined): { reason: string } | null {
  if (noseRadius === null || noseRadius === undefined) {
    return {
      reason:
        "No insert nose radius recorded at this station. On a taper or a blend the nose radius decides the profile, and CANVAS will not assume an insert.",
    };
  }
  if (!(noseRadius >= 0)) return { reason: `Nose radius ${noseRadius} is not a radius.` };
  return null;
}

/** The uncompensated profile error, stated as the bound it actually is. */
function compensationWarning(noseRadius: number): string {
  return (
    `Path is the imaginary tool tip, uncompensated: the cut profile will deviate by up to the ` +
    `${noseRadius.toFixed(4)}" nose radius. Turn on nose radius compensation at the control, or ` +
    `prove the chamfer on the first piece before running the rest.`
  );
}

/** Chamfer: one straight cut between two diameters. */
export function chamferToolpath(op: TurnOperation, noseRadius: number | null): TurnToolpathResult {
  const nose = noseRadiusCheck(noseRadius);
  if (nose) return { ok: false, reason: nose.reason };

  const dz = op.endZ - op.startZ;
  const dx = (op.endDiameter - op.startDiameter) / 2; // radial
  if (dz === 0 && dx === 0) return { ok: false, reason: "Chamfer has no extent in Z or X — there is nothing to cut." };
  if (op.startDiameter < 0 || op.endDiameter < 0) return { ok: false, reason: "Negative diameter." };

  const slant = Math.hypot(dz, dx);
  const angleDeg = Math.abs((Math.atan2(dx, dz) * 180) / Math.PI);
  const approachD = Math.max(op.startDiameter, op.endDiameter) + 2 * SAFE_X_CLEAR;
  const moves: TurnMove[] = [
    { kind: "RAPID", x: approachD, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "RAPID", x: op.startDiameter, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "CUT", x: op.startDiameter, z: op.startZ, feedPerRev: op.params.feedPerRev },
    // The chamfer itself: a single interpolated move, X and Z together.
    { kind: "CUT", x: op.endDiameter, z: op.endZ, feedPerRev: op.params.feedPerRev },
    { kind: "RAPID", x: approachD, z: op.endZ, feedPerRev: null },
  ];
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3(passMinutes(slant, op.params, (op.startDiameter + op.endDiameter) / 2)),
      assumptions: [
        "ESTIMATED: no acceleration model; feed applied along the slant length.",
        `Chamfer at ${angleDeg.toFixed(1)}° to the centreline, ${slant.toFixed(4)}" along the slant.`,
      ],
      warnings: [compensationWarning(noseRadius!)],
    },
  };
}

/**
 * Radius blend: an arc between two diameters, chorded into linear moves.
 *
 * Chorded rather than emitted as G02/G03 because the post has no arc output
 * and a move this engine cannot express is not a move it should pretend to
 * make. The chord tolerance is stated and the deviation is bounded by it.
 */
export function radiusBlendToolpath(
  op: TurnOperation,
  blendRadius: number | null,
  noseRadius: number | null,
  concave: boolean | null,
): TurnToolpathResult {
  const nose = noseRadiusCheck(noseRadius);
  if (nose) return { ok: false, reason: nose.reason };
  if (blendRadius === null || !(blendRadius > 0)) {
    return {
      ok: false,
      reason: "No blend radius recorded on the target segment. A blend is its radius; CANVAS will not choose one.",
    };
  }
  /*
   * Which way the blend curves decides where its centre goes, and the model
   * does not always record it. Guessing puts the arc on the wrong side of
   * its own endpoints — a visibly wrong profile, cut confidently.
   */
  if (concave === null || concave === undefined) {
    return {
      ok: false,
      reason:
        "The target segment does not record whether this blend curves into the material or onto it. Which way a radius turns decides where its centre is, and CANVAS will not pick a side.",
    };
  }
  /*
   * A concave blend cannot be cut by a nose bigger than it — the same
   * impossibility the milling engine refuses for a corner radius against an
   * end mill. A convex blend has no such limit: a large nose simply rolls
   * around the outside of it.
   */
  if (concave && noseRadius! > blendRadius) {
    return {
      ok: false,
      reason: `A ⌀${(noseRadius! * 2).toFixed(4)} nose (R${noseRadius!.toFixed(4)}) cannot produce a concave R${blendRadius.toFixed(4)} blend.`,
    };
  }

  const dz = op.endZ - op.startZ;
  const dx = (op.endDiameter - op.startDiameter) / 2;
  const chordLen = Math.hypot(dz, dx);
  if (chordLen === 0) return { ok: false, reason: "Blend has no extent — start and end are the same point." };
  if (chordLen > 2 * blendRadius + 1e-9) {
    return {
      ok: false,
      reason: `The blend endpoints are ${chordLen.toFixed(4)}" apart, which no R${blendRadius.toFixed(4)} arc can span.`,
    };
  }

  /*
   * Segment count from the stated chord tolerance: for a sagitta t on a
   * radius R, each chord subtends 2*acos(1 - t/R).
   */
  const maxStep = 2 * Math.acos(Math.max(-1, Math.min(1, 1 - BLEND_CHORD_TOLERANCE / blendRadius)));
  const sweep = 2 * Math.asin(Math.max(-1, Math.min(1, chordLen / (2 * blendRadius))));
  const steps = Math.max(2, Math.ceil(sweep / Math.max(maxStep, 1e-9)));

  const approachD = Math.max(op.startDiameter, op.endDiameter) + 2 * SAFE_X_CLEAR;
  const moves: TurnMove[] = [
    { kind: "RAPID", x: approachD, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "RAPID", x: op.startDiameter, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "CUT", x: op.startDiameter, z: op.startZ, feedPerRev: op.params.feedPerRev },
  ];
  /*
   * Exact points ON the arc, not an approximation of its offset from the
   * chord. The first version interpolated the chord and pushed each point
   * out by a parabola; it claimed a 0.0005" tolerance and delivered
   * 0.0027" — five times worse, and stated with a confidence it had not
   * earned. Stepping the true arc leaves the chord sagitta as the ONLY
   * deviation, which is what the step count is derived to bound.
   *
   * Centre: the two candidates sit either side of the chord, and the
   * concavity picks which.
   */
  const nz = -dx / chordLen; // unit normal to the chord, in (z, radial)
  const nr = dz / chordLen;
  const mz = op.startZ + dz / 2;
  const mr = op.startDiameter / 2 + dx / 2;
  const half = Math.sqrt(Math.max(0, blendRadius * blendRadius - (chordLen / 2) * (chordLen / 2)));
  const side = concave ? 1 : -1;
  const cz = mz + nz * half * side;
  const cr = mr + nr * half * side;

  const a0 = Math.atan2(op.startDiameter / 2 - cr, op.startZ - cz);
  const a1 = Math.atan2(op.endDiameter / 2 - cr, op.endZ - cz);
  // Sweep the short way round: a blend between two adjacent diameters is a
  // minor arc, never the long way about the centre.
  let delta = a1 - a0;
  while (delta > Math.PI) delta -= 2 * Math.PI;
  while (delta < -Math.PI) delta += 2 * Math.PI;

  for (let i = 1; i <= steps; i++) {
    const ang = a0 + (delta * i) / steps;
    const z = cz + blendRadius * Math.cos(ang);
    const rad = cr + blendRadius * Math.sin(ang);
    moves.push({ kind: "CUT", x: Number((rad * 2).toFixed(5)), z: Number(z.toFixed(5)), feedPerRev: op.params.feedPerRev });
  }
  moves.push({ kind: "RAPID", x: approachD, z: op.endZ, feedPerRev: null });

  const arcLen = blendRadius * sweep;
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3(passMinutes(arcLen, op.params, (op.startDiameter + op.endDiameter) / 2)),
      assumptions: [
        "ESTIMATED: no acceleration model.",
        `R${blendRadius.toFixed(4)} ${concave ? "concave" : "convex"} blend chorded into ${steps} linear moves at a ${BLEND_CHORD_TOLERANCE.toFixed(4)}" chord tolerance — the post has no arc output, so the arc is not claimed as one.`,
      ],
      warnings: [compensationWarning(noseRadius!)],
    },
  };
}

/* ------------------------------------------------------------------ */
/* ID BORING                                                           */
/* ------------------------------------------------------------------ */

/**
 * Boring is not OD turning with the numbers negated, and the difference is
 * the one that breaks bars:
 *
 * - The cut runs OUTWARD. Roughing an OD walks the diameter down from stock;
 *   boring walks it up from the drilled hole to the finished size.
 * - The retract runs INWARD. On an OD you pull away by going to a larger X.
 *   Inside a bore a larger X is the wall — retracting "clear" the OD way
 *   drives the bar into the bore it just cut. Every retract here goes to a
 *   SMALLER diameter, and that is why the clearance is subtracted.
 * - The bar has to fit in the hole before any of this is a question. A
 *   boring bar cannot enter a hole smaller than itself, and it cannot cut a
 *   bore it cannot enter.
 *
 * Reach (length-to-diameter) is assessed separately, at the plan level, by
 * assessBoringBar — this is the geometry check, not the chatter one.
 */

/** Radial clearance from the bore wall on a retract. Diameter, inches. */
const BORE_X_CLEAR = 0.06;

function boreEntryCheck(
  op: TurnOperation,
  barDiameter: number | null,
): { reason: string } | null {
  if (op.startDiameter <= 0) {
    return {
      reason:
        "Boring starts from an existing hole. There is no hole recorded at this station — drill or centre-drill before the bar goes in.",
    };
  }
  if (op.endDiameter <= op.startDiameter) {
    return {
      reason: `Bore finishes at ⌀${op.endDiameter.toFixed(4)} from a ⌀${op.startDiameter.toFixed(4)} hole — a bore opens a hole up, and this removes nothing.`,
    };
  }
  if (Math.abs(op.endZ - op.startZ) <= 0) return { reason: "Zero-length cut." };
  if (barDiameter === null) {
    return {
      reason:
        "No boring bar diameter recorded for this station. Whether the bar fits the hole is the first question boring asks, and CANVAS will not assume a bar.",
    };
  }
  if (barDiameter >= op.startDiameter) {
    return {
      reason: `⌀${barDiameter.toFixed(4)} boring bar does not fit the ⌀${op.startDiameter.toFixed(4)} hole it has to enter.`,
    };
  }
  return null;
}

/** ID roughing: successive passes opening the hole out toward the bore. */
export function idBoreRoughToolpath(
  op: TurnOperation,
  barDiameter: number | null,
): TurnToolpathResult {
  if (op.params.doc <= 0) return { ok: false, reason: "Depth of cut must be positive." };
  const entry = boreEntryCheck(op, barDiameter);
  if (entry) return { ok: false, reason: entry.reason };

  const targetD = op.endDiameter - 2 * op.params.finishAllowance;
  if (targetD <= op.startDiameter) {
    return {
      ok: false,
      reason: `Finish allowance ${op.params.finishAllowance.toFixed(4)}" leaves the roughing pass nothing to cut between ⌀${op.startDiameter.toFixed(4)} and ⌀${op.endDiameter.toFixed(4)}.`,
    };
  }
  const cutLen = Math.abs(op.endZ - op.startZ);
  const radialTotal = (targetD - op.startDiameter) / 2;
  const passes = Math.max(1, Math.ceil(radialTotal / op.params.doc));
  const moves: TurnMove[] = [];
  let minutes = 0;
  for (let i = 1; i <= passes; i++) {
    // Opening OUT: each pass sits at a larger diameter than the last.
    const d = Math.min(targetD, op.startDiameter + 2 * op.params.doc * i);
    // Position at the pass diameter in free air AHEAD of the face, never
    // while entering the bore: X and Z do not move together in here.
    moves.push({ kind: "RAPID", x: d, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "CUT", x: d, z: op.endZ, feedPerRev: op.params.feedPerRev });
    // Come OFF the wall before travelling: inward, never outward.
    moves.push({ kind: "CUT", x: Math.max(0, d - 2 * BORE_X_CLEAR), z: op.endZ, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "RAPID", x: Math.max(0, d - 2 * BORE_X_CLEAR), z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    minutes += passMinutes(cutLen, op.params, (d + Math.max(op.startDiameter, d - 2 * op.params.doc)) / 2);
  }
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "ESTIMATED: no acceleration model; CSS approximated at each pass's mean diameter.",
        `Finish allowance ${op.params.finishAllowance.toFixed(4)}" left on diameter per side.`,
        `Retracts clear the bore wall by ${(2 * BORE_X_CLEAR).toFixed(3)}" on diameter, inward.`,
        "X and Z never move together inside the bore: the bar reaches its diameter in free air ahead of the face.",
      ],
      warnings: [],
    },
  };
}

/** ID finishing: one pass at size, plus spring passes. */
export function idBoreFinishToolpath(
  op: TurnOperation,
  barDiameter: number | null,
): TurnToolpathResult {
  const entry = boreEntryCheck(op, barDiameter);
  if (entry) return { ok: false, reason: entry.reason };

  const cutLen = Math.abs(op.endZ - op.startZ);
  const passes = 1 + Math.max(0, op.params.springPasses);
  const d = op.endDiameter;
  const clear = Math.max(0, d - 2 * BORE_X_CLEAR);
  const moves: TurnMove[] = [];
  let minutes = 0;
  for (let i = 0; i < passes; i++) {
    moves.push({ kind: "RAPID", x: d, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "CUT", x: d, z: op.endZ, feedPerRev: op.params.feedPerRev });
    // A finished bore is scratched by a tool dragged back along it under
    // pressure, so come off the wall before the Z move, every time.
    moves.push({ kind: "CUT", x: clear, z: op.endZ, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "RAPID", x: clear, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    minutes += passMinutes(cutLen, op.params, d);
  }
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "ESTIMATED: no acceleration model.",
        op.params.springPasses > 0 ? `${op.params.springPasses} spring pass(es) at full length.` : "No spring passes.",
        "Tool comes off the bore wall before every Z retract.",
      ],
      warnings: [],
    },
  };
}

/** Facing: from OD to centerline at the given Z. */
export function faceToolpath(op: TurnOperation, profile: RotationalProfile): TurnToolpathResult {
  const startD = profile.stockDiameter + 2 * SAFE_X_CLEAR;
  const moves: TurnMove[] = [
    { kind: "RAPID", x: startD, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "RAPID", x: startD, z: op.endZ, feedPerRev: null },
    { kind: "CUT", x: 0, z: op.endZ, feedPerRev: op.params.feedPerRev },
    { kind: "RAPID", x: startD, z: op.endZ + SAFE_Z_CLEAR, feedPerRev: null },
  ];
  const cutLen = profile.stockDiameter / 2;
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3(passMinutes(cutLen, op.params, profile.stockDiameter / 2)),
      assumptions: ["ESTIMATED: facing time uses the mean of the swept diameters; CSS spin-up not modelled."],
      warnings: [],
    },
  };
}

/** Plunge groove at Z, to depth, with peck retracts. */
export function grooveToolpath(op: TurnOperation, grooveWidth: number, toolWidth: number): TurnToolpathResult {
  if (toolWidth <= 0) return { ok: false, reason: "Groove tool width unknown — refusing to guess an insert." };
  if (grooveWidth < toolWidth) {
    return { ok: false, reason: `Groove ${grooveWidth.toFixed(3)}" is narrower than the ${toolWidth.toFixed(3)}" insert.` };
  }
  const plunges = Math.max(1, Math.ceil(grooveWidth / (toolWidth * 0.9)));
  const moves: TurnMove[] = [];
  let minutes = 0;
  const radial = (op.startDiameter - op.endDiameter) / 2;
  for (let i = 0; i < plunges; i++) {
    const z = op.startZ + Math.min(grooveWidth - toolWidth, i * toolWidth * 0.9);
    moves.push({ kind: "RAPID", x: op.startDiameter + 2 * SAFE_X_CLEAR, z, feedPerRev: null });
    moves.push({ kind: "CUT", x: op.endDiameter, z, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "RAPID", x: op.startDiameter + 2 * SAFE_X_CLEAR, z, feedPerRev: null });
    minutes += passMinutes(radial, op.params, (op.startDiameter + op.endDiameter) / 2);
  }
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: plunges,
      estimatedMinutes: r3(minutes),
      assumptions: ["ESTIMATED: plunge feed only; dwell at depth not modelled.", `${plunges} plunge(s) at 90% insert width.`],
      warnings: [],
    },
  };
}

/**
 * Threading: G32-style passes with square infeed, depth from pitch (0.6134×p
 * for 60° external threads), pass count from a fixed first-pass DOC schedule.
 * Feed IS the pitch; it is never retimed — the same law as rigid tapping.
 */
export function threadToolpath(op: TurnOperation, pitchIn: number): TurnToolpathResult {
  if (pitchIn <= 0) return { ok: false, reason: "Thread pitch unknown — a thread without a pitch is not a thread." };
  const majorD = op.startDiameter;
  const depth = 0.6134 * pitchIn; // radial, 60° V external
  const firstDoc = Math.min(0.012, depth / 2);
  const passes = Math.max(2, Math.ceil((depth / firstDoc) ** (2 / 3)) + 1);
  const cutLen = Math.abs(op.endZ - op.startZ);
  // The ID thread refuses this; the OD one silently emitted a stack of
  // zero-length passes with a zero-minute estimate — same law both sides.
  if (cutLen <= 0) return { ok: false, reason: "Zero-length thread." };
  const moves: TurnMove[] = [];
  for (let i = 1; i <= passes; i++) {
    // Constant-area infeed: depth_i = depth × sqrt(i/passes).
    const di = majorD - 2 * depth * Math.sqrt(i / passes);
    moves.push({ kind: "RAPID", x: majorD + 2 * SAFE_X_CLEAR, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "THREAD_PASS", x: di, z: op.endZ, feedPerRev: pitchIn });
    moves.push({ kind: "RAPID", x: majorD + 2 * SAFE_X_CLEAR, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
  }
  const rpm = op.params.rpm; // threading runs G97 fixed RPM, always
  const minutes = rpm > 0 ? (passes * cutLen) / (pitchIn * rpm) : 0;
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "Thread feed equals pitch and is never retimed.",
        "Constant-area infeed schedule; 60° external form depth 0.6134 × pitch.",
        "G97 fixed RPM — CSS is never used for threading.",
      ],
      warnings: [],
    },
  };
}

/** Part-off: single plunge to centre (or to bore) at the cutoff Z. */
export function partOffToolpath(op: TurnOperation, toolWidth: number): TurnToolpathResult {
  if (toolWidth <= 0) return { ok: false, reason: "Cutoff tool width unknown." };
  const radial = (op.startDiameter - op.endDiameter) / 2;
  const moves: TurnMove[] = [
    { kind: "RAPID", x: op.startDiameter + 2 * SAFE_X_CLEAR, z: op.startZ, feedPerRev: null },
    { kind: "CUT", x: op.endDiameter, z: op.startZ, feedPerRev: op.params.feedPerRev },
    { kind: "RAPID", x: op.startDiameter + 2 * SAFE_X_CLEAR, z: op.startZ, feedPerRev: null },
  ];
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3(passMinutes(radial, op.params, (op.startDiameter + op.endDiameter) / 2)),
      assumptions: ["ESTIMATED: constant feed to centre; falling-RPM CSS behaviour near centre not modelled."],
      warnings: ["Part-off drops the part unless a catcher, sub-spindle or tailstock manages it — see the part-off review."],
    },
  };
}

/** Drilling on centre (center drill, drill): Z plunge at X0. */
/* ------------------------------------------------------------------ */
/* ID GROOVING AND THREADING — boring's law applies                    */
/* ------------------------------------------------------------------ */

/**
 * Everything inside a bore obeys the rule the boring engines established:
 * clear is INWARD. An OD groove retracts to a bigger X; an ID groove
 * retracting to a bigger X is parked in the groove it just cut. And before
 * any of it, the tool has to fit the hole — the tool record states the
 * smallest bore it enters (minBoreDiameter), and an unrecorded value is a
 * refusal, not an assumption, because "does it fit" is the first question
 * and CANVAS does not answer it with a guess.
 */
function idEntryCheck(boreDiameter: number, minBore: number | null | undefined): { reason: string } | null {
  if (boreDiameter <= 0) {
    return { reason: "This operation runs inside a bore, and there is no bore recorded at this operation. Drill or bore first." };
  }
  if (minBore === null || minBore === undefined) {
    return {
      reason:
        "The tool record does not state the smallest bore this tool enters (minBoreDiameter). Whether it fits the hole is the first question an ID operation asks, and CANVAS will not assume it.",
    };
  }
  if (minBore > boreDiameter) {
    return { reason: `This tool needs a ⌀${minBore.toFixed(4)} bore to enter and the bore is ⌀${boreDiameter.toFixed(4)}.` };
  }
  return null;
}

/**
 * ID groove: plunge OUTWARD from the bore surface, retract INWARD.
 * startDiameter is the bore, endDiameter the groove root — a groove inside
 * a hole is BIGGER than the hole, the mirror of the OD case.
 */
export function grooveIdToolpath(
  op: TurnOperation,
  grooveWidth: number,
  toolWidth: number,
  minBore: number | null,
): TurnToolpathResult {
  if (toolWidth <= 0) return { ok: false, reason: "Groove tool width unknown — refusing to guess an insert." };
  if (grooveWidth < toolWidth) {
    return { ok: false, reason: `Groove ${grooveWidth.toFixed(3)}" is narrower than the ${toolWidth.toFixed(3)}" insert.` };
  }
  const entry = idEntryCheck(op.startDiameter, minBore);
  if (entry) return { ok: false, reason: entry.reason };
  if (op.endDiameter <= op.startDiameter) {
    return {
      ok: false,
      reason: `Groove root ⌀${op.endDiameter.toFixed(4)} is not larger than the ⌀${op.startDiameter.toFixed(4)} bore — an internal groove opens outward, and this one removes nothing.`,
    };
  }

  const clearX = Math.max(0, op.startDiameter - 2 * BORE_X_CLEAR);
  const plunges = Math.max(1, Math.ceil(grooveWidth / (toolWidth * 0.9)));
  const radial = (op.endDiameter - op.startDiameter) / 2;
  const moves: TurnMove[] = [];
  let minutes = 0;
  // In through the mouth at clear diameter, once — X and Z never together.
  moves.push({ kind: "RAPID", x: clearX, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
  for (let i = 0; i < plunges; i++) {
    const z = op.startZ + Math.min(grooveWidth - toolWidth, i * toolWidth * 0.9);
    moves.push({ kind: "RAPID", x: clearX, z, feedPerRev: null });
    // Plunge OUTWARD to the groove root, back INWARD to clear.
    moves.push({ kind: "CUT", x: op.endDiameter, z, feedPerRev: op.params.feedPerRev });
    moves.push({ kind: "CUT", x: clearX, z, feedPerRev: op.params.feedPerRev });
    minutes += passMinutes(radial, op.params, (op.startDiameter + op.endDiameter) / 2);
  }
  // Back out of the bore at clear diameter.
  moves.push({ kind: "RAPID", x: clearX, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: plunges,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "ESTIMATED: plunge feed only; dwell at depth not modelled.",
        `${plunges} plunge(s) at 90% insert width.`,
        `Retracts clear the bore inward to ⌀${clearX.toFixed(4)} before any Z move.`,
      ],
      warnings: [],
    },
  };
}

/**
 * Internal 60° thread height as a fraction of pitch — shallower than the
 * external 0.6134 because the internal form is truncated at the crest
 * (5/8H engagement, the standard nut form). Stated, not tuned.
 */
const ID_THREAD_DEPTH_FACTOR = 0.5413;

/**
 * ID thread: passes open OUTWARD from the minor diameter (the bore) toward
 * the major. Feed is the pitch, G97 fixed RPM, same law as the OD thread —
 * plus boring's: every between-pass retract is inward, and the bar leaves
 * the bore along the clear diameter.
 */
export function threadIdToolpath(op: TurnOperation, pitchIn: number, minBore: number | null): TurnToolpathResult {
  if (pitchIn <= 0) return { ok: false, reason: "Thread pitch unknown — a thread without a pitch is not a thread." };
  const entry = idEntryCheck(op.startDiameter, minBore);
  if (entry) return { ok: false, reason: entry.reason };
  const cutLen = Math.abs(op.endZ - op.startZ);
  if (cutLen <= 0) return { ok: false, reason: "Zero-length thread." };

  const minorD = op.startDiameter; // the bore is the minor diameter
  const depth = ID_THREAD_DEPTH_FACTOR * pitchIn; // radial
  const firstDoc = Math.min(0.012, depth / 2);
  const passes = Math.max(2, Math.ceil((depth / firstDoc) ** (2 / 3)) + 1);
  const clearX = Math.max(0, minorD - 2 * BORE_X_CLEAR);
  const moves: TurnMove[] = [];
  for (let i = 1; i <= passes; i++) {
    // Constant-area infeed, opening OUT: depth_i = depth × sqrt(i/passes).
    const di = minorD + 2 * depth * Math.sqrt(i / passes);
    moves.push({ kind: "RAPID", x: clearX, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "RAPID", x: di, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
    moves.push({ kind: "THREAD_PASS", x: di, z: op.endZ, feedPerRev: pitchIn });
    // Off the flank INWARD, then out of the bore at clear diameter.
    moves.push({ kind: "RAPID", x: clearX, z: op.endZ, feedPerRev: null });
    moves.push({ kind: "RAPID", x: clearX, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null });
  }
  const rpm = op.params.rpm; // threading runs G97 fixed RPM, always
  const minutes = rpm > 0 ? (passes * cutLen) / (pitchIn * rpm) : 0;
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes,
      estimatedMinutes: r3(minutes),
      assumptions: [
        "Thread feed equals pitch and is never retimed.",
        `Constant-area infeed; 60° internal form depth ${ID_THREAD_DEPTH_FACTOR} × pitch (5/8H crest truncation).`,
        "G97 fixed RPM — CSS is never used for threading.",
        `Between-pass retracts clear the thread inward to ⌀${clearX.toFixed(4)} before leaving the bore.`,
      ],
      warnings: [],
    },
  };
}

/* ------------------------------------------------------------------ */
/* TAP AND REAM — centreline operations with hard rules                */
/* ------------------------------------------------------------------ */

/**
 * The spindle cap for tapping. A tap is driven into a blind or through hole
 * with its feed locked to the spindle; the slower it runs, the more the
 * control's synchronisation and the machinist's ear can save a broken tap.
 * Same convention as the mill engine's rigid-tap cap.
 */
const TAP_RPM_CAP = 600;

/**
 * Tap: the feed is not chosen, it IS the thread.
 *
 * In G99 (feed per revolution — this post's mode) the tap's feed word is
 * the pitch, exactly. A tap fed at anything else cross-threads or breaks:
 * there is no "conservative" tap feed the way there is a conservative
 * turning feed, which is why params.feedPerRev is OVERRIDDEN here rather
 * than trusted, and the override is stated.
 *
 * The reversal at the bottom cannot be expressed as moves — TurnMove has no
 * spindle state. The toolpath therefore carries `rigidTapCycle: true` and
 * the post emits a canned cycle (M29/G84, closed by G80) that owns the
 * spindle, exactly as the mill's Haas post does. A post without the cycle
 * must refuse the operation, not emit unsynchronised G1 moves.
 */
export function tapToolpath(op: TurnOperation, pitchIn: number | null): TurnToolpathResult {
  if (pitchIn === null || !(pitchIn > 0)) {
    return {
      ok: false,
      reason:
        "No thread pitch. A tap's feed IS its pitch — record the thread designation on the target segment; CANVAS will not invent one.",
    };
  }
  const depth = Math.abs(op.endZ - op.startZ);
  if (depth <= 0) return { ok: false, reason: "Zero tapping depth." };
  if (op.startDiameter <= 0) {
    return {
      ok: false,
      reason: "Tapping needs a drilled hole. There is no hole recorded at this operation — drill to the tap-drill size first.",
    };
  }
  if (op.params.cssEnabled) {
    return {
      ok: false,
      reason: "CSS while tapping is refused: the cycle owns the spindle, and a surface-speed override mid-tap breaks the synchronisation that keeps the tap alive.",
    };
  }

  const rpm = Math.min(op.params.rpm, TAP_RPM_CAP);
  const warnings: string[] = [];
  if (Math.abs(op.params.feedPerRev - pitchIn) > 1e-6) {
    warnings.push(
      `Programmed feed ${op.params.feedPerRev.toFixed(4)}"/rev overridden to the ${pitchIn.toFixed(4)}" pitch — a tap's feed is its thread.`,
    );
  }
  if (op.params.rpm > TAP_RPM_CAP) {
    warnings.push(`Spindle capped at ${TAP_RPM_CAP} RPM for tapping (was ${op.params.rpm}).`);
  }

  // In and back out at the synchronised feed. The post replaces these with
  // the canned cycle; they exist so simulation and timing see the motion.
  const moves: TurnMove[] = [
    { kind: "RAPID", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "CUT", x: 0, z: op.startZ - depth, feedPerRev: pitchIn },
    { kind: "CUT", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: pitchIn },
  ];
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      // Down and back out, both at pitch feed, both counted.
      estimatedMinutes: r3((2 * depth) / (pitchIn * rpm)),
      assumptions: [
        "ESTIMATED: in and out at the synchronised feed; reversal dwell not modelled.",
        `Feed locked to the ${pitchIn.toFixed(4)}" pitch at ${rpm} RPM — G99 feed per revolution.`,
        "G97 fixed RPM on centre — CSS at X0 is meaningless.",
      ],
      warnings,
      rigidTapCycle: true,
      spindleRpmOverride: rpm,
    },
  };
}

/**
 * How much a reamer is allowed to remove, on diameter. Below the floor it
 * burnishes instead of cutting and the hole goes glassy and undersize;
 * above the ceiling it is being used as a drill and cuts oversize, bell-
 * mouthed, or grabs. Machinery's Handbook territory; stated, not tuned.
 */
export const REAM_MIN_STOCK = 0.003;
export const REAM_MAX_STOCK = 0.015;

/**
 * Ream: a reamer follows a hole, it does not make one.
 *
 * The reamer feeds in AND OUT at cutting feed, spindle forward the whole
 * time — a reamer is never reversed (it chips the flute edges) and never
 * rapided out of the hole it just sized (it drags a spiral scratch down
 * the finish it exists to produce).
 */
export function reamToolpath(op: TurnOperation, pitchIn: number | null): TurnToolpathResult {
  void pitchIn;
  const depth = Math.abs(op.endZ - op.startZ);
  if (depth <= 0) return { ok: false, reason: "Zero reaming depth." };
  if (op.startDiameter <= 0) {
    return {
      ok: false,
      reason: "A reamer follows a hole, it does not make one. There is no drilled hole recorded at this operation.",
    };
  }
  if (op.endDiameter <= op.startDiameter) {
    return {
      ok: false,
      reason: `Reaming to ⌀${op.endDiameter.toFixed(4)} from a ⌀${op.startDiameter.toFixed(4)} hole removes nothing.`,
    };
  }
  const removal = op.endDiameter - op.startDiameter;
  if (removal < REAM_MIN_STOCK) {
    return {
      ok: false,
      reason: `${removal.toFixed(4)}" on diameter is below the ${REAM_MIN_STOCK.toFixed(3)}" a reamer needs to cut — it will burnish instead, and the hole comes out glassy and undersize. Drill smaller.`,
    };
  }
  if (removal > REAM_MAX_STOCK) {
    return {
      ok: false,
      reason: `${removal.toFixed(4)}" on diameter is more than the ${REAM_MAX_STOCK.toFixed(3)}" a reamer should take — that is a drilling cut, and reamed that way the hole comes out oversize or bell-mouthed. Drill closer to size.`,
    };
  }

  const moves: TurnMove[] = [
    { kind: "RAPID", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "CUT", x: 0, z: op.startZ - depth, feedPerRev: op.params.feedPerRev },
    // OUT AT FEED. Not a rapid: a rapid out of a reamed hole drags a spiral
    // scratch down the finish the reamer exists to produce.
    { kind: "CUT", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: op.params.feedPerRev },
  ];
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3((2 * depth + SAFE_Z_CLEAR) / Math.max(1e-9, op.params.feedPerRev * effectiveRpm(op.params, op.endDiameter))),
      assumptions: [
        "ESTIMATED: in and out at cutting feed; no dwell at depth.",
        `Removing ${removal.toFixed(4)}" on diameter — inside the ${REAM_MIN_STOCK.toFixed(3)}"–${REAM_MAX_STOCK.toFixed(3)}" reaming window.`,
        "G97 fixed RPM on centre — CSS at X0 is meaningless.",
      ],
      warnings: [],
    },
  };
}

export function centerlineDrillToolpath(op: TurnOperation): TurnToolpathResult {
  const depth = Math.abs(op.endZ - op.startZ);
  if (depth <= 0) return { ok: false, reason: "Zero drilling depth." };
  const moves: TurnMove[] = [
    { kind: "RAPID", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
    { kind: "CUT", x: 0, z: op.startZ - depth, feedPerRev: op.params.feedPerRev },
    { kind: "RAPID", x: 0, z: op.startZ + SAFE_Z_CLEAR, feedPerRev: null },
  ];
  return {
    ok: true,
    toolpath: {
      operationNumber: op.operationNumber,
      type: op.type,
      moves,
      passes: 1,
      estimatedMinutes: r3(passMinutes(depth, op.params, 0.1)),
      assumptions: ["ESTIMATED: single plunge, no peck modelling.", "G97 fixed RPM on centre — CSS at X0 is meaningless."],
      warnings: [],
    },
  };
}

/**
 * What the engine needs to know about the tool and the geometry that is not
 * in the operation itself. Every field is nullable and every null is a
 * refusal at the operation that needs it — never a substituted value.
 */
export interface TurnToolContext {
  /** Groove/cutoff insert width at this station. */
  toolWidth?: number | null;
  /** Thread pitch, inches, parsed from the segment's designation. */
  pitchIn?: number | null;
  /** Boring bar diameter at this station. */
  barDiameter?: number | null;
  /** Insert nose radius at this station. Decides chamfers and blends. */
  noseRadius?: number | null;
  /** Blend radius from the target segment, inches. */
  blendRadius?: number | null;
  /** True when the feature is inside the part (a bore), from the segment. */
  internal?: boolean | null;
  /** Whether a blend curves into the material. Null = not recorded. */
  concave?: boolean | null;
  /**
   * Smallest bore this station's tool fits into, from the tool record.
   * The first question every ID operation asks.
   */
  minBoreDiameter?: number | null;
}

export function generateTurnToolpath(
  op: TurnOperation,
  profile: RotationalProfile,
  ctx: TurnToolContext = {},
): TurnToolpathResult {
  const { toolWidth = null, pitchIn = null, barDiameter = null } = ctx;
  switch (op.type) {
    case "FACE":
      return faceToolpath(op, profile);
    case "OD_ROUGH":
      return odRoughToolpath(op, profile);
    case "OD_FINISH":
      return odFinishToolpath(op);
    case "ID_BORE_ROUGH":
      return idBoreRoughToolpath(op, barDiameter);
    case "ID_BORE_FINISH":
      return idBoreFinishToolpath(op, barDiameter);
    case "GROOVE_ID":
      return grooveIdToolpath(op, Math.abs(op.endZ - op.startZ), toolWidth ?? 0, ctx.minBoreDiameter ?? null);
    case "THREAD_ID":
      return threadIdToolpath(op, pitchIn ?? 0, ctx.minBoreDiameter ?? null);
    case "GROOVE_OD":
      return grooveToolpath(op, Math.abs(op.endZ - op.startZ), toolWidth ?? 0);
    case "THREAD_OD":
      return threadToolpath(op, pitchIn ?? 0);
    case "CHAMFER":
      return chamferToolpath(op, ctx.noseRadius ?? null);
    case "RADIUS_BLEND":
      return radiusBlendToolpath(op, ctx.blendRadius ?? null, ctx.noseRadius ?? null, ctx.concave ?? null);
    case "PART_OFF":
      return partOffToolpath(op, toolWidth ?? 0);
    case "CENTER_DRILL":
    case "ID_DRILL":
      return centerlineDrillToolpath(op);
    case "TAP":
      return tapToolpath(op, ctx.pitchIn ?? null);
    case "REAM":
      return reamToolpath(op, ctx.pitchIn ?? null);
    default:
      return { ok: false, reason: `${op.type} has no turning engine yet. It is listed, not faked.` };
  }
}

const r3 = (v: number) => Number(v.toFixed(3));
