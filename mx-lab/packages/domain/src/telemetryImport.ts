import type { Db, Lap, Session } from './types';
import { SIM_HZ, type SimData } from './simulator';

/**
 * REAL telemetry import — the first measured-data path in the platform.
 *
 * Teams export CSV from any logger; this module parses it, resamples to the
 * platform rate, and stores it compactly on the session. Every analysis
 * surface (compare, insights, start lab, archive upload) then runs on the
 * measured trace instead of the simulator, labeled IMPORTED. Honesty rules:
 * nothing is invented — channels the file doesn't carry stay flat at zero
 * and are listed as absent; laps come from a lap column or are left as one
 * span, never guessed.
 */

export interface ImportedTrace {
  hz: number;
  samples: number;
  /** channels actually present in the source file, in stored order */
  channelNames: string[];
  /** base64 of Float32Array: [t..., ch0..., ch1..., ...] */
  base64: string;
  laps: Lap[];
  sourceName: string;
  importedAt: string;
  byUserId: string;
}

// ---------------------------------------------------------------- base64
// Portable (browser + node), dependency-free.

const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

export function bytesToBase64(bytes: Uint8Array): string {
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i];
    const b = i + 1 < bytes.length ? bytes[i + 1] : 0;
    const c = i + 2 < bytes.length ? bytes[i + 2] : 0;
    out += B64[a >> 2] + B64[((a & 3) << 4) | (b >> 4)]
      + (i + 1 < bytes.length ? B64[((b & 15) << 2) | (c >> 6)] : '=')
      + (i + 2 < bytes.length ? B64[c & 63] : '=');
  }
  return out;
}

export function base64ToBytes(s: string): Uint8Array {
  const clean = s.replace(/=+$/, '');
  const idx = (ch: string) => B64.indexOf(ch);
  const out = new Uint8Array(Math.floor((clean.length * 3) / 4));
  let o = 0;
  for (let i = 0; i < clean.length; i += 4) {
    const n = (idx(clean[i]) << 18) | (idx(clean[i + 1]) << 12)
      | ((i + 2 < clean.length ? idx(clean[i + 2]) : 0) << 6)
      | (i + 3 < clean.length ? idx(clean[i + 3]) : 0);
    out[o++] = (n >> 16) & 255;
    if (i + 2 < clean.length) out[o++] = (n >> 8) & 255;
    if (i + 3 < clean.length) out[o++] = n & 255;
  }
  return out;
}

export function encodeSeries(series: number[][]): string {
  const flat = new Float32Array(series.reduce((n, s) => n + s.length, 0));
  let o = 0;
  for (const s of series) { flat.set(s, o); o += s.length; }
  return bytesToBase64(new Uint8Array(flat.buffer));
}

export function decodeSeries(base64: string, count: number): number[][] {
  const bytes = base64ToBytes(base64);
  const flat = new Float32Array(bytes.buffer, 0, Math.floor(bytes.length / 4));
  const per = Math.floor(flat.length / count);
  const out: number[][] = [];
  for (let i = 0; i < count; i++) out.push(Array.from(flat.subarray(i * per, (i + 1) * per)));
  return out;
}

// ---------------------------------------------------------------- CSV parse

/** header aliases → canonical channel names (platform units: kph, °C, %) */
const HEADER_MAP: Array<[RegExp, string, ((v: number) => number)?]> = [
  [/^(t|time|time_s|sec|seconds|timestamp)$/, 't'],
  [/^(rpm|engine_?rpm|engine_?speed)$/, 'rpm'],
  [/^(tps|throttle|throttle_?pct|throttle_?pos(ition)?)$/, 'tps'],
  [/^(speed|speed_?kph|kph|vehicle_?speed)$/, 'speed'],
  [/^(speed_?mph|mph)$/, 'speed', (v) => v * 1.60934],
  [/^(gear)$/, 'gear'],
  [/^(coolant|coolant_?c|ect|water_?temp)$/, 'coolant'],
  [/^(iat|intake_?air_?temp|air_?temp)$/, 'iat'],
  [/^(battv|batt|battery|voltage|vbat)$/, 'battv'],
  [/^(clutch|clutch_?pct)$/, 'clutch'],
  [/^(slip|wheel_?slip|slip_?pct)$/, 'slip'],
  [/^(accel|accel_?g|longitudinal_?g)$/, 'accel'],
  [/^(fork|fork_?travel)$/, 'fork'],
  [/^(shock|shock_?travel)$/, 'shock'],
  [/^(lap|lap_?n|lap_?number)$/, 'lap'],
];

export interface CsvParseResult {
  hz: number;
  samples: number;
  durationS: number;
  channelNames: string[];   // canonical, excluding t and lap
  series: Record<string, number[]>; // resampled at SIM_HZ, includes t
  laps: Lap[];
  absent: string[];         // core channels the file did not carry
  warnings: string[];
}

const CORE = ['rpm', 'tps', 'speed'];

