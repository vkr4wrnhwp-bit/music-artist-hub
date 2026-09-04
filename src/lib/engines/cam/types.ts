import type { Tool } from "@/lib/domain/shop";

/**
 * CAM ARCHITECTURE — see /docs/CAM_ENGINE.md
 *
 * The single most important rule in CANVAS: an LLM never emits machine motion.
 * The pipeline is
 *
 *   USER INTENT → VALIDATED PART MODEL → MANUFACTURING PLAN →
 *   DETERMINISTIC TOOLPATH ENGINE → MACHINE CONSTRAINT VALIDATION →
 *   WORKHOLDING VALIDATION → SIMULATION → POST → NC VERIFICATION →
 *   HUMAN APPROVAL → EXPORT
 *
 * The AI layer may only propose an OperationRequest — the same structure a
 * human fills in by hand. Everything downstream of that is arithmetic.
 */

export const OPERATION_TYPES = [
  "FACE",
  "POCKET_2D",
  "ADAPTIVE_2D",
  "DRILL",
  "PECK_DRILL",
  "BORE",
  "TAP",
  "CONTOUR_2D",
  "CHAMFER",
  "ENGRAVE",
  "SOFT_JAW_POCKET",
] as const;
export type OperationType = (typeof OPERATION_TYPES)[number];

/** Operation types whose toolpath engine is fully implemented in Phase 1. */
export const IMPLEMENTED_OPERATIONS: OperationType[] = [
  "FACE",
  "POCKET_2D",
  "ADAPTIVE_2D",
  "DRILL",
  "PECK_DRILL",
  "BORE",
  "TAP",
  "CONTOUR_2D",
  "CHAMFER",
  "ENGRAVE",
  "SOFT_JAW_POCKET",
];

/**
 * Operation types that exist as interfaces only. Empty since ADAPTIVE_2D
 * gained its engine — kept because the honesty machinery around it (labels,
 * pre-flight wording, post comments) is exactly what a future operation
 * type will need on day one.
 */
export const PLACEHOLDER_OPERATIONS: OperationType[] = [];

export interface CuttingParameters {
  /** Spindle speed, RPM. */
  rpm: number;
  /** Feed, in/min. */
  feed: number;
  /** Plunge feed, in/min. */
  plungeFeed: number;
  /** Axial depth per pass. */
  stepdown: number;
  /** Radial engagement as a fraction of tool diameter. */
  stepover: number;
  /** Surface speed used to derive rpm, SFM. */
  sfm: number;
  /** Chip load used to derive feed, in/tooth. */
  chipload: number;
  coolant: "FLOOD" | "MIST" | "AIR" | "THROUGH_SPINDLE" | "OFF";
  /** Material left for a finishing pass. */
  stockToLeave: number;
}

export interface OperationRequest {
  id: string;
  type: OperationType;
  label: string;
  featureId: string | null;
  toolId: string;
  setupId: string;
  /**
   * ROUGHING OR FINISHING, AS A PROPERTY OF THE OPERATION.
   *
   * `stockToLeave` used to be the only thing that distinguished them, which
   * made a finish pass a roughing pass with a different number in it: the same
   * mid-range chipload, the same stepdown, the same depth ladder. Roughing
   * feeds on the final wall, and a witness line at every depth step — on the
   * ±0.0005" features the inspection engine reasons so carefully about.
   *
   * Absent means ROUGH, because that is what every operation was before this
   * existed and a missing value must not silently change what an old plan does.
   */
  pass?: "ROUGH" | "FINISH";
  /** Optional overrides. Anything omitted is derived from tool + material. */
  overrides?: Partial<CuttingParameters>;
  /** Z of the top of material for this operation. */
  topZ: number;
  /** Final depth, absolute Z (negative into the part). */
  finalZ: number;
  clearanceZ: number;
  retractZ: number;
}

export const MOVE_TYPES = ["RAPID", "CUT", "PLUNGE", "LEAD_IN", "LEAD_OUT", "RETRACT", "ARC"] as const;
export type MoveType = (typeof MOVE_TYPES)[number];

