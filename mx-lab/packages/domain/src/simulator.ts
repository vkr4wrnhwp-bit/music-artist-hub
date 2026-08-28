import type { Db, EventMarker, Lap, Session, Track } from './types';
import { importedTraceToSimData } from './telemetryImport';

/**
 * Deterministic telemetry simulator.
 *
 * Phase 1 stores NO fake "measured" samples. A session stores only its seed
 * and metadata; every chart regenerates the identical trace from the seed.
 * All simulated channels are labeled SIMULATION at the provenance layer, and
 * the app banners every screen with SIMULATED DEMONSTRATION DATA.
 *
 * Real hardware (Phase 2+) replaces this module behind the same interface:
 * chunked binary session files in object storage, downsampled for charts.
 */

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface SimData {
  hz: number;
  t: number[];                       // seconds
  channels: Record<string, number[]>;
  laps: Lap[];
}

export const SIM_HZ = 10;

/** smooth pseudo-random speed profile around the track, deterministic per track */
function speedProfile(track: Track, frac: number): number {
  let h = 0;
  for (const ch of track.id) h = (h * 31 + ch.charCodeAt(0)) & 0xffff;
  const p1 = (h % 7) + 3;          // corner count-ish harmonics
  const p2 = (h % 5) + 2;
  const s =
    0.55 +
    0.28 * Math.sin(2 * Math.PI * p1 * frac + h) +
    0.17 * Math.sin(2 * Math.PI * p2 * frac + h * 0.5);
  return Math.min(1, Math.max(0.18, s));
}

const cache = new Map<string, SimData>();

export function simulateSession(db: Db, session: Session): SimData {
  // measured data wins: an imported trace replaces the simulator entirely
  const imported = db.importedTraces?.[session.id];
  if (imported) {
    const key = `imported|${session.id}|${imported.importedAt}`;
    const cached = cache.get(key);
    if (cached) return cached;
    const data = importedTraceToSimData(imported, session);
    cache.set(key, data);
    return data;
  }

  const markers = db.markers.filter((m) => m.sessionId === session.id);
  // the marker set is part of the cache key: a marker exists because something
  // happened on track, so the regenerated trace must contain its anomaly
  const cacheKey = `${session.id}|${markers.map((m) => `${m.id}@${m.trackFrac}`).join(',')}`;
  const hit = cache.get(cacheKey);
  if (hit) return hit;

  const track = db.tracks.find((t) => t.id === session.trackId)!;
  const rnd = mulberry32(session.simSeed);
  const build = db.engineBuilds.find((b) => b.id === session.setupSnapshot.engineBuildId);
  const revLimit = build?.revLimit ?? 13500;
  const is450 = db.bikeModels.find(
    (m) => m.id === db.bikes.find((b) => b.id === session.bikeId)?.bikeModelId,
  )?.model.includes('450');

  const n = Math.floor(session.durationS * SIM_HZ);
  const t: number[] = new Array(n);
  const mk = () => new Array<number>(n).fill(0);
  const ch: Record<string, number[]> = {
    rpm: mk(), tps: mk(), speed: mk(), accel: mk(), coolant: mk(), iat: mk(),
    battv: mk(), slip: mk(), clutch: mk(), fork: mk(), shock: mk(),
    gear: mk(), frac: mk(),
  };

  const baseLap = (is450 ? 96 : 99) + rnd() * 4;
  const laps: Lap[] = [];
  let lapStart = 8 + rnd() * 4; // out-lap offset
  let lapN = 1;
  const lapAt = (sec: number) => laps.find((l) => sec >= l.startS && sec < l.endS);
  while (lapStart < session.durationS - 20) {
    const lt = baseLap + (rnd() - 0.5) * 3.5;
    laps.push({ n: lapN++, startS: lapStart, endS: lapStart + lt, timeS: +lt.toFixed(2) });
    lapStart += lt;
  }

  // event-injection plan: each marker's anomaly recurs on ~70% of laps at the
  // same track position, with varying magnitude — the AI must *find* this
  const injections: Array<{ frac: number; lapNs: number[]; mag: number[] }> = markers.map((m, i) => {
    const r = mulberry32(session.simSeed + 1000 + i);
    const lapNs: number[] = [];
    const mag: number[] = [];
    for (const l of laps) {
      if (r() < 0.72) { lapNs.push(l.n); mag.push(0.6 + r() * 0.8); }
    }
    return { frac: m.trackFrac, lapNs, mag };
  });

  const topSpeed = is450 ? 112 : 104; // kph
  let speed = 10;
  let coolant = 62;
  for (let i = 0; i < n; i++) {
    const sec = i / SIM_HZ;
    t[i] = +sec.toFixed(2);
    const lap = lapAt(sec);
    const frac = lap ? (sec - lap.startS) / (lap.endS - lap.startS) : (sec % baseLap) / baseLap;
    ch.frac[i] = frac;

    const target = speedProfile(track, frac) * topSpeed;
    const ahead = speedProfile(track, (frac + 0.02) % 1) * topSpeed;
    let tps = Math.min(100, Math.max(0, 38 + (ahead - speed) * 6 + (rnd() - 0.5) * 6));
    if (!lap) tps = Math.min(tps, 35); // out-lap / cool-down

    // injected anomaly window: abrupt torque transition after throttle reopening
    let slipExtra = 0;
    let accelDip = 0;
    let rpmFlare = 0;
    for (let k = 0; k < injections.length; k++) {
      const inj = injections[k];
      if (!lap || !inj.lapNs.includes(lap.n)) continue;
      const d = frac - inj.frac;
      if (d > 0 && d < 0.018) {
        const idx = inj.lapNs.indexOf(lap.n);
        const m = inj.mag[idx];
        const w = Math.sin((d / 0.018) * Math.PI); // rise & fall
        slipExtra = 24 * m * w;
        accelDip = 0.45 * m * w;
        rpmFlare = 900 * m * w;
        tps = Math.max(tps, 55 + 25 * w);
      } else if (d > -0.012 && d <= 0) {
        tps = Math.min(tps, 12); // closed throttle entering the corner
      }
    }

    speed += ((tps / 100) * (target + 14) - speed) * 0.09 + (rnd() - 0.5) * 0.4;
    speed = Math.max(4, Math.min(topSpeed + 4, speed));
    const gear = speed < 25 ? 1 : speed < 42 ? 2 : speed < 60 ? 3 : speed < 82 ? 4 : 5;
    const bandLo = [0, 25, 42, 60, 82][gear - 1];
    const bandHi = [25, 42, 60, 82, 112][gear - 1];
    const inBand = (speed - bandLo) / (bandHi - bandLo);
    let rpm = 4200 + inBand * (revLimit - 5200) + tps * 8 + rpmFlare + (rnd() - 0.5) * 150;
    rpm = Math.min(revLimit, Math.max(1800, rpm));

    coolant += (76 + tps * 0.05 - coolant) * 0.002 + (rnd() - 0.5) * 0.05;

    ch.tps[i] = +tps.toFixed(1);
    ch.speed[i] = +speed.toFixed(1);
    ch.rpm[i] = Math.round(rpm);
    ch.gear[i] = gear;
    ch.accel[i] = +(((tps / 100) * 0.9 - 0.35) - accelDip + (rnd() - 0.5) * 0.08).toFixed(3);
    ch.slip[i] = +(Math.max(0, slipExtra + (tps > 70 ? 4 : 1) * rnd())).toFixed(1);
    ch.coolant[i] = +coolant.toFixed(1);
    ch.iat[i] = +(session.weather.ambientC + 7 + (rnd() - 0.5)).toFixed(1);
    ch.battv[i] = +(13.9 + (rnd() - 0.5) * 0.15).toFixed(2);
    ch.clutch[i] = +(tps < 15 && speed < 30 ? 40 + rnd() * 50 : rnd() * 4).toFixed(1);
    ch.fork[i] = +(35 + 30 * Math.abs(Math.sin(frac * 40)) + rnd() * 12).toFixed(1);
    ch.shock[i] = +(30 + 28 * Math.abs(Math.cos(frac * 34)) + rnd() * 12).toFixed(1);
  }

  const data: SimData = { hz: SIM_HZ, t, channels: ch, laps };
  cache.set(cacheKey, data);
  return data;
}

