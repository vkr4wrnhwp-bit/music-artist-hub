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
  "DRILL",
  "PECK_DRILL",
  "CONTOUR_2D",
  "CHAMFER",
  "ENGRAVE",
  "SOFT_JAW_POCKET",
];

/** Operation types that exist as interfaces only. The UI labels these clearly. */
export const PLACEHOLDER_OPERATIONS: OperationType[] = ["ADAPTIVE_2D", "BORE", "TAP"];

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

export interface Move {
  type: MoveType;
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
  /** SFM window for the material being cut. */
  materialSfmMin: number;
  materialSfmMax: number;
  materialName: string;
  /** Rapid rate for cycle time computation, in/min. */
  rapidRate: number;
  maxSpindleRPM: number;
  maxFeed: number;
}