/**
 * WHERE THE PROGRAM SENDS THE TOOL, WHEN THE CONTROL IS DOING THE OFFSETTING.
 *
 * `x`/`y` on a Move are always the CUTTER CENTRE — that is what the simulator
 * sweeps, what cycle time measures, and what every collision check reasons
 * about. When cutter compensation is active the PROGRAM carries a different
 * point: the part boundary, with the control offsetting by the value in the D
 * register. Both are needed, and conflating them is how a simulator ends up
 * proving a path half a tool width from the one that gets cut.
 *
 * `side` is which side of the programmed path the cutter runs on, in the
 * direction of travel — LEFT is G41, RIGHT is G42.
 */
export interface ProgrammedPoint {
  x: number;
  y: number;
  /** Arc centre offsets in PROGRAMMED coordinates, for an arc block. */
  i?: number;
  j?: number;
  side: "LEFT" | "RIGHT";
  /** Turn compensation on over this move (G41/G42 with the D register). */
  activate?: boolean;
  /** Turn it off over this move (G40). */
  deactivate?: boolean;
}

export interface Move {
  type: MoveType;
  /** Cutter centre. */
  x: number;
  y: number;
  z: number;
  /** in/min. Null for rapids. */
  feed: number | null;
  /** Arc center offsets, present only for ARC moves. */
  i?: number;
  j?: number;
  /** Arc direction. */
  cw?: boolean;
  /**
   * The point the PROGRAM carries, when it is not the cutter centre. Absent
   * means the program and the cutter centre are the same point.
   */
  program?: ProgrammedPoint;
}

/**
 * A hole-making operation, as the control's own cycle.
 *
 * Drilling used to leave the post writing long-hand `G1` plunges and retracts.
 * It cuts, but it is not what anybody expects to read at the control, and it
 * gives up everything the control does better: `G83` chip-break timing, dwell
 * at the bottom, retract to R rather than all the way to Z, and single-block
 * stepping through one cycle instead of forty lines.
 *
 * The descriptor is produced by the engine ALONGSIDE the move list and from the
 * same numbers, never pattern-matched out of the moves afterwards. Both have to
 * describe the same motion: the simulator walks the moves and the machine runs
 * the cycle, and if those two disagree the simulation is proving a program that
 * will not run. `Q` and `R` are therefore the same peck increment and the same
 * retract plane the moves were built from.
 *
 * A post whose control does not have these cycles — GRBL has none at all —
 * emits the moves instead and says so. That is correct motion in more blocks,
 * which beats a cycle the control will fault on.
 */
export interface CannedCycle {
  /** G81 drill, G83 peck, G84 rigid tap. */
  code: "G81" | "G83" | "G84";
  x: number;
  y: number;
  /** Final depth, absolute. */
  z: number;
  /** Retract plane, absolute. The same plane the move list retracts to. */
  r: number;
  /** Peck increment for G83. Absent otherwise. */
  q?: number;
  /** Feed. For a tap this is pitch × rpm and must not be altered. */
  feed: number;
  /** Spindle speed the cycle runs at. */
  rpm: number;
}

export interface Toolpath {
  operationId: string;
  type: OperationType;
  toolId: string;
  toolNumber: number;
  moves: Move[];
  parameters: CuttingParameters;
  /** Minutes. Computed from actual move lengths, not estimated by a model. */
  cycleTimeMinutes: number;
  /** Cubic inches of material this operation removes. */
  materialRemoved: number;
  /** Length of cutting moves, inches. Feeds tool-wear costing. */
  cuttingDistance: number;
  warnings: string[];
  /** True when the engine could not produce real motion for this type. */
  isPlaceholder: boolean;
  /** Present for hole-making, so a post can emit the control's own cycle. */
  cannedCycle?: CannedCycle;
}

export interface ToolpathError {
  operationId: string;
  reason: string;
  recommendations: string[];
}

export type ToolpathResult =
  | { ok: true; toolpath: Toolpath }
  | { ok: false; error: ToolpathError };

export interface MachiningContext {
  tool: Tool;
  /**
   * SFM window for the material being cut. Null when the shop has no record
   * of this material — and then no motion is produced for it. Surface speed
   * is what sets the spindle, and a default window is a different material's
   * numbers wearing this one's name.
   */
  materialSfmMin: number | null;
  materialSfmMax: number | null;
  materialName: string;
  /** Rapid rate for cycle time computation, in/min. */
  rapidRate: number;
  maxSpindleRPM: number;
  maxFeed: number;
}