/** position on the normalized track path for a given track fraction */
export function pathPoint(track: Track, frac: number): [number, number] {
  const pts = track.path;
  const f = ((frac % 1) + 1) % 1;
  const seg = f * (pts.length - 1);
  const i = Math.floor(seg);
  const u = seg - i;
  const a = pts[i];
  const b = pts[Math.min(i + 1, pts.length - 1)];
  return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u];
}

/** window statistics used by the AI engineer — computed, never asserted */
export interface WindowStats {
  lapsAnalyzed: number;
  lapsWithEvent: number;
  meanDelayAfterReopenS: number;
  peakSlipPct: number;
  meanAccelDipG: number;
  rpmFlare: number;
  coolantC: number;
}

export function analyzeMarkerWindow(db: Db, session: Session, marker: EventMarker): WindowStats {
  const sim = simulateSession(db, session);
  const { channels: ch } = sim;
  let lapsWithEvent = 0;
  let peakSlip = 0;
  let accelDips: number[] = [];
  let flare = 0;
  let delays: number[] = [];
  for (const lap of sim.laps) {
    // examine the window around the marker's track position on every lap
    const i0 = Math.floor((lap.startS + marker.trackFrac * (lap.endS - lap.startS)) * SIM_HZ);
    const i1 = Math.min(i0 + 3 * SIM_HZ, sim.t.length - 1);
    let slipMax = 0, dipMin = 0, rpmMax = 0, reopenIdx = -1, slipIdx = -1;
    for (let i = Math.max(0, i0 - 2 * SIM_HZ); i < i1; i++) {
      if (reopenIdx < 0 && i > 0 && ch.tps[i - 1] < 20 && ch.tps[i] >= 20) reopenIdx = i;
      if (ch.slip[i] > slipMax) { slipMax = ch.slip[i]; slipIdx = i; }
      dipMin = Math.min(dipMin, ch.accel[i]);
      rpmMax = Math.max(rpmMax, ch.rpm[i]);
    }
    if (slipMax > 12) {
      lapsWithEvent++;
      peakSlip = Math.max(peakSlip, slipMax);
      accelDips.push(dipMin);
      flare = Math.max(flare, rpmMax);
      if (reopenIdx >= 0 && slipIdx > reopenIdx) delays.push((slipIdx - reopenIdx) / SIM_HZ);
    }
  }
  const iMark = Math.min(Math.floor(marker.tS * SIM_HZ), sim.t.length - 1);
  return {
    lapsAnalyzed: sim.laps.length,
    lapsWithEvent,
    meanDelayAfterReopenS: delays.length ? +(delays.reduce((a, b) => a + b, 0) / delays.length).toFixed(2) : 0,
    peakSlipPct: +peakSlip.toFixed(1),
    meanAccelDipG: accelDips.length ? +(accelDips.reduce((a, b) => a + b, 0) / accelDips.length).toFixed(2) : 0,
    rpmFlare: Math.round(flare),
    coolantC: ch.coolant[iMark],
  };
}
