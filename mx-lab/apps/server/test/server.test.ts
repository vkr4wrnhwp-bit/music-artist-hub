import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { createSeededDb, fullMerge, type Db } from '@mxlab/domain';
import { startTraceServer, type TraceServer } from '../src/server';

let srv: TraceServer;
let base: string;
let userToken = '';
let managerToken = '';
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

const PASSWORD = 'pit-lane-secret-9';

beforeAll(async () => {
  srv = await startTraceServer(mkdtempSync(join(tmpdir(), 'trace-srv-')), 0);
  base = `http://localhost:${srv.port}`;
  // first sign-ins set passwords (org db not pushed yet → role claims bootstrap)
  const login = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-tuner', role: 'tuner', password: PASSWORD }) }, '');
  userToken = login.body.token;
  const mgr = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-manager', role: 'team_manager', password: PASSWORD }) }, '');
  managerToken = mgr.body.token;
});
afterAll(async () => { await srv.close(); });

describe('auth (scrypt password, first-sign-in bootstrap)', () => {
  it('first sign-in set the password and issued a token; bad tokens rejected', async () => {
    expect(userToken.length).toBeGreaterThan(20);
    const bad = await api(`/orgs/${ORG}/db`, {}, 'not.a.token');
    expect(bad.status).toBe(401);
    const noToken = await api(`/orgs/${ORG}/db`, {}, '');
    expect(noToken.status).toBe(401);
  });
  it('rejects a short password on first sign-in', async () => {
    const res = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-chief', role: 'crew_chief', password: 'short' }) }, '');
    expect(res.status).toBe(400);
    expect(res.body.error).toMatch(/8 characters/);
  });
  it('rejects the wrong password once one is set', async () => {
    const res = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-tuner', role: 'tuner', password: 'not-the-password' }) }, '');
    expect(res.status).toBe(401);
    expect(res.body.error).toMatch(/wrong password/);
  });
  it('accepts the right password on a repeat sign-in', async () => {
    const res = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-tuner', role: 'tuner', password: PASSWORD }) }, '');
    expect(res.status).toBe(200);
    expect(res.body.firstLogin).toBe(false);
  });
  it('a token for another org is rejected', async () => {
    const other = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: 'org-other', userId: 'x', role: 'tuner', password: PASSWORD }) }, '');
    const res = await api(`/orgs/${ORG}/db`, {}, other.body.token);
    expect(res.status).toBe(403);
  });
  it('once the org db is pushed, unknown users cannot sign in', async () => {
    const db = createSeededDb();
    await api(`/orgs/org-role/db`, { method: 'PUT', body: JSON.stringify({ baseRev: 0, db }) },
      (await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: 'org-role', userId: 'u-tuner', role: 'tuner', password: PASSWORD }) }, '')).body.token);
    const res = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: 'org-role', userId: 'u-intruder', role: 'org_admin', password: PASSWORD }) }, '');
    expect(res.status).toBe(401);
  });
});

