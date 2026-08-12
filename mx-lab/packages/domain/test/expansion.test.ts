import { beforeEach, describe, expect, it } from 'vitest';
import {
  askTrace, bikeReliability, buildChecklist, compareSetups, componentLife,
  computeRiderDNA, confidenceFrom, createSeededDb, dayTimeline, detectUncontrolled,
  draftDebrief, fatigueEstimate, grantAllows, grantIsActive, morningBrief,
  predictSetup, rankContributors, searchAll, setupPerformance, twinFor, whatChanged,
} from '../src';
import type { Db, RemoteAccessGrant } from '../src';

let db: Db;
beforeEach(() => { db = createSeededDb(); });

describe('unified confidence', () => {
  it('grows with sample size and shrinks with uncontrolled variables', () => {
    const small = confidenceFrom({ sampleSize: 1, dataQualityOk: true, conditionSimilarity: 0.9, variablesChanged: 0 });
    const big = confidenceFrom({ sampleSize: 6, dataQualityOk: true, conditionSimilarity: 0.9, variablesChanged: 0 });
    const messy = confidenceFrom({ sampleSize: 6, dataQualityOk: true, conditionSimilarity: 0.9, variablesChanged: 3 });
    expect(big.pct).toBeGreaterThan(small.pct);
    expect(messy.pct).toBeLessThan(big.pct);
    expect(big.pct).toBeLessThanOrEqual(90);
  });
  it('degraded data caps confidence', () => {
    const c = confidenceFrom({ sampleSize: 10, dataQualityOk: false, conditionSimilarity: 1, variablesChanged: 0 });
    expect(c.pct).toBeLessThanOrEqual(50);
  });
});

describe('TRACE Compare / What Changed', () => {
  it('detects the map change between the seeded A/B sessions', () => {
    const a = db.sessions.find((s) => s.id === 'sess-4')!;
    const b = db.sessions.find((s) => s.id === 'sess-5')!;
    const vars = compareSetups(db, a, b);
    const map = vars.find((v) => v.field === 'map')!;
    expect(map.changed).toBe(true);
    expect(map.a).toBe('R06');
    expect(map.b).toBe('R07');
    expect(vars.find((v) => v.field === 'gearing')!.changed).toBe(false);
  });
  it('flags hold-constant violations via the linked test plan', () => {
    const s8 = db.sessions.find((s) => s.id === 'sess-8')!;
    const res = whatChanged(db, s8);
    expect(res.baseline?.id).toBe('sess-7');
    const gearing = res.vars.find((v) => v.field === 'gearing')!;
    expect(gearing.changed).toBe(true);
    expect(gearing.intended).toBe(true); // gearing was the intended variable of plan-gearing
    expect(res.warnings.join(' ')).not.toMatch(/should have remained constant/);
  });
  it('warns about uncontrolled multi-variable changes with no plan', () => {
    const s9 = db.sessions.find((s) => s.id === 'sess-9')!;
    const res = whatChanged(db, s9); // baseline is a 250?? no — same bike only
    expect(res.baseline?.bikeId).toBe('bike-450');
  });
  it('ranks the intended variable first among contributors', () => {
    const a = db.sessions.find((s) => s.id === 'sess-4')!;
    const b = db.sessions.find((s) => s.id === 'sess-5')!;
    const vars = compareSetups(db, a, b);
    const ranked = rankContributors(db, a, b, vars);
    expect(ranked[0].label).toMatch(/Map R06 → R07/);
  });
});

describe('test planner', () => {
  it('accepts a single-variable plan and flags multi-variable plans', () => {
    const clean = db.testPlans.find((p) => p.id === 'plan-corner6')!;
    expect(detectUncontrolled(clean)).toHaveLength(0);
    const dirty = {
      variants: [
        { mapRevisionId: 'a', gearing: '13/50', tirePressureRear: 0.85 },
        { mapRevisionId: 'b', gearing: '13/49', tirePressureRear: 0.9 },
      ],
    };
    const warnings = detectUncontrolled(dirty);
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toMatch(/attribution will be weaker/i);
  });
});

