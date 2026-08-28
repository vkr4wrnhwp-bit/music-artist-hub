import { simulateSession } from './simulator';
import type { Db, Rider, Session } from './types';
import type { CoachingInsight, FatigueEstimate, RiderDNA } from './expansion';

/**
 * Rider intelligence — everything here is computed from (simulated) telemetry
 * and labeled DEVELOPMENT: real validation needs real riders and real data.
 * Measured behavior, rider preference, and AI inference are kept separate.
 */

export function computeRiderDNA(db: Db, rider: Rider): RiderDNA {
  const sessions = db.sessions.filter((s) => s.riderId === rider.id && s.status === 'complete');
  let rpmLo = Infinity; let rpmHi = 0; let dtps: number[] = []; let clutchOn = 0; let total = 0;
  let minCorner: number[] = []; let sigmas: number[] = [];
  for (const s of sessions) {
    const sim = simulateSession(db, s);
    const rpmSorted = [...sim.channels.rpm].sort((a, b) => a - b);
    rpmLo = Math.min(rpmLo, rpmSorted[Math.floor(rpmSorted.length * 0.2)] ?? rpmLo);
    rpmHi = Math.max(rpmHi, rpmSorted[Math.floor(rpmSorted.length * 0.9)] ?? rpmHi);
    for (let i = 1; i < sim.channels.tps.length; i++) {
      dtps.push(Math.abs(sim.channels.tps[i] - sim.channels.tps[i - 1]));
      if (sim.channels.clutch[i] > 20) clutchOn++;
      total++;
    }
    for (const lap of sim.laps) {
      const i0 = Math.floor(lap.startS * sim.hz);
      const i1 = Math.floor(lap.endS * sim.hz);
      minCorner.push(Math.min(...sim.channels.speed.slice(i0, Math.max(i0 + 1, i1))));
    }
    const times = sim.laps.map((l) => l.timeS);
    const mean = times.reduce((a, b) => a + b, 0) / Math.max(1, times.length);
    sigmas.push(Math.sqrt(times.reduce((a, t) => a + (t - mean) ** 2, 0) / Math.max(1, times.length)));
  }
  const pref = db.riderPrefs.find((p) => p.riderId === rider.id);
  const sens = sigmas.length && sigmas.reduce((a, b) => a + b, 0) / sigmas.length < 1.2 ? 'low' : 'moderate';
  return {
    riderId: rider.id,
    measured: {
      typicalRpmBand: [Math.round(rpmLo === Infinity ? 0 : rpmLo), Math.round(rpmHi)],
      throttleAggressiveness: +((dtps.reduce((a, b) => a + b, 0) / Math.max(1, dtps.length)) / 10).toFixed(2),
      clutchUsePctOfLap: +((clutchOn / Math.max(1, total)) * 100).toFixed(1),
      avgMinCornerSpeed: +(minCorner.reduce((a, b) => a + b, 0) / Math.max(1, minCorner.length)).toFixed(1),
      lapConsistency: +(sigmas.reduce((a, b) => a + b, 0) / Math.max(1, sigmas.length)).toFixed(2),
      sessions: sessions.length,
    },
    preferences: {
      delivery: rider.preferredDelivery,
      engineBraking: pref?.preferredEngineBraking ?? 'unknown',
      initialHit: pref?.preferredInitialHit ?? 'unknown',
    },
    inferred: {
      setupSensitivity: sens,
      trackTypeStrength: sessions.some((s) => db.tracks.find((t) => t.id === s.trackId)?.kind === 'supercross_test')
        ? 'Comparable across MX and SX layouts (small sample)' : 'MX layouts only so far',
      basis: `Inferred from ${sessions.length} simulated session${sessions.length === 1 ? '' : 's'} — AI INFERENCE, not measurement.`,
    },
    state: 'DEVELOPMENT',
  };
}