export function parseTelemetryCsv(text: string): CsvParseResult {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  if (lines.length < 50) throw new Error('CSV too short — need at least 50 data rows.');
  const delim = lines[0].includes(';') ? ';' : lines[0].includes('\t') ? '\t' : ',';
  const rawHeads = lines[0].split(delim).map((h) => h.trim().toLowerCase().replace(/["']/g, ''));

  const columns: Array<{ name: string; convert?: (v: number) => number } | null> = rawHeads.map((h) => {
    for (const [re, name, convert] of HEADER_MAP) if (re.test(h)) return { name, convert };
    return null;
  });
  if (!columns.some((c) => c?.name === 't')) {
    throw new Error('No time column found (accepted: t, time, sec, seconds, timestamp).');
  }
  const present = columns.filter((c): c is NonNullable<typeof c> => !!c).map((c) => c.name);
  if (!CORE.some((c) => present.includes(c))) {
    throw new Error('None of rpm / tps / speed found — nothing to analyze.');
  }

  // collect raw rows
  const raw: Record<string, number[]> = {};
  for (const c of present) raw[c] = [];
  const warnings: string[] = [];
  let dropped = 0;
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split(delim);
    if (cells.length < columns.length) { dropped++; continue; }
    let bad = false;
    const rowVals: Array<[string, number]> = [];
    for (let cIdx = 0; cIdx < columns.length; cIdx++) {
      const col = columns[cIdx];
      if (!col) continue;
      const v = parseFloat(cells[cIdx]);
      if (Number.isNaN(v)) { bad = true; break; }
      rowVals.push([col.name, col.convert ? col.convert(v) : v]);
    }
    if (bad) { dropped++; continue; }
    for (const [name, v] of rowVals) raw[name].push(v);
  }
  if (dropped) warnings.push(`${dropped} malformed row${dropped > 1 ? 's' : ''} skipped.`);
  const t0 = raw.t;
  if (t0.length < 50) throw new Error('Fewer than 50 valid data rows after parsing.');
  for (let i = 1; i < t0.length; i++) {
    if (t0[i] <= t0[i - 1]) throw new Error(`Time column is not strictly increasing (row ${i + 1}).`);
  }

  // normalize time to start at 0; resample everything to the platform rate
  const start = t0[0];
  const tNorm = t0.map((v) => v - start);
  const durationS = tNorm[tNorm.length - 1];
  if (durationS < 30) throw new Error('Trace shorter than 30 seconds.');
  if (durationS > 3 * 3600) throw new Error('Trace longer than 3 hours — split the file.');

  const n = Math.floor(durationS * SIM_HZ) + 1;
  const resample = (src: number[], step = false): number[] => {
    const out = new Array<number>(n);
    let j = 0;
    for (let i = 0; i < n; i++) {
      const tt = i / SIM_HZ;
      while (j < tNorm.length - 2 && tNorm[j + 1] <= tt) j++;
      const u = (tt - tNorm[j]) / Math.max(1e-9, tNorm[j + 1] - tNorm[j]);
      out[i] = step
        ? src[u < 1 ? j : j + 1]
        : src[j] + (src[Math.min(j + 1, src.length - 1)] - src[j]) * Math.min(1, Math.max(0, u));
    }
    return out;
  };

  const series: Record<string, number[]> = { t: Array.from({ length: n }, (_, i) => +(i / SIM_HZ).toFixed(2)) };
  const channelNames: string[] = [];
  for (const c of present) {
    if (c === 't' || c === 'lap') continue;
    series[c] = resample(raw[c], c === 'gear');
    channelNames.push(c);
  }

  // laps: only from an explicit lap column — never guessed
  const laps: Lap[] = [];
  if (present.includes('lap')) {
    const lapRes = resample(raw.lap, true).map(Math.round);
    let cur = lapRes[0];
    let startIdx = 0;
    for (let i = 1; i <= lapRes.length; i++) {
      if (i === lapRes.length || lapRes[i] !== cur) {
        const s = startIdx / SIM_HZ;
        const e = i / SIM_HZ;
        if (cur > 0 && e - s > 20) laps.push({ n: cur, startS: s, endS: e, timeS: +(e - s).toFixed(2) });
        cur = lapRes[i];
        startIdx = i;
      }
    }
  }
  if (!laps.length) {
    laps.push({ n: 1, startS: 0, endS: durationS, timeS: +durationS.toFixed(2) });
    warnings.push('No lap column — the whole trace is treated as one span; per-lap analysis will be thin.');
  }

  const absent = CORE.filter((c) => !channelNames.includes(c));
  if (absent.length) warnings.push(`Missing channels stay flat at zero: ${absent.join(', ')}.`);

  return { hz: SIM_HZ, samples: n, durationS, channelNames, series, laps, absent, warnings };
}

// ------------------------------------------------------- session integration

export function buildImportedTrace(
  parsed: CsvParseResult, sourceName: string, byUserId: string, importedAt: string,
): ImportedTrace {
  const order = ['t', ...parsed.channelNames];
  return {
    hz: parsed.hz,
    samples: parsed.samples,
    channelNames: parsed.channelNames,
    base64: encodeSeries(order.map((c) => parsed.series[c])),
    laps: parsed.laps,
    sourceName,
    importedAt,
    byUserId,
  };
}

/** every channel the simulator produces — imported data zero-fills the rest */
const ALL_CHANNELS = [
  'rpm', 'tps', 'speed', 'accel', 'coolant', 'iat', 'battv', 'slip', 'clutch',
  'fork', 'shock', 'gear', 'frac',
];

export function importedTraceToSimData(trace: ImportedTrace, session: Session): SimData {
  const order = ['t', ...trace.channelNames];
  const series = decodeSeries(trace.base64, order.length);
  const byName: Record<string, number[]> = {};
  order.forEach((name, i) => { byName[name] = series[i]; });
  const n = byName.t.length;
  const channels: Record<string, number[]> = {};
  for (const c of ALL_CHANNELS) channels[c] = byName[c] ?? new Array<number>(n).fill(0);
  // frac: position within the current lap (or the whole span)
  if (!byName.frac) {
    channels.frac = byName.t.map((tt) => {
      const lap = trace.laps.find((l) => tt >= l.startS && tt < l.endS) ?? trace.laps[trace.laps.length - 1];
      return Math.min(1, Math.max(0, (tt - lap.startS) / Math.max(1e-9, lap.endS - lap.startS)));
    });
  }
  void session;
  return { hz: trace.hz, t: byName.t, channels, laps: trace.laps };
}