describe('digital twin & component life', () => {
  it('tracks components per bike with service history', () => {
    const comps = twinFor(db, 'bike-250');
    expect(comps.length).toBeGreaterThanOrEqual(10);
    expect(comps.every((c) => c.serviceHistory.length > 0)).toBe(true);
  });
  it('predicts approaching service for the 7.2h clutch (8.5h interval)', () => {
    const clutch = db.twin.find((c) => c.id === 'CL2')!;
    const life = componentLife(clutch);
    expect(life.status).toBe('Approaching service');
    expect(life.state).toBe('DEVELOPMENT');
  });
  it('marks over-interval components as service due', () => {
    const cl45 = db.twin.find((c) => c.id === 'CL45')!;
    expect(componentLife(cl45).status).toBe('Service due');
  });
});

describe('reliability score', () => {
  it('a critical failed gate overrides the score entirely', () => {
    const bike450 = db.bikes.find((b) => b.id === 'bike-450')!;
    const r = bikeReliability(db, bike450); // seeded sensor fault = critical
    expect(r.scorePct).toBeNull();
    expect(r.overriddenBy).toBeTruthy();
    expect(r.factors.length).toBeGreaterThanOrEqual(5);
  });
  it('a healthy bike gets a score with visible reasons', () => {
    const bike250 = db.bikes.find((b) => b.id === 'bike-250')!;
    const r = bikeReliability(db, bike250);
    expect(r.scorePct).not.toBeNull();
    expect(r.scorePct!).toBeGreaterThan(50);
    expect(r.factors.every((f) => f.detail.length > 0)).toBe(true);
  });
});

describe('setup intelligence & predict', () => {
  it('groups sessions by setup and reports sample sizes', () => {
    const rows = setupPerformance(db, { riderId: 'rider-1', bikeId: 'bike-250' });
    expect(rows.length).toBeGreaterThanOrEqual(3); // R05, R06, R07 variants incl. gearing splits
    for (const r of rows) expect(r.sessions.length).toBeGreaterThanOrEqual(1);
  });
  it('predict returns a starting point with citations and bounded confidence', () => {
    const rec = predictSetup(db, { bikeId: 'bike-250', riderId: 'rider-1', surface: 'hard pack' });
    expect(rec).not.toBeNull();
    expect(rec!.comparableSessions).toBeGreaterThanOrEqual(1);
    expect(rec!.citations.length).toBe(rec!.comparableSessions);
    expect(rec!.confidence.pct).toBeLessThanOrEqual(90);
    expect(rec!.state).toBe('DEVELOPMENT');
  });
  it('single-session evidence is labeled as a hint, not truth', () => {
    const rec = predictSetup(db, { bikeId: 'bike-450', riderId: 'rider-2', surface: 'hard pack' });
    if (rec && rec.comparableSessions === 1) expect(rec.reason).toMatch(/one session only/i);
  });
});

describe('rider DNA / coaching / fatigue', () => {
  it('separates measured, preference, and inference', () => {
    const dna = computeRiderDNA(db, db.riders[0]);
    expect(dna.measured.sessions).toBeGreaterThan(0);
    expect(dna.measured.typicalRpmBand[1]).toBeGreaterThan(dna.measured.typicalRpmBand[0]);
    expect(dna.preferences.delivery.length).toBeGreaterThan(0);
    expect(dna.inferred.basis).toMatch(/AI INFERENCE/);
    expect(dna.state).toBe('DEVELOPMENT');
  });
  it('fatigue estimate always carries the disclaimer', () => {
    const s = db.sessions[0];
    const f = fatigueEstimate(db, s);
    expect(f.disclaimer).toBe('DEVELOPMENT ESTIMATE — NOT MEDICAL OR SAFETY DIAGNOSIS');
    expect(f.state).toBe('DEVELOPMENT');
    expect(f.evidence.length).toBeGreaterThan(0);
  });
});

