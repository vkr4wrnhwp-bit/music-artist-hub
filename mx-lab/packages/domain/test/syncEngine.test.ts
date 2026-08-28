import { beforeEach, describe, expect, it } from 'vitest';
import { createSeededDb, fullMerge, redactDbForGrant } from '../src';
import type { Db } from '../src';

let a: Db;
let b: Db;
beforeEach(() => {
  a = createSeededDb();
  b = JSON.parse(JSON.stringify(a)) as Db;
});

describe('fullMerge', () => {
  it('unions append-only collections from both sides — nothing lost', () => {
    a.sessions.push({ ...a.sessions[0], id: 'sess-local-only' });
    b.sessions.push({ ...b.sessions[0], id: 'sess-remote-only' });
    b.audit.push({ ...b.audit[0], id: 'audit-remote-only' });
    const { merged, conflicts } = fullMerge(a, b);
    expect(merged.sessions.some((s) => s.id === 'sess-local-only')).toBe(true);
    expect(merged.sessions.some((s) => s.id === 'sess-remote-only')).toBe(true);
    expect(merged.audit.some((e) => e.id === 'audit-remote-only')).toBe(true);
    expect(conflicts).toHaveLength(0);
  });
  it('divergent decisions preserve both versions as conflicts', () => {
    a.decisions[0] = { ...a.decisions[0], outcome: 'local view' };
    b.decisions[0] = { ...b.decisions[0], outcome: 'remote view' };
    const { conflicts } = fullMerge(a, b);
    const c = conflicts.find((x) => x.entityType === 'DecisionRecord');
    expect(c).toBeDefined();
    expect(c!.requiresReview).toBe(true);
    expect((c!.local as { outcome: string }).outcome).toBe('local view');
    expect((c!.remote as { outcome: string }).outcome).toBe('remote view');
  });
  it('divergent map approvals stay protected (inherited policy)', () => {
    const rev = b.mapRevisions.find((r) => r.id === 'rev-250-r07')!;
    rev.state = 'REJECTED';
    const { merged, conflicts } = fullMerge(a, b);
    expect(conflicts.some((c) => c.entityType === 'MapRevision')).toBe(true);
    expect(merged.mapRevisions.find((r) => r.id === 'rev-250-r07')!.state).toBe('TEAM_BASELINE');
  });
  it('divergent TRACE Focus is a conflict, never a silent overwrite', () => {
    b.focus = { ...b.focus!, text: 'Different objective set remotely.' };
    const { merged, conflicts } = fullMerge(a, b);
    expect(conflicts.some((c) => c.entityType === 'TraceFocus')).toBe(true);
    expect(merged.focus!.text).toBe(a.focus!.text); // local stands until a human resolves
  });
});

describe('redactDbForGrant', () => {
  it('scopes to granted bikes and hides team IP', () => {
    const grant = a.grants[0]; // bike-450, no export, no map edit
    const red = redactDbForGrant(a, grant);
    expect(red.bikes.map((x) => x.id)).toEqual(['bike-450']);
    expect(red.sessions.every((s) => s.bikeId === 'bike-450')).toBe(true);
    expect(red.mapRevisions.every((r) => r.compatibility.ecuDefinitionId === 'ecu-sim-450')).toBe(true);
    expect(red.decisions).toHaveLength(0);
    expect(red.debriefs).toHaveLength(0);
    expect(red.audit).toHaveLength(0);
    expect(red.users).toHaveLength(0);
    expect(red.focus).toBeUndefined();
  });
  it('readTelemetry=false hides sessions entirely', () => {
    const grant = { ...a.grants[0], readTelemetry: false };
    const red = redactDbForGrant(a, grant);
    expect(red.sessions).toHaveLength(0);
    expect(red.markers).toHaveLength(0);
  });
});
