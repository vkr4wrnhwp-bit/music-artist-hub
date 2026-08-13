import { describe, expect, it } from 'vitest';
import {
  buildImportedTrace, createSeededDb, decodeSeries, encodeSeries, fullMerge,
  parseTelemetryCsv, redactDbForGrant, simulateSession,
} from '../src';

function makeCsv(opts: { mph?: boolean; laps?: boolean; rows?: number } = {}): string {
  const rows = opts.rows ?? 1200; // 120 s at 10 Hz source
  const head = ['Time', 'RPM', opts.mph ? 'Speed_MPH' : 'Speed', 'Throttle', ...(opts.laps ? ['Lap'] : [])];
  const lines = [head.join(',')];
  for (let i = 0; i < rows; i++) {
    const t = i / 10;
    const rpm = 6000 + 3000 * Math.sin(t / 3);
    const speedKph = 60 + 30 * Math.sin(t / 5);
    const speed = opts.mph ? speedKph / 1.60934 : speedKph;
    const tps = 40 + 30 * Math.sin(t / 2);
    const lap = 1 + Math.floor(t / 40);
    lines.push([t.toFixed(2), rpm.toFixed(0), speed.toFixed(2), tps.toFixed(1), ...(opts.laps ? [String(lap)] : [])].join(','));
  }
  return lines.join('\n');
}

describe('CSV telemetry import (REAL data path)', () => {
  it('parses flexible headers, resamples to 10 Hz, converts mph', () => {
    const parsed = parseTelemetryCsv(makeCsv({ mph: true }));
    expect(parsed.hz).toBe(10);
    expect(parsed.channelNames.sort()).toEqual(['rpm', 'speed', 'tps']);
    // mph converted back to platform kph
    const speed = parsed.series.speed;
    expect(Math.max(...speed)).toBeGreaterThan(85);
    expect(Math.max(...speed)).toBeLessThan(95);
    expect(parsed.warnings.join(' ')).toContain('one span');
  });

  it('derives laps from an explicit lap column and never guesses otherwise', () => {
    const withLaps = parseTelemetryCsv(makeCsv({ laps: true }));
    expect(withLaps.laps.length).toBeGreaterThanOrEqual(2);
    expect(withLaps.laps[0].timeS).toBeGreaterThan(20);
    const without = parseTelemetryCsv(makeCsv());
    expect(without.laps).toHaveLength(1);
  });

  it('rejects non-monotonic time and unusable files', () => {
    const bad = 't,rpm\n' + Array.from({ length: 60 }, (_, i) => `${i % 30},${5000 + i}`).join('\n');
    expect(() => parseTelemetryCsv(bad)).toThrow(/increasing/);
    expect(() => parseTelemetryCsv('a,b\n1,2\n')).toThrow(/short/);
    const noCore = 't,coolant\n' + Array.from({ length: 60 }, (_, i) => `${i},${70}`).join('\n');
    expect(() => parseTelemetryCsv(noCore)).toThrow(/rpm \/ tps \/ speed/);
  });

  it('encodes and decodes series losslessly enough for charts', () => {
    const series = [[0, 0.1, 0.2, 0.3], [1000, 2000.5, 3000.25, 4000]];
    const decoded = decodeSeries(encodeSeries(series), 2);
    expect(decoded[1][1]).toBeCloseTo(2000.5, 1);
    expect(decoded[0]).toHaveLength(4);
  });

  it('an imported trace replaces the simulator for that session', () => {
    const db = createSeededDb();
    const session = db.sessions[0];
    const parsed = parseTelemetryCsv(makeCsv({ laps: true }));
    db.importedTraces[session.id] = buildImportedTrace(parsed, 'dyno-log.csv', 'u-data', '2026-08-14T10:00:00Z');
    const sim = simulateSession(db, session);
    expect(sim.laps).toEqual(parsed.laps);
    expect(sim.t.length).toBe(parsed.samples);
    // channels the file did not carry stay flat at zero — never invented
    expect(Math.max(...sim.channels.slip)).toBe(0);
    expect(Math.max(...sim.channels.rpm)).toBeGreaterThan(8000);
  });

  it('sync merges imported traces by union and grants redact them by scope', () => {
    const a = createSeededDb();
    const b = createSeededDb();
    const parsed = parseTelemetryCsv(makeCsv());
    const s450 = a.sessions.find((s) => s.bikeId === 'bike-450')!;
    const s250 = a.sessions.find((s) => s.bikeId === 'bike-250')!;
    a.importedTraces[s450.id] = buildImportedTrace(parsed, 'a.csv', 'u-1', '2026-08-14T10:00:00Z');
    b.importedTraces[s250.id] = buildImportedTrace(parsed, 'b.csv', 'u-2', '2026-08-14T11:00:00Z');
    const { merged } = fullMerge(a, b);
    expect(Object.keys(merged.importedTraces).sort()).toEqual([s450.id, s250.id].sort());

    const grant = { ...merged.grants[0], bikeIds: ['bike-450'], readTelemetry: true };
    const redacted = redactDbForGrant(merged, grant);
    expect(redacted.importedTraces[s450.id]).toBeTruthy();
    expect(redacted.importedTraces[s250.id]).toBeUndefined();
    const noTelemetry = redactDbForGrant(merged, { ...grant, readTelemetry: false });
    expect(Object.keys(noTelemetry.importedTraces)).toHaveLength(0);
  });
});
