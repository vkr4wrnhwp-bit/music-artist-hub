/**
 * MACHINE TELEMETRY — architecture only. NOT CONNECTED.
 *
 * These interfaces define the shapes CANVAS will consume when a real
 * telemetry source exists (MTConnect, OPC UA, controller logs, CSV
 * import). Nothing in the product claims live telemetry until a source
 * reports CONNECTED — and no source can, because no adapter is built.
 * The UI renders this status verbatim; do not soften it.
 *
 * The long-term objective: calibrate estimated load and cycle time
 * against what the shop's machines actually did — spindle load samples
 * against the engagement model, actual cycles against the time model,
 * tool-life data against consumption estimates.
 */

export type TelemetryProtocol = "MTCONNECT" | "OPC_UA" | "CONTROLLER_LOG" | "CSV_IMPORT";

export interface MachineTelemetrySource {
  id: string;
  machineId: string;
  protocol: TelemetryProtocol;
  endpoint: string | null;
  status: "NOT_CONNECTED"; // the only value that exists today
  lastSampleAt: string | null;
}

export interface SpindleLoadSample {
  sourceId: string;
  timestampIso: string;
  /** Percent of rated spindle load. */
  loadPct: number;
  rpm: number | null;
}

export interface FeedSample {
  sourceId: string;
  timestampIso: string;
  actualFeedIpm: number;
  overridePct: number | null;
}

export interface ActualCycleSample {
  sourceId: string;
  programNumber: string | null;
  startedAtIso: string;
  cycleMinutes: number;
  alarms: string[];
}

export interface ToolLifeSample {
  sourceId: string;
  toolNumber: number;
  timestampIso: string;
  minutesInCut: number;
  conditionNote: string | null;
}

/** Every source the product can name today, with its honest status. */
export const TELEMETRY_SOURCES: { protocol: TelemetryProtocol; label: string; status: "NOT_CONNECTED" }[] = [
  { protocol: "MTCONNECT", label: "MTConnect agent", status: "NOT_CONNECTED" },
  { protocol: "OPC_UA", label: "OPC UA server", status: "NOT_CONNECTED" },
  { protocol: "CONTROLLER_LOG", label: "Controller log import", status: "NOT_CONNECTED" },
  { protocol: "CSV_IMPORT", label: "CSV cycle import", status: "NOT_CONNECTED" },
];
