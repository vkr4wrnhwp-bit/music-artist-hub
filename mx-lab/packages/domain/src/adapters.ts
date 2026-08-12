import type { FutureFlashJob, SignalQuality, TelemetryChannelDef } from './types';

/**
 * Hardware adapter boundary (section 23). Phase 1 ships only the simulated
 * implementation. The interface is deliberately read-only: there are no
 * ECU-control methods, and none may be added before Phase 4 authorization.
 */

export interface DeviceIdentity {
  deviceId: string;
  kind: 'MX_NODE';
  hardwareRev: string;
  firmware: string;
  simulated: boolean;
}

export interface DeviceCapabilities {
  channels: string[];
  gps: boolean;
  imu: boolean;
  storageBytes: number;
  modes: Array<'test' | 'competition'>;
}

export interface ConnectionResult {
  connected: boolean;
  transport: 'SIMULATED' | 'usb' | 'serial' | 'can' | 'ble' | 'wifi' | 'dock';
  detail: string;
}

export interface LoggingConfiguration {
  channelIds: string[];
  mode: 'test' | 'competition';
}

export interface LoggingSession { loggingId: string; startedAt: string }
export interface LoggingSummary { loggingId: string; samples: number; durationS: number }
export interface TelemetryFile { sessionId: string; format: 'sim-v1'; simSeed: number }
export interface DeviceDiagnostics {
  batteryPct: number;
  storagePct: number;
  channelQuality: Record<string, SignalQuality>;
  radioDisabled: boolean;
  clockDriftMs: number;
}

export interface TelemetryHardwareAdapter {
  identify(): Promise<DeviceIdentity>;
  getCapabilities(): Promise<DeviceCapabilities>;
  connect(): Promise<ConnectionResult>;
  disconnect(): Promise<void>;
  getChannelDefinitions(): Promise<TelemetryChannelDef[]>;
  startLogging(config: LoggingConfiguration): Promise<LoggingSession>;
  stopLogging(): Promise<LoggingSummary>;
  downloadSession(sessionId: string): Promise<TelemetryFile>;
  getDiagnostics(): Promise<DeviceDiagnostics>;
}

/** The only Phase 1 adapter. It cannot be mistaken for hardware: every
 *  surface it exposes carries `simulated: true` / SIMULATED transport. */
export class SimulatedMxNodeAdapter implements TelemetryHardwareAdapter {
  constructor(
    private deviceId: string,
    private channelDefs: TelemetryChannelDef[],
    private simSeedForSession: (sessionId: string) => number,
  ) {}

  async identify(): Promise<DeviceIdentity> {
    return { deviceId: this.deviceId, kind: 'MX_NODE', hardwareRev: 'SIM-A1', firmware: 'sim-0.9.2', simulated: true };
  }
  async getCapabilities(): Promise<DeviceCapabilities> {
    return {
      channels: this.channelDefs.map((c) => c.id),
      gps: true, imu: true, storageBytes: 32 * 1024 ** 3,
      modes: ['test', 'competition'],
    };
  }
  async connect(): Promise<ConnectionResult> {
    return { connected: true, transport: 'SIMULATED', detail: 'Simulated MX Node — no physical hardware present.' };
  }
  async disconnect(): Promise<void> { /* nothing to release */ }
  async getChannelDefinitions(): Promise<TelemetryChannelDef[]> {
    return this.channelDefs.map((c) => ({ ...c, quality: 'Simulated' as const }));
  }
  async startLogging(_config: LoggingConfiguration): Promise<LoggingSession> {
    return { loggingId: `sim-log-${Date.now()}`, startedAt: new Date().toISOString() };
  }
  async stopLogging(): Promise<LoggingSummary> {
    return { loggingId: 'sim-log', samples: 0, durationS: 0 };
  }
  async downloadSession(sessionId: string): Promise<TelemetryFile> {
    return { sessionId, format: 'sim-v1', simSeed: this.simSeedForSession(sessionId) };
  }
  async getDiagnostics(): Promise<DeviceDiagnostics> {
    return { batteryPct: 87, storagePct: 22, channelQuality: {}, radioDisabled: true, clockDriftMs: 0 };
  }
}

export const FUTURE_FLASH_DISABLED_MESSAGE =
  'AUTHORIZED DIRECT ECU INTEGRATION HAS NOT BEEN IMPLEMENTED' as const;

export const DIRECT_WRITE_LABEL =
  'DIRECT ECU WRITE DISABLED — AUTHORIZED VORTEX INTEGRATION NOT YET VALIDATED' as const;

export function createFutureFlashJob(id: string): FutureFlashJob {
  return { id, status: 'DISABLED', message: FUTURE_FLASH_DISABLED_MESSAGE };
}

/** Phase 4 execution slot. In Phases 1–3 this ALWAYS throws. */
export function executeFlashJob(_job: FutureFlashJob): never {
  throw new Error(FUTURE_FLASH_DISABLED_MESSAGE);
}
