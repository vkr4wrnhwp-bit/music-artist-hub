import { beforeEach, describe, expect, it } from 'vitest';
import {
  buildRecommendation, canTransition, checkCompatibility, computeReadiness,
  createFutureFlashJob, createSeededDb, decideRecommendation, diffRevisions,
  exceedsEnvelope, executeFlashJob, FUTURE_FLASH_DISABLED_MESSAGE,
  mergeMapRevisions, mulberry32, can, RIDER_FORBIDDEN, simulateSession,
  startInsight, telemetrySupportsPreference, compareSessions, transitionRevision,
} from '../src';
import type { Db, MapRevision, User } from '../src';

let db: Db;
const user = (id: string) => db.users.find((u) => u.id === id)!;

beforeEach(() => {
  db = createSeededDb();
});

// ------------------------------------------------------------- permissions

describe('permissions', () => {
  it('riders can never approve maps, edit ECU definitions, confirm transfers, or define envelopes', () => {
    for (const action of RIDER_FORBIDDEN) {
      expect(can('rider', action)).toBe(false);
    }
  });
  it('riders can submit feedback and view sessions but not create revisions', () => {
    expect(can('rider', 'feedback.submit')).toBe(true);
    expect(can('rider', 'session.view')).toBe(true);
    expect(can('rider', 'map.createRevision')).toBe(false);
  });
  it('mechanics can confirm transfers but not approve maps', () => {
    expect(can('mechanic', 'transfer.confirm')).toBe(true);
    expect(can('mechanic', 'map.approveForTest')).toBe(false);
  });
  it('tuners can approve maps and decide recommendations', () => {
    expect(can('tuner', 'map.approveForTest')).toBe(true);
    expect(can('tuner', 'ai.decide')).toBe(true);
  });
  it('viewers are read-only', () => {
    expect(can('viewer', 'map.view')).toBe(true);
    expect(can('viewer', 'setup.edit')).toBe(false);
    expect(can('viewer', 'transfer.confirm')).toBe(false);
  });
});

// ------------------------------------------------------------- compatibility

describe('compatibility gates', () => {
  it('a 450 revision is blocked on the 250 bike (ECU mismatch)', () => {
    const rev450 = db.mapRevisions.find((r) => r.id === 'rev-450-r03')!;
    const bike250 = db.bikes.find((b) => b.id === 'bike-250')!;
    const res = checkCompatibility(rev450.compatibility, db, bike250);
    expect(res.blocking).toBe(true);
    expect(res.verdict).toBe('ECU mismatch');
  });
  it('the current 250 baseline is compatible with its bike', () => {
    const r07 = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const bike250 = db.bikes.find((b) => b.id === 'bike-250')!;
    const res = checkCompatibility(r07.compatibility, db, bike250);
    expect(res.blocking).toBe(false);
    expect(res.verdict).toBe('Compatible');
  });
  it('an unidentified bike is Unverified and blocking', () => {
    const bike = { ...db.bikes[0], ecuInstanceId: undefined };
    const r07 = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const res = checkCompatibility(r07.compatibility, db, bike);
    expect(res.verdict).toBe('Unverified');
    expect(res.blocking).toBe(true);
  });
  it('fuel change is a blocking mismatch', () => {
    const bike = JSON.parse(JSON.stringify(db.bikes[0]));
    bike.setup.fuelId = 'fuel-pump-93';
    const r07 = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    expect(checkCompatibility(r07.compatibility, db, bike).verdict).toBe('Fuel mismatch');
  });
});

// ------------------------------------------------------------- readiness

describe('readiness gates', () => {
  it('overall status equals the worst unresolved critical gate', () => {
    const bike450 = db.bikes.find((b) => b.id === 'bike-450')!;
    const r = computeReadiness(db, bike450);
    // seeded sensor failure: rear wheel-speed Missing on node-02
    expect(r.readyForInstrumentedTest).toBe(false);
    expect(r.status).toBe('Sensor Fault');
  });
  it('the 250 is ready for test with all critical gates passing', () => {
    const bike250 = db.bikes.find((b) => b.id === 'bike-250')!;
    const r = computeReadiness(db, bike250);
    expect(r.gates.filter((g) => g.critical).every((g) => g.pass)).toBe(true);
    expect(r.status).toBe('Ready for Test');
  });
  it('losing identity confirmation degrades status — no inference can restore it', () => {
    const bike = { ...db.bikes.find((b) => b.id === 'bike-250')!, identityConfirmed: false };
    const r = computeReadiness(db, bike);
    expect(r.readyForInstrumentedTest).toBe(false);
    expect(r.status).toBe('Not Inventoried');
  });
  it('a bike without a transfer confirmation for its loaded map is not ready', () => {
    const bike = JSON.parse(JSON.stringify(db.bikes.find((b) => b.id === 'bike-250')!));
    db.transfers = db.transfers.filter((t) => t.mapRevisionId !== bike.currentMapRevisionId);
    const r = computeReadiness(db, bike);
    expect(r.status).toBe('Awaiting Approval');
  });
});

// ------------------------------------------------------------- map workflow

