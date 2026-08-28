import { analyzeMarkerWindow, simulateSession } from './simulator';
import { appendAudit } from './audit';
import { assertCan } from './permissions';
import type {
  AIRecommendation, CauseCategory, DataQualityFlag, Db, EventMarker,
  RankedCause, RecommendationStatus, Session, User,
} from './types';

/**
 * AI Race Engineer — a structured, rule-based analysis pipeline
 * (section 13.4), not a chat box and not a controller.
 *
 * Hard guarantees, enforced here and by tests:
 *  - it never mutates a map revision or its workflow state
 *  - it never satisfies a readiness gate
 *  - degraded data quality caps confidence and is surfaced, never hidden
 *  - every recommendation is created AWAITING_TUNER_REVIEW; only a human
 *    with the right role can move it
 *  - proposed tests are bounded by the tuner-defined validated envelope;
 *    if none exists, the recommendation says so instead of inventing one
 */

let recCounter = 0;

export function buildRecommendation(
  db: Db,
  session: Session,
  marker: EventMarker,
  riderStatement: string,
): AIRecommendation {
  // ---- 1. data-quality check --------------------------------------------
  // An imported trace is measured data: quality comes from what the log file
  // actually carried, not from the simulated device's channel health.
  const imported = db.importedTraces?.[session.id];
  const device = db.devices.find((d) => d.id === session.hardwareCheck.deviceId);
  const dataQuality: DataQualityFlag[] = [];
  if (imported) {
    for (const chId of ['rpm', 'tps', 'speed', 'slip', 'accel']) {
      if (!imported.channelNames.includes(chId)) {
        dataQuality.push({
          channelId: chId, quality: 'Missing',
          note: `${chId} is not in the imported log — correlation on this channel is impossible, not merely weak.`,
        });
      }
    }
  } else {
    if (device) {
      for (const [chId, q] of Object.entries(device.channelHealth)) {
        if (q === 'Missing' || q === 'Intermittent' || q === 'Out of range' || q === 'Uncalibrated' || q === 'Low confidence') {
          dataQuality.push({ channelId: chId, quality: q, note: `${chId} reported ${q} during this session.` });
        }
      }
    }
    if (session.simulated) {
      dataQuality.push({ channelId: '*', quality: 'Simulated', note: 'All channels are simulated demonstration data.' });
    }
  }
  const degraded = dataQuality.some((f) => f.quality !== 'Simulated');
  const blocked = imported
    ? !['rpm', 'tps'].some((c) => imported.channelNames.includes(c))
    : session.hardwareCheck.ecuData === 'Missing';
  const dataQualityStatus = blocked ? 'BLOCKED' : degraded ? 'DEGRADED' : 'OK';

  // ---- 2. telemetry correlation ----------------------------------------
  const stats = analyzeMarkerWindow(db, session, marker);
  const seg = db.tracks.find((t) => t.id === session.trackId)
    ?.segments.find((s) => marker.trackFrac >= s.startFrac && marker.trackFrac < s.endFrac);
  const where = seg ? seg.name : `track position ${(marker.trackFrac * 100).toFixed(0)}%`;

  const measuredEvidence = blocked
    ? ['ECU data stream unavailable — no telemetry correlation possible for this event.']
    : [
        `Pattern detected on ${stats.lapsWithEvent} of ${stats.lapsAnalyzed} comparable laps at ${where}.`,
        stats.meanDelayAfterReopenS > 0
          ? `Event begins ≈${stats.meanDelayAfterReopenS.toFixed(1)} s after throttle reopening.`
          : 'No consistent throttle-reopening relationship found.',
        `Peak rear-wheel slip estimate ${stats.peakSlipPct}% in the event window.`,
        `Mean forward-acceleration dip ${stats.meanAccelDipG} g during the event.`,
        `Peak RPM in window ${stats.rpmFlare} rpm; coolant ${stats.coolantC.toFixed(0)} °C at the marker.`,
      ];

  // ---- 3. cause ranking --------------------------------------------------
  const causes = rankCauses(marker, stats, dataQuality.length > 0);
  const [likelyCause, ...alternativeCauses] = causes;

  // ---- 4. non-map checks & proposed test --------------------------------
  const nonMapChecks = nonMapChecksFor(causes.map((c) => c.category));

  const rev = db.mapRevisions.find((r) => r.id === session.setupSnapshot.mapRevisionId);
  const envelope = rev
    ? db.envelopes.find((e) => e.ecuDefinitionId === rev.compatibility.ecuDefinitionId)
    : undefined;

  const mapCause = likelyCause.category === 'Fueling' || likelyCause.category === 'Torque transition'
    || likelyCause.category === 'Ignition' || likelyCause.category === 'Engine braking';

  const affectedRegion = mapCause && !blocked
    ? {
        tableId: likelyCause.category === 'Ignition' ? 'ignition' : 'fuel',
        xRange: [2, 4] as [number, number],   // partial-throttle columns (20–60 %)
        yRange: [3, 6] as [number, number],   // mid-rpm rows
        description: 'Partial-to-heavy throttle reopening region in the mid-rpm range.',
      }
    : undefined;

  const proposedTest = blocked
    ? 'Restore ECU data quality before testing — no controlled test can be evaluated without telemetry.'
    : mapCause
      ? envelope
        ? `Create a Revision B with a small, tuner-defined change (within the validated envelope, max ±${envelope.maxStepDelta[affectedRegion?.tableId ?? 'fuel'] ?? '—'} per cell) in the affected region only. Hold gearing, tire, suspension, and clutch setup unchanged. Run an A/B back-to-back on the same track section.`
        : 'No validated tuning envelope exists for this ECU definition. A tuner must define one before any map A/B test can be proposed.'
      : `Test the leading non-map cause first (${likelyCause.category.toLowerCase()}). Change one variable only and repeat the same section.`;

  const expectedObservable = mapCause
    ? 'Reduced rear-slip spike and smaller acceleration dip in the same section, with rider-reported smoother reopening; lap-time variance unchanged or improved.'
    : 'Reduced event frequency at the same section without any map change.';

  // ---- 5. confidence — computed, capped, never certain -------------------
  let confidence = blocked ? 10
    : Math.round((stats.lapsWithEvent / Math.max(1, stats.lapsAnalyzed)) * 90 * likelyCause.weight + 20);
  if (degraded) confidence = Math.min(confidence, 55);
  confidence = Math.max(5, Math.min(90, confidence));

  const riskFlags = [
    'Any fuel change toward lean raises thermal load — tuner must review direction and magnitude.',
    'Recommendation is based on simulated demonstration data — NOT A VALID TUNE.',
    ...(envelope ? [] : ['No validated envelope on file for this ECU definition.']),
  ];

  const missingData = [
    ...dataQuality.filter((f) => f.quality !== 'Simulated').map((f) => `${f.channelId}: ${f.quality}`),
    ...(db.telemetryChannels.some((c) => c.id === 'wheelSpeedFront' && c.quality !== 'Missing')
      ? [] : ['Front wheel speed not fitted (test-only sensor) — slip is estimated, not measured.']),
  ];

  const rec: AIRecommendation = {
    id: `rec-${Date.now()}-${recCounter++}`,
    orgId: db.org.id,
    sessionId: session.id,
    markerId: marker.id,
    riderStatement,
    observedEvent: `${marker.category} at ${where}, lap ${marker.lap}.`,
    measuredEvidence,
    dataQuality,
    dataQualityStatus,
    likelyCause,
    alternativeCauses,
    nonMapChecks,
    affectedRegion,
    proposedTest,
    expectedObservable,
    riskFlags,
    missingData,
    confidencePct: confidence,
    status: 'AWAITING_TUNER_REVIEW',
    createdAt: new Date().toISOString(),
    provenance: 'AI INFERENCE',
  };
  return rec;
}