/** Coaching insights vs the rider's fastest lap of the session. */
export function coachingInsights(db: Db, session: Session): CoachingInsight[] {
  const sim = simulateSession(db, session);
  if (sim.laps.length < 3) return [];
  const best = sim.laps.reduce((a, b) => (a.timeS < b.timeS ? a : b));
  const out: CoachingInsight[] = [];
  const lapStat = (lap: typeof best, ch: string) => {
    const i0 = Math.floor(lap.startS * sim.hz);
    const i1 = Math.floor(lap.endS * sim.hz);
    const arr = sim.channels[ch].slice(i0, Math.max(i0 + 1, i1));
    return arr.reduce((a, b) => a + b, 0) / Math.max(1, arr.length);
  };
  const others = sim.laps.filter((l) => l.n !== best.n);
  const meanTps = others.reduce((a, l) => a + lapStat(l, 'tps'), 0) / others.length;
  const bestTps = lapStat(best, 'tps');
  if (bestTps - meanTps > 1) {
    out.push({
      sessionId: session.id, riderId: session.riderId,
      text: `Throttle commitment on the fastest lap averaged ${(bestTps - meanTps).toFixed(1)}% higher than the session mean — the pace is there when the exit is trusted.`,
      evidence: `Lap ${best.n} mean TPS ${bestTps.toFixed(1)}% vs ${meanTps.toFixed(1)}% session mean`,
      shareableWithRider: true, provenance: 'CALCULATED', state: 'DEVELOPMENT',
    });
  }
  const meanClutch = others.reduce((a, l) => a + lapStat(l, 'clutch'), 0) / others.length;
  const bestClutch = lapStat(best, 'clutch');
  if (meanClutch - bestClutch > 0.5) {
    out.push({
      sessionId: session.id, riderId: session.riderId,
      text: 'Clutch use was lower on the fastest lap — extra clutch work on other laps is masking drive rather than creating it.',
      evidence: `Lap ${best.n} clutch ${bestClutch.toFixed(1)}% vs ${meanClutch.toFixed(1)}% mean`,
      shareableWithRider: true, provenance: 'CALCULATED', state: 'DEVELOPMENT',
    });
  }
  const half = Math.floor(sim.laps.length / 2);
  const early = sim.laps.slice(0, half).reduce((a, l) => a + l.timeS, 0) / half;
  const late = sim.laps.slice(half).reduce((a, l) => a + l.timeS, 0) / (sim.laps.length - half);
  if (late - early > 0.8) {
    out.push({
      sessionId: session.id, riderId: session.riderId,
      text: `Laps slowed ${(late - early).toFixed(1)}s on average in the second half — worth pairing with the fatigue estimate before drawing setup conclusions.`,
      evidence: `First-half mean ${early.toFixed(2)}s vs second-half ${late.toFixed(2)}s`,
      shareableWithRider: true, provenance: 'CALCULATED', state: 'DEVELOPMENT',
    });
  }
  return out;
}

/** Fatigue pattern estimate — explicitly a development estimate. */
export function fatigueEstimate(db: Db, session: Session): FatigueEstimate {
  const sim = simulateSession(db, session);
  const evidence: string[] = [];
  let onsetLap: number | undefined;
  if (sim.laps.length >= 5) {
    const times = sim.laps.map((l) => l.timeS);
    const mean3 = (i: number) => (times[i] + times[i - 1] + times[i - 2]) / 3;
    for (let i = 3; i < times.length; i++) {
      if (times[i] > mean3(i - 1) + 1.2) { onsetLap = sim.laps[i].n; break; }
    }
    const half = Math.floor(sim.laps.length / 2);
    const sd = (xs: number[]) => {
      const m = xs.reduce((a, b) => a + b, 0) / xs.length;
      return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / xs.length);
    };
    const early = sd(times.slice(0, half));
    const late = sd(times.slice(half));
    if (late > early * 1.3) evidence.push(`Lap variance increased ${Math.round(((late / Math.max(0.01, early)) - 1) * 100)}% in the second half.`);
    // clutch trend
    const mid = Math.floor(sim.channels.clutch.length / 2);
    const cEarly = sim.channels.clutch.slice(0, mid).reduce((a, b) => a + b, 0) / mid;
    const cLate = sim.channels.clutch.slice(mid).reduce((a, b) => a + b, 0) / (sim.channels.clutch.length - mid);
    if (cLate > cEarly * 1.15) evidence.push(`Clutch use increased ${Math.round(((cLate / Math.max(0.01, cEarly)) - 1) * 100)}% late in the session.`);
  }
  return {
    sessionId: session.id,
    detected: evidence.length > 0,
    onsetLap,
    evidence: evidence.length ? evidence : ['No consistent fatigue signature in this session.'],
    disclaimer: 'DEVELOPMENT ESTIMATE — NOT MEDICAL OR SAFETY DIAGNOSIS',
    state: 'DEVELOPMENT',
  };
}