describe('map approval workflow', () => {
  const draft = (): MapRevision => {
    const r07 = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const d: MapRevision = JSON.parse(JSON.stringify(r07));
    d.id = 'rev-test-draft';
    d.rev = 'R08';
    d.state = 'DRAFT';
    delete d.approvedByUserId;
    db.mapRevisions.push(d);
    return d;
  };

  it('follows the lifecycle and audits every transition', () => {
    const d = draft();
    const tuner = user('u-tuner');
    const mech = user('u-mech');
    const before = db.audit.length;
    transitionRevision(db, tuner, d, 'TUNER_REVIEW');
    transitionRevision(db, tuner, d, 'APPROVED_FOR_TEST');
    transitionRevision(db, tuner, d, 'EXPORTED');
    transitionRevision(db, mech, d, 'TRANSFER_CONFIRMED');
    transitionRevision(db, tuner, d, 'TESTED');
    transitionRevision(db, tuner, d, 'ACCEPTED');
    transitionRevision(db, tuner, d, 'TEAM_BASELINE');
    expect(db.audit.length - before).toBe(7);
    expect(d.approvedByUserId).toBe('u-tuner');
  });
  it('rejects invalid transitions', () => {
    const d = draft();
    expect(canTransition('DRAFT', 'TEAM_BASELINE')).toBe(false);
    expect(() => transitionRevision(db, user('u-tuner'), d, 'TEAM_BASELINE')).toThrow(/Invalid/);
  });
  it('riders cannot approve for test', () => {
    const d = draft();
    transitionRevision(db, user('u-tuner'), d, 'TUNER_REVIEW');
    expect(() => transitionRevision(db, user('u-rider1'), d, 'APPROVED_FOR_TEST')).toThrow(/Permission denied/);
  });
  it('diff identifies exactly the changed cells', () => {
    const a = db.mapRevisions.find((r) => r.id === 'rev-250-r06')!;
    const b = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const diff = diffRevisions(a, b);
    expect(diff.length).toBeGreaterThan(0);
    for (const d of diff) expect(d.a).not.toBe(d.b);
  });
  it('envelope check flags oversized steps and missing envelopes', () => {
    const a = db.mapRevisions.find((r) => r.id === 'rev-250-r06')!;
    const b: MapRevision = JSON.parse(JSON.stringify(a));
    b.id = 'rev-oversize';
    b.tables.fuel[4][3] += 8; // exceeds ±3 validated step
    expect(exceedsEnvelope(db, a, b).exceeded).toBe(true);

    const c: MapRevision = JSON.parse(JSON.stringify(a));
    c.id = 'rev-no-env';
    c.compatibility = { ...c.compatibility, envelopeVersion: 'ENV-MISSING' };
    c.tables.fuel[4][3] += 0.5;
    const res = exceedsEnvelope(db, a, c);
    expect(res.exceeded).toBe(true);
    expect(res.details[0]).toMatch(/No validated tuning envelope/);
  });
});

// ------------------------------------------------------------- AI guardrails

describe('AI race engineer guardrails', () => {
  it('creates recommendations only in AWAITING_TUNER_REVIEW', () => {
    const s = db.sessions.find((x) => x.id === 'sess-6')!;
    const m = db.markers.find((x) => x.id === 'mark-3')!;
    const rec = buildRecommendation(db, s, m, 'test statement');
    expect(rec.status).toBe('AWAITING_TUNER_REVIEW');
    expect(rec.provenance).toBe('AI INFERENCE');
  });
  it('never mutates map revision state', () => {
    const states = db.mapRevisions.map((r) => r.state);
    const s = db.sessions.find((x) => x.id === 'sess-6')!;
    const m = db.markers.find((x) => x.id === 'mark-3')!;
    buildRecommendation(db, s, m, 'test');
    expect(db.mapRevisions.map((r) => r.state)).toEqual(states);
  });
  it('caps confidence when data quality is degraded', () => {
    const s = db.sessions.find((x) => x.id === 'sess-6')!; // node-02 has slip: Missing
    const m = db.markers.find((x) => x.id === 'mark-3')!;
    const rec = buildRecommendation(db, s, m, 'test');
    expect(rec.dataQualityStatus).toBe('DEGRADED');
    expect(rec.confidencePct).toBeLessThanOrEqual(55);
    expect(rec.missingData.length).toBeGreaterThan(0);
  });
  it('never reaches certainty even with clean repeated evidence', () => {
    const s = db.sessions.find((x) => x.id === 'sess-4')!;
    const m = db.markers.find((x) => x.id === 'mark-1')!;
    const rec = buildRecommendation(db, s, m, 'test');
    expect(rec.confidencePct).toBeLessThanOrEqual(90);
  });
  it('only authorized roles may decide; deciding is audited', () => {
    const rec = db.recommendations.find((r) => r.id === 'rec-open')!;
    expect(() => decideRecommendation(db, user('u-rider1'), rec, 'ACCEPTED_FOR_TEST', 'no')).toThrow(/Permission denied/);
    const before = db.audit.length;
    decideRecommendation(db, user('u-tuner'), rec, 'REJECTED', 'sensor fault first');
    expect(rec.status).toBe('REJECTED');
    expect(db.audit.length).toBe(before + 1);
  });
  it('proposes non-map checks alongside any map region', () => {
    const rec = db.recommendations.find((r) => r.id === 'rec-open')!;
    expect(rec.nonMapChecks.length).toBeGreaterThan(0);
    expect(rec.alternativeCauses.length).toBeGreaterThan(1);
  });
  it('A/B telemetry agreement is computed, not asserted', () => {
    const a = db.sessions.find((x) => x.id === 'sess-4')!;
    const b = db.sessions.find((x) => x.id === 'sess-5')!;
    const rows = compareSessions(db, a, b);
    expect(rows.length).toBeGreaterThanOrEqual(4);
    expect(typeof telemetrySupportsPreference(rows, 'B')).toBe('boolean');
  });
});