function rankCauses(marker: EventMarker, stats: ReturnType<typeof analyzeMarkerWindow>, sensorIssues: boolean): RankedCause[] {
  const causes: RankedCause[] = [];
  const push = (category: CauseCategory, weight: number, rationale: string) =>
    causes.push({ category, weight, rationale });

  const repeats = stats.lapsWithEvent >= Math.max(2, stats.lapsAnalyzed * 0.5);

  switch (marker.category) {
    case 'Abrupt hit':
    case 'Wheelspin':
    case 'Loss of drive':
      if (repeats && stats.meanDelayAfterReopenS > 0.15 && stats.meanDelayAfterReopenS < 1.0) {
        push('Torque transition', 0.62, 'Slip spike consistently follows throttle reopening by a fixed delay across laps — consistent with an abrupt torque step in the partial-throttle region.');
      } else {
        push('Track condition', 0.45, 'Event does not repeat consistently at the same throttle relationship — surface variation is the stronger prior.');
      }
      push('Suspension', 0.35, 'Rear suspension unload at the same track feature can present as loss of drive.');
      push('Tire', 0.3, 'Rear tire wear or pressure drift produces the same rider sensation.');
      push('Clutch', 0.25, 'Aggressive clutch re-engagement can spike rear-wheel torque.');
      push('Rider input', 0.2, 'Line and throttle-rate variation across laps is not excluded.');
      break;
    case 'Bog':
    case 'Throttle-response delay':
      push('Fueling', 0.55, 'Hesitation on reopening is most often transient enrichment mismatch in the low-throttle region.');
      push('Clutch', 0.3, 'Clutch drag or release point can mimic a bog.');
      push('Rider input', 0.2, 'Throttle chop-and-reopen technique interacts with any transient behavior.');
      break;
    case 'Excessive engine braking':
    case 'Insufficient engine braking':
      push('Engine braking', 0.6, 'Rider report directly concerns closed-throttle behavior.');
      push('Gearing', 0.3, 'Final-drive choice changes perceived engine braking.');
      break;
    case 'Overheating':
      push('Temperature', 0.6, `Coolant ${stats.coolantC.toFixed(0)} °C at the marker.`);
      push('Mechanical', 0.3, 'Coolant flow or radiator blockage must be excluded first.');
      break;
    case 'Hard starting':
    case 'Inconsistent launch':
      push('Clutch', 0.45, 'Launch variance correlates with release technique before any map factor.');
      push('Fueling', 0.3, 'Launch-region fueling only after clutch and surface are excluded.');
      push('Rider input', 0.25, 'Start technique variance.');
      break;
    default:
      push('Unknown', 0.3, 'Insufficient signal in the analyzed window to rank a likely cause.');
      push('Rider input', 0.2, 'More markers on repeated laps would improve the ranking.');
  }
  if (sensorIssues) {
    push('Sensor', 0.28, 'One or more channels were degraded in this session — a sensor artifact cannot be excluded.');
  }
  return causes.sort((a, b) => b.weight - a.weight);
}