describe('sync with optimistic concurrency', () => {
  it('initial push, pull, stale push → 409 → client merge → retry', async () => {
    const db = createSeededDb();
    // the seed's grant is date-pinned demo fiction; pin it into the future so
    // grant tests below stay independent of wall-clock time
    db.grants[0].expiresAt = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
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
  it('lightweight rev probe for live polling', async () => {
    const res = await api(`/orgs/${ORG}/rev`);
    expect(res.status).toBe(200);
    expect(res.body.rev).toBe(3);
    const anon = await api(`/orgs/${ORG}/rev`, {}, '');
    expect(anon.status).toBe(401);
  });
});

describe('same-origin app serving (single-service deployments)', () => {
  it('serves the built app at non-API GETs; the API stays token-gated', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'trace-static-'));
    const htmlPath = join(dir, 'index.html');
    writeFileSync(htmlPath, '<title>TRACE</title><div id="root"></div>');
    const s = await startTraceServer(dir, 0, htmlPath);
    const base2 = `http://localhost:${s.port}`;
    const root = await fetch(`${base2}/`);
    expect(root.status).toBe(200);
    expect(root.headers.get('content-type')).toContain('text/html');
    expect(await root.text()).toContain('TRACE');
    const deep = await fetch(`${base2}/anything`);
    expect(deep.status).toBe(200); // hash-router SPA — every page is the app
    const apiRes = await fetch(`${base2}/orgs/org-x/db`);
    expect(apiRes.status).toBe(401); // API untouched
    await s.close();
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

describe('invite-based provisioning (after the org db is on the server)', () => {
  it('a known user with no password cannot sign in without an invite', async () => {
    const res = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: PASSWORD }) }, '');
    expect(res.status).toBe(403);
    expect(res.body.error).toMatch(/invite/);
  });
  it('minting invites requires user.manage', async () => {
    const res = await api(`/orgs/${ORG}/invites`, { method: 'POST', body: JSON.stringify({ userId: 'u-mech' }) }); // tuner token
    expect(res.status).toBe(403);
  });
  it('manager mints an invite; wrong codes refused; it admits once then dies', async () => {
    const mint = await api(`/orgs/${ORG}/invites`, { method: 'POST', body: JSON.stringify({ userId: 'u-mech' }) }, managerToken);
    expect(mint.status).toBe(200);
    const code = mint.body.code as string;
    expect(code.length).toBeGreaterThan(8);
    const bad = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: PASSWORD, inviteCode: 'wrong-code' }) }, '');
    expect(bad.status).toBe(403);
    const first = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: PASSWORD, inviteCode: code }) }, '');
    expect(first.status).toBe(200);
    expect(first.body.firstLogin).toBe(true);
    // invite consumed; from now on only the password matters
    const again = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: PASSWORD }) }, '');
    expect(again.status).toBe(200);
    expect(again.body.firstLogin).toBe(false);
  });
  it('invites cannot target users outside the team database', async () => {
    const res = await api(`/orgs/${ORG}/invites`, { method: 'POST', body: JSON.stringify({ userId: 'u-ghost' }) }, managerToken);
    expect(res.status).toBe(404);
  });
});

describe('self-service password change', () => {
  it('wrong old password refused; the new password takes effect immediately', async () => {
    const wrong = await api('/auth/change-password', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', oldPassword: 'nope-nope-1', newPassword: 'fresh-brakes-22' }) }, '');
    expect(wrong.status).toBe(401);
    const ok = await api('/auth/change-password', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', oldPassword: PASSWORD, newPassword: 'fresh-brakes-22' }) }, '');
    expect(ok.status).toBe(200);
    const oldPw = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: PASSWORD }) }, '');
    expect(oldPw.status).toBe(401);
    const newPw = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: ORG, userId: 'u-mech', password: 'fresh-brakes-22' }) }, '');
    expect(newPw.status).toBe(200);
  });
});

describe('remote-access grant enforcement (server-side)', () => {
  let grantToken = '';
  it('refuses to mint without a manage-capable user token', async () => {
    const anon = await api('/auth/grant-token', { method: 'POST', body: JSON.stringify({ orgId: ORG, grantId: 'grant-1' }) }, '');
    expect(anon.status).toBe(403);
    const rider = await api('/auth/login', { method: 'POST', body: JSON.stringify({ orgId: 'org-other', userId: 'x', role: 'rider', password: PASSWORD }) }, '');
    const asRider = await api('/auth/grant-token', { method: 'POST', body: JSON.stringify({ orgId: 'org-other', grantId: 'grant-1' }) }, rider.body.token);
    expect(asRider.status).toBe(403);
  });
  it('mints a scoped token for an active grant', async () => {
    const res = await api('/auth/grant-token', { method: 'POST', body: JSON.stringify({ orgId: ORG, grantId: 'grant-1' }) });
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
