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

export function generateTurnToolpath(
  op: TurnOperation,
  profile: RotationalProfile,
  toolWidth: number | null,
  pitchIn: number | null,
): TurnToolpathResult {
  switch (op.type) {
    case "FACE":
      return faceToolpath(op, profile);
    case "OD_ROUGH":
      return odRoughToolpath(op, profile);
    case "OD_FINISH":
      return odFinishToolpath(op);
    case "GROOVE_OD":
      return grooveToolpath(op, Math.abs(op.endZ - op.startZ), toolWidth ?? 0);
    case "THREAD_OD":
      return threadToolpath(op, pitchIn ?? 0);
    case "PART_OFF":
      return partOffToolpath(op, toolWidth ?? 0);
    case "CENTER_DRILL":
    case "ID_DRILL":
      return centerlineDrillToolpath(op);
    default:
      return { ok: false, reason: `${op.type} has no turning engine yet. It is listed, not faked.` };
  }
}

const r3 = (v: number) => Number(v.toFixed(3));