function nonMapChecksFor(categories: CauseCategory[]): string[] {
  const checks = new Set<string>();
  for (const c of categories) {
    if (c === 'Tire') { checks.add('Check rear tire wear and pressure against session sheet.'); }
    if (c === 'Suspension') { checks.add('Verify sag and rear compression clicks against the setup snapshot.'); }
    if (c === 'Clutch') { checks.add('Check clutch free play, plate wear, and rider release technique on video if available.'); }
    if (c === 'Track condition') { checks.add('Walk the section — compare rut depth and moisture with earlier laps.'); }
    if (c === 'Gearing') { checks.add('Confirm sprocket sizes and chain wear match the recorded gearing.'); }
    if (c === 'Temperature') { checks.add('Inspect radiators for mud blockage; verify coolant level cold.'); }
    if (c === 'Mechanical') { checks.add('Inspect for intake leaks and exhaust damage.'); }
    if (c === 'Sensor') { checks.add('Re-seat and recalibrate the flagged sensors before the next session.'); }
  }
  return [...checks];
}

/** Human decision on a recommendation. This is the ONLY way status changes. */
export function decideRecommendation(
  db: Db,
  actor: User,
  rec: AIRecommendation,
  decision: Extract<RecommendationStatus, 'ACCEPTED_FOR_TEST' | 'REJECTED' | 'REVISED'>,
  note: string,
): AIRecommendation {
  assertCan(actor.role, 'ai.decide');
  rec.status = decision;
  rec.tunerDecisionNote = note;
  rec.decidedByUserId = actor.id;
  appendAudit(db, actor.id, `ai.${decision.toLowerCase()}`, 'AIRecommendation', rec.id,
    `Recommendation ${decision.replaceAll('_', ' ').toLowerCase()}: ${note}`);
  return rec;
}

// ------------------------------------------------------------- A/B analysis

export interface SessionComparison {
  metric: string;
  a: number;
  b: number;
  betterIs: 'lower' | 'higher';
  unit: string;
}

export function compareSessions(db: Db, a: Session, b: Session): SessionComparison[] {
  const simA = simulateSession(db, a);
  const simB = simulateSession(db, b);
  const lapTimes = (laps: { timeS: number }[]) => laps.map((l) => l.timeS);
  const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / Math.max(1, xs.length);
  const std = (xs: number[]) => {
    const m = mean(xs);
    return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)));
  };
  const p95 = (xs: number[]) => [...xs].sort((x, y) => x - y)[Math.floor(xs.length * 0.95)] ?? 0;

  return [
    { metric: 'Best lap', a: Math.min(...lapTimes(simA.laps)), b: Math.min(...lapTimes(simB.laps)), betterIs: 'lower', unit: 's' },
    { metric: 'Mean lap', a: +mean(lapTimes(simA.laps)).toFixed(2), b: +mean(lapTimes(simB.laps)).toFixed(2), betterIs: 'lower', unit: 's' },
    { metric: 'Lap consistency (σ)', a: +std(lapTimes(simA.laps)).toFixed(2), b: +std(lapTimes(simB.laps)).toFixed(2), betterIs: 'lower', unit: 's' },
    { metric: 'Peak slip (p95)', a: +p95(simA.channels.slip).toFixed(1), b: +p95(simB.channels.slip).toFixed(1), betterIs: 'lower', unit: '%' },
    { metric: 'Mean coolant', a: +mean(simA.channels.coolant).toFixed(1), b: +mean(simB.channels.coolant).toFixed(1), betterIs: 'lower', unit: '°C' },
  ];
}

/** Does the telemetry direction agree with the rider's preference? */
export function telemetrySupportsPreference(rows: SessionComparison[], preferred: 'A' | 'B'): boolean {
  let score = 0;
  for (const r of rows) {
    const bBetter = r.betterIs === 'lower' ? r.b < r.a : r.b > r.a;
    score += (bBetter ? 1 : -1) * (preferred === 'B' ? 1 : -1);
  }
  return score > 0;
}
