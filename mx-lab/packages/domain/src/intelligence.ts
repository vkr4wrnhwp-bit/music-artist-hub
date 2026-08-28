import { simulateSession } from './simulator';
import { confidenceFrom } from './compare';
import type { Db } from './types';
import type { KnowledgeCitation, SetupPerformanceRecord, SetupRecommendation } from './expansion';

/**
 * Setup Intelligence — persistent relationships between setup and outcome,
 * computed from session snapshots. Always carries sample size; a single
 * session is surfaced as exactly that, never as established truth.
 */

export interface IntelligenceFilters {
  riderId?: string;
  bikeId?: string;
  trackId?: string;
  surface?: string;
}

export function setupPerformance(db: Db, f: IntelligenceFilters = {}): SetupPerformanceRecord[] {
  const groups = new Map<string, SetupPerformanceRecord>();
  for (const s of db.sessions.filter((x) => x.status === 'complete')) {
    if (f.riderId && s.riderId !== f.riderId) continue;
    if (f.bikeId && s.bikeId !== f.bikeId) continue;
    if (f.trackId && s.trackId !== f.trackId) continue;
    if (f.surface && !s.trackCondition.surfaceType.toLowerCase().includes(f.surface.toLowerCase())) continue;
    const rev = db.mapRevisions.find((r) => r.id === s.setupSnapshot.mapRevisionId);
    const key = `${rev?.rev ?? '?'} · ${s.setupSnapshot.setup.gearing} · ${s.setupSnapshot.setup.tirePressureRear} bar`;
    const sim = simulateSession(db, s);
    const times = sim.laps.map((l) => l.timeS);
    const mean = times.reduce((a, b) => a + b, 0) / Math.max(1, times.length);
    const sigma = Math.sqrt(times.reduce((a, t) => a + (t - mean) ** 2, 0) / Math.max(1, times.length));
    const slipSorted = [...sim.channels.slip].sort((a, b) => a - b);
    const p95 = slipSorted[Math.floor(slipSorted.length * 0.95)] ?? 0;
    const existing = groups.get(key);
    if (existing) {
      existing.sessions.push(s.id);
      existing.bestLap = Math.min(existing.bestLap, Math.min(...times));
      existing.meanLap = +((existing.meanLap + mean) / 2).toFixed(2);
      existing.lapSigma = +((existing.lapSigma + sigma) / 2).toFixed(2);
      existing.peakSlipP95 = +Math.max(existing.peakSlipP95, p95).toFixed(1);
    } else {
      groups.set(key, {
        key, sessions: [s.id], riderId: s.riderId, bikeId: s.bikeId, trackId: s.trackId,
        surface: s.trackCondition.surfaceType,
        gearing: s.setupSnapshot.setup.gearing,
        tirePressureRear: s.setupSnapshot.setup.tirePressureRear,
        mapRev: rev?.rev ?? '?',
        bestLap: +Math.min(...times).toFixed(2),
        meanLap: +mean.toFixed(2),
        lapSigma: +sigma.toFixed(2),
        peakSlipP95: +p95.toFixed(1),
      });
    }
  }
  return [...groups.values()].sort((a, b) => a.meanLap - b.meanLap);
}

/**
 * TRACE Predict — a starting-point recommendation. Requires human
 * confirmation before it becomes anything; DEVELOPMENT until validated.
 */
export function predictSetup(db: Db, f: { bikeId: string; riderId: string; trackId?: string; surface?: string }): SetupRecommendation | null {
  // prefer exact surface+rider matches, fall back to rider-only
  let records = setupPerformance(db, { riderId: f.riderId, bikeId: f.bikeId, surface: f.surface });
  let similarity = 0.9;
  if (!records.length) { records = setupPerformance(db, { riderId: f.riderId, bikeId: f.bikeId }); similarity = 0.6; }
  if (!records.length) { records = setupPerformance(db, { bikeId: f.bikeId }); similarity = 0.4; }
  if (!records.length) return null;

  // rank by mean lap, break ties on consistency
  const best = [...records].sort((a, b) => a.meanLap - b.meanLap || a.lapSigma - b.lapSigma)[0];
  const bike = db.bikes.find((b) => b.id === f.bikeId);
  const n = best.sessions.length;
  const citations: KnowledgeCitation[] = best.sessions.map((id) => {
    const s = db.sessions.find((x) => x.id === id)!;
    return { kind: 'session', id, label: `${new Date(s.startedAt).toLocaleDateString()} · ${s.objective}`, href: `#/session/${id}` };
  });
  return {
    mapRev: best.mapRev,
    gearing: best.gearing,
    tirePressureRear: best.tirePressureRear,
    sagMm: bike?.setup.sagMm ?? 104,
    reason: n > 1
      ? `This combination produced the strongest lap pace and consistency for this rider across ${n} comparable sessions (${best.surface}).`
      : `Best single comparable session (${best.surface}) — one session only, treat as a hint, not established truth.`,
    confidence: confidenceFrom({ sampleSize: n, dataQualityOk: true, conditionSimilarity: similarity, variablesChanged: 0 }),
    comparableSessions: n,
    citations,
    state: 'DEVELOPMENT',
  };
}