// ------------------------------------------------------------- simulator

describe('telemetry simulator', () => {
  it('is deterministic for a given seed', () => {
    const r1 = mulberry32(42);
    const r2 = mulberry32(42);
    expect([r1(), r1(), r1()]).toEqual([r2(), r2(), r2()]);
  });
  it('produces identical traces on regeneration', () => {
    const s = db.sessions[0];
    const a = simulateSession(db, s);
    const b = simulateSession(createSeededDb(), { ...s });
    expect(a.channels.rpm.slice(0, 50)).toEqual(b.channels.rpm.slice(0, 50));
  });
  it('respects the rev limit of the engine build', () => {
    const s = db.sessions.find((x) => x.bikeId === 'bike-450')!;
    const sim = simulateSession(db, s);
    const revLimit = db.engineBuilds.find((b) => b.id === 'build-450-b03')!.revLimit;
    expect(Math.max(...sim.channels.rpm)).toBeLessThanOrEqual(revLimit);
  });
});

// ------------------------------------------------------------- start lab

describe('start lab', () => {
  it('does not advise a map change when spin variance dominates', () => {
    const attempts = db.startAttempts;
    const insight = startInsight(attempts);
    expect(insight.attempts).toBe(12);
    expect(insight.mapChangeAdvised).toBe(false);
    expect(insight.recommendation.join(' ')).toMatch(/clutch/i);
  });
});

// ------------------------------------------------------------- future flash

describe('future flash job (Phase 4 slot)', () => {
  it('is DISABLED and can never execute', () => {
    const job = createFutureFlashJob('job-1');
    expect(job.status).toBe('DISABLED');
    expect(job.message).toBe(FUTURE_FLASH_DISABLED_MESSAGE);
    expect(() => executeFlashJob(job)).toThrow(FUTURE_FLASH_DISABLED_MESSAGE);
  });
});

// ------------------------------------------------------------- offline sync

describe('offline sync merge', () => {
  it('preserves both versions on approval conflicts and never overwrites', () => {
    const local = db;
    const r07 = local.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const remote: MapRevision = JSON.parse(JSON.stringify(r07));
    remote.state = 'REJECTED'; // divergent decision made elsewhere
    const { merged, conflicts } = mergeMapRevisions(local, [remote]);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].requiresReview).toBe(true);
    // local approval untouched:
    expect(merged.mapRevisions.find((r) => r.id === r07.id)!.state).toBe('TEAM_BASELINE');
  });
  it('adds unseen remote revisions without conflict', () => {
    const r07 = db.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    const remote: MapRevision = JSON.parse(JSON.stringify(r07));
    remote.id = 'rev-remote-new';
    const { merged, conflicts } = mergeMapRevisions(db, [remote]);
    expect(conflicts).toHaveLength(0);
    expect(merged.mapRevisions.some((r) => r.id === 'rev-remote-new')).toBe(true);
  });
});

// ------------------------------------------------------------- seed sanity

describe('seeded demo data (section 25)', () => {
  it('contains the required demonstration entities', () => {
    expect(db.bikes).toHaveLength(2);
    expect(db.riders).toHaveLength(2);
    expect(db.ecuDefinitions).toHaveLength(2);
    expect(db.tracks).toHaveLength(2);
    expect(db.engineBuilds).toHaveLength(3);
    expect(db.mapRevisions.length).toBeGreaterThanOrEqual(4);
    expect(db.sessions).toHaveLength(6);
    expect(db.startAttempts).toHaveLength(12);
    expect(db.recommendations.length).toBeGreaterThanOrEqual(3);
    expect(db.recommendations.some((r) => r.status === 'REJECTED')).toBe(true);
    expect(db.mapRevisions.some((r) => r.state === 'TEAM_BASELINE')).toBe(true);
    expect(db.abTests).toHaveLength(1);
    // sensor failure + maintenance warning present
    expect(Object.values(db.devices[1].channelHealth)).toContain('Missing');
    expect(db.bikes.some((b) => b.maintenanceStatus !== 'Current')).toBe(true);
  });
  it('every ECU definition and device is explicitly simulated', () => {
    expect(db.ecuDefinitions.every((e) => e.simulated)).toBe(true);
    expect(db.devices.every((d) => d.simulated)).toBe(true);
    expect(db.sessions.every((s) => s.simulated)).toBe(true);
  });
});