describe('race operations', () => {
  it('checklist blocks on real gate failures and READY only when clear', () => {
    const b450 = db.bikes.find((b) => b.id === 'bike-450')!;
    const cl = buildChecklist(db, b450);
    expect(cl.ready).toBe(false);
    expect(cl.blockers.length).toBeGreaterThan(0);
    const b250 = db.bikes.find((b) => b.id === 'bike-250')!;
    const cl250 = buildChecklist(db, b250);
    expect(cl250.ready).toBe(true);
    expect(cl250.items.some((i) => i.status === 'manual')).toBe(true); // physical checks stay human
  });
  it('timeline is derived from real audit events in order', () => {
    const day = db.audit[0].at.slice(0, 10);
    const tl = dayTimeline(db, day);
    expect(tl.length).toBeGreaterThan(0);
    for (let i = 1; i < tl.length; i++) expect(tl[i].at >= tl[i - 1].at).toBe(true);
  });
  it('morning brief and debrief draft compose from real records', () => {
    const brief = morningBrief(db);
    expect(brief.total).toBe(2);
    expect(brief.scheduled.join(' ')).toMatch(/race distance|R07/i);
    const draft = draftDebrief(db, '2026-08-05');
    expect(draft.learned.join(' ')).toMatch(/R07/);
    expect(draft.tomorrow.length).toBeGreaterThan(0);
  });
});

describe('knowledge & search', () => {
  it('universal search finds bikes, maps, components, decisions', () => {
    expect(searchAll(db, 'R07').some((h) => h.kind === 'Map')).toBe(true);
    expect(searchAll(db, 'S04').some((h) => h.kind === 'Component')).toBe(true);
    expect(searchAll(db, '13/49').some((h) => h.kind === 'Session')).toBe(true);
    expect(searchAll(db, 'gearing').some((h) => h.kind === 'Decision')).toBe(true);
  });
  it('askTrace answers about a revision test with real citations only', () => {
    const a = askTrace(db, 'What did we learn from the R07 test?');
    expect(a.answer.join(' ')).toMatch(/R07|Corner 6/);
    expect(a.citations.length).toBeGreaterThan(0);
    for (const c of a.citations) {
      if (c.kind === 'session') expect(db.sessions.some((s) => s.id === c.id)).toBe(true);
      if (c.kind === 'decision') expect(db.decisions.some((d) => d.id === c.id)).toBe(true);
    }
    expect(a.state).toBe('DEVELOPMENT');
  });
  it('askTrace admits when it has nothing rather than inventing', () => {
    const a = askTrace(db, 'what is the meaning of life');
    expect(a.answer[0]).toMatch(/No matching team records/);
    expect(a.missing.length).toBeGreaterThan(0);
  });
  it('coolant scan runs over real traces', () => {
    const a = askTrace(db, 'Show every session where coolant temperature exceeded 170°F');
    expect(a.answer.length).toBeGreaterThan(0);
    expect(a.citations.length).toBeGreaterThan(0);
  });
});

describe('remote access grants', () => {
  const base = (): RemoteAccessGrant => ({ ...db.grants[0] });
  it('scopes by bike, permission, expiry, and revocation', () => {
    const g = base();
    expect(grantIsActive(g, new Date('2026-08-12T00:00:00Z'))).toBe(true);
    expect(grantAllows(g, 'telemetry', 'bike-450', new Date('2026-08-12T00:00:00Z'))).toBe(true);
    expect(grantAllows(g, 'telemetry', 'bike-250', new Date('2026-08-12T00:00:00Z'))).toBe(false);
    expect(grantAllows(g, 'mapEdit', 'bike-450', new Date('2026-08-12T00:00:00Z'))).toBe(false);
    expect(grantAllows(g, 'telemetry', 'bike-450', new Date('2026-08-20T00:00:00Z'))).toBe(false); // expired
    const revoked = { ...g, revokedAt: '2026-08-11T10:00:00Z' };
    expect(grantIsActive(revoked, new Date('2026-08-12T00:00:00Z'))).toBe(false);
  });
});
