import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createSeededDb, fullMerge, type Db } from '@mxlab/domain';
import { startTraceServer, type TraceServer } from '../src/server';

let srv: TraceServer;
let base: string;
let userToken = '';
const ORG = 'org-demo';

const api = async (path: string, init: RequestInit = {}, token = userToken) => {
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  const ct = res.headers.get('content-type') ?? '';
  return { status: res.status, body: ct.includes('json') ? await res.json() : Buffer.from(await res.arrayBuffer()) };
};

beforeAll(async () => {
  srv = await startTraceServer(mkdtempSync(join(tmpdir(), 'trace-srv-')), 0);
  base = `http://localhost:${srv.port}`;
  const login = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-tuner', role: 'tuner' }) }, '');
  userToken = login.body.token;
});
afterAll(async () => { await srv.close(); });

describe('auth', () => {
  it('issues demo tokens and rejects bad ones', async () => {
    expect(userToken.length).toBeGreaterThan(20);
    const bad = await api(`/orgs/${ORG}/db`, {}, 'not.a.token');
    expect(bad.status).toBe(401);
    const noToken = await api(`/orgs/${ORG}/db`, {}, '');
    expect(noToken.status).toBe(401);
  });
  it('a token for another org is rejected', async () => {
    const other = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: 'org-other', userId: 'x', role: 'tuner' }) }, '');
    const res = await api(`/orgs/${ORG}/db`, {}, other.body.token);
    expect(res.status).toBe(403);
  });
});

describe('sync with optimistic concurrency', () => {
  it('initial push, pull, stale push → 409 → client merge → retry', async () => {
    const db = createSeededDb();
    const push1 = await api(`/orgs/${ORG}/db`, { method: 'PUT', body: JSON.stringify({ baseRev: 0, db }) });
    expect(push1.status).toBe(200);
    expect(push1.body.rev).toBe(1);

    const pull = await api(`/orgs/${ORG}/db`);
    expect(pull.status).toBe(200);
    expect(pull.body.rev).toBe(1);
    expect(pull.body.db.org.id).toBe(ORG);

    // device B pushes a divergent decision edit at rev 1
    const dbB: Db = JSON.parse(JSON.stringify(pull.body.db));
    dbB.decisions[0] = { ...dbB.decisions[0], outcome: 'Edited on device B' };
    dbB.sessions.push({ ...dbB.sessions[0], id: 'sess-device-b' });
    const push2 = await api(`/orgs/${ORG}/db`, { method: 'PUT', headers: { 'If-Match': '1' }, body: JSON.stringify({ db: dbB }) });
    expect(push2.status).toBe(200);
    expect(push2.body.rev).toBe(2);

    // device A, still on rev 1, pushes its own divergent edit → stale
    const dbA: Db = JSON.parse(JSON.stringify(pull.body.db));
    dbA.decisions[0] = { ...dbA.decisions[0], outcome: 'Edited on device A' };
    dbA.sessions.push({ ...dbA.sessions[0], id: 'sess-device-a' });
    const stale = await api(`/orgs/${ORG}/db`, { method: 'PUT', headers: { 'If-Match': '1' }, body: JSON.stringify({ db: dbA }) });
    expect(stale.status).toBe(409);
    expect(stale.body.rev).toBe(2);

    // client-side merge with the conflict-preserving policy, then retry
    const { merged, conflicts } = fullMerge(dbA, stale.body.db as Db);
    expect(conflicts.some((c) => c.entityType === 'DecisionRecord')).toBe(true); // both edits preserved for review
    expect(merged.sessions.some((s) => s.id === 'sess-device-a')).toBe(true);
    expect(merged.sessions.some((s) => s.id === 'sess-device-b')).toBe(true);    // nothing lost
    const retry = await api(`/orgs/${ORG}/db`, { method: 'PUT', headers: { 'If-Match': '2' }, body: JSON.stringify({ db: merged }) });
    expect(retry.status).toBe(200);
    expect(retry.body.rev).toBe(3);
  });
});

describe('telemetry chunks (outside the metadata store)', () => {
  it('uploads and downloads binary chunks', async () => {
    const payload = Buffer.from(Float32Array.from([1.5, 2.5, 3.5]).buffer);
    const up = await fetch(`${base}/orgs/${ORG}/telemetry/sess-9`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${userToken}`, 'Content-Type': 'application/octet-stream' },
      body: payload,
    });
    expect(up.status).toBe(200);
    const down = await api(`/orgs/${ORG}/telemetry/sess-9`);
    expect(down.status).toBe(200);
    expect(Buffer.compare(down.body as Buffer, payload)).toBe(0);
  });
});

describe('remote-access grant enforcement (server-side)', () => {
  let grantToken = '';
  it('mints a scoped token for an active grant', async () => {
    const res = await api('/auth/grant-token', { method: 'POST', body: JSON.stringify({ orgId: ORG, grantId: 'grant-1' }) }, '');
    expect(res.status).toBe(200);
    grantToken = res.body.token;
    expect(res.body.scope.bikeIds).toEqual(['bike-450']);
  });
  it('grant reads are redacted to scope; team IP is never exposed', async () => {
    const res = await api(`/orgs/${ORG}/db`, {}, grantToken);
    expect(res.status).toBe(200);
    expect(res.body.redacted).toBe(true);
    const db = res.body.db as Db;
    expect(db.bikes.map((b) => b.id)).toEqual(['bike-450']);
    expect(db.sessions.every((s) => s.bikeId === 'bike-450')).toBe(true);
    expect(db.decisions).toHaveLength(0);
    expect(db.audit).toHaveLength(0);
    expect(db.users).toHaveLength(0);
    expect(db.testPlans).toHaveLength(0);
  });
  it('grant tokens can never write', async () => {
    const res = await api(`/orgs/${ORG}/db`, { method: 'PUT', headers: { 'If-Match': '3' }, body: JSON.stringify({ db: {} }) }, grantToken);
    expect(res.status).toBe(403);
  });
  it('telemetry export is denied when the grant does not allow it', async () => {
    const res = await api(`/orgs/${ORG}/telemetry/sess-9`, {}, grantToken);
    expect(res.status).toBe(403);
    expect(res.body.error).toMatch(/export/);
  });
  it('revoking the grant kills existing tokens immediately', async () => {
    const pull = await api(`/orgs/${ORG}/db`);
    const db = pull.body.db as Db;
    db.grants.find((g) => g.id === 'grant-1')!.revokedAt = new Date().toISOString();
    const push = await api(`/orgs/${ORG}/db`, { method: 'PUT', headers: { 'If-Match': String(pull.body.rev) }, body: JSON.stringify({ db }) });
    expect(push.status).toBe(200);
    const res = await api(`/orgs/${ORG}/db`, {}, grantToken);
    expect(res.status).toBe(403);
  });
});
