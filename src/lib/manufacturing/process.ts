/**
 * MANUFACTURING PROCESS — the multi-process spine.
 *
 * CANVAS began as a 3-axis milling system. Turning is the second first-class
 * process; everything else is architecture with its status stated. The
 * SUPPORT map is the single source of truth the UI reads — a process is
 * REAL, DEVELOPMENT or FUTURE here, and nowhere else.
 */

export const MANUFACTURING_PROCESSES = [
  "MILL_3_AXIS",
  "MILL_4_AXIS",
  "MILL_5_AXIS",
  "TURN_2_AXIS",
  "TURN_LIVE_TOOLING",
  "MILL_TURN",
  "SWISS",
  "ROUTER",
  "ADDITIVE",
  "HYBRID",
] as const;
export type ManufacturingProcess = (typeof MANUFACTURING_PROCESSES)[number];

export type ProcessSupport = "REAL" | "DEVELOPMENT" | "FUTURE";

export const PROCESS_SUPPORT: Record<ManufacturingProcess, ProcessSupport> = {
  MILL_3_AXIS: "REAL",
  TURN_2_AXIS: "REAL",
  // Architecture exists (capability flags, feature vocabulary); no CAM, no
  // posts, no validation. The UI must say DEVELOPMENT wherever these appear.
  TURN_LIVE_TOOLING: "DEVELOPMENT",
  MILL_TURN: "DEVELOPMENT",
  // Documented intentions only.
  MILL_4_AXIS: "FUTURE",
  MILL_5_AXIS: "FUTURE",
  SWISS: "FUTURE",
  ROUTER: "FUTURE",
  ADDITIVE: "FUTURE",
  HYBRID: "FUTURE",
};

export const PROCESS_LABEL: Record<ManufacturingProcess, string> = {
  MILL_3_AXIS: "3-axis mill",
  MILL_4_AXIS: "4-axis mill",
  MILL_5_AXIS: "5-axis mill",
  TURN_2_AXIS: "2-axis lathe",
  TURN_LIVE_TOOLING: "Lathe with live tooling",
  MILL_TURN: "Mill-turn",
  SWISS: "Swiss",
  ROUTER: "Router",
  ADDITIVE: "Additive",
  HYBRID: "Hybrid",
};

/**
 * Live-tooling machine capability flags — architecture for the future
 * process, carried on the lathe machine record. Their presence never
 * implies live-tooling CAM exists; PROCESS_SUPPORT says what exists.
 */
export interface LiveToolingCapability {
  hasCaxis: boolean;
  hasYaxis: boolean;
  hasLiveTooling: boolean;
  liveToolStations: number | null;
  cAxisIndexing: boolean;
  continuousCaxis: boolean;
  polarInterpolation: boolean;
  maxLiveToolRPM: number | null;
  maxLiveToolTorque: number | null;
}
