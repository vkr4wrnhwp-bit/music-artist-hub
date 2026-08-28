/**
 * TRACE sync server — self-hostable production persistence backend.
 *
 * Real, durable, and honest about what it is:
 *  - Metadata store: revisioned JSON snapshots on disk behind a ServerStore
 *    interface (a Firestore adapter is a drop-in replacement).
 *  - Telemetry chunks: binary files on disk, NEVER inside the metadata store
 *    (an S3/GCS adapter is a drop-in replacement).
 *  - Auth: HMAC-signed tokens with real verification middleware. Identity
 *    issuance is real password auth (scrypt, timing-safe compare) with a
 *    first-sign-in-sets-password bootstrap; once the org database is on the
 *    server, roles come from it, never from the client. Swapping in an IdP
 *    for SSO replaces only the /auth/login handler.
 *  - Remote-access grants are enforced HERE, server-side: a grant token can
 *    only ever see redacted, scoped data, and denied actions 403.
 *  - Sync: optimistic concurrency. PUT with a stale revision returns 409 plus
 *    the server copy; the client merges with the domain's conflict-preserving
 *    policy and retries. The server never merges silently.
 */
import { createHmac, randomBytes, scryptSync, timingSafeEqual } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import { join } from 'node:path';
import { can, grantIsActive, redactDbForGrant, type Db, type RemoteAccessGrant, type Role } from '@mxlab/domain';

// ------------------------------------------------------------------ store

export interface PasswordRecord { salt: string; hash: string }

export interface ServerStore {
  loadOrg(orgId: string): { rev: number; db: Db } | null;
  saveOrg(orgId: string, rev: number, db: Db): void;
  saveChunk(orgId: string, sessionId: string, data: Buffer): void;
  loadChunk(orgId: string, sessionId: string): Buffer | null;
  loadAuth(orgId: string): Record<string, PasswordRecord> | null;
  saveAuth(orgId: string, records: Record<string, PasswordRecord>): void;
  loadInvites(orgId: string): Record<string, PasswordRecord> | null;
  saveInvites(orgId: string, records: Record<string, PasswordRecord>): void;
}

export class FileStore implements ServerStore {
  constructor(private dir: string) {
    mkdirSync(join(dir, 'telemetry'), { recursive: true });
  }
  private orgPath(orgId: string) { return join(this.dir, `org-${orgId}.json`); }
  loadOrg(orgId: string) {
    const p = this.orgPath(orgId);
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, 'utf8')) as { rev: number; db: Db };
  }
  saveOrg(orgId: string, rev: number, db: Db) {
    // atomic-enough for a pit laptop: write temp then rename would be ideal;
    // single-process writes keep this consistent for Phase 1 self-hosting
    writeFileSync(this.orgPath(orgId), JSON.stringify({ rev, db }));
  }
  saveChunk(orgId: string, sessionId: string, data: Buffer) {
    writeFileSync(join(this.dir, 'telemetry', `${orgId}-${sessionId}.bin`), data);
  }
  loadChunk(orgId: string, sessionId: string) {
    const p = join(this.dir, 'telemetry', `${orgId}-${sessionId}.bin`);
    return existsSync(p) ? readFileSync(p) : null;
  }
  private authPath(orgId: string) { return join(this.dir, `auth-${orgId}.json`); }
  loadAuth(orgId: string) {
    const p = this.authPath(orgId);
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, 'utf8')) as Record<string, PasswordRecord>;
  }
  saveAuth(orgId: string, records: Record<string, PasswordRecord>) {
    writeFileSync(this.authPath(orgId), JSON.stringify(records));
  }
  private invitePath(orgId: string) { return join(this.dir, `invites-${orgId}.json`); }
  loadInvites(orgId: string) {
    const p = this.invitePath(orgId);
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, 'utf8')) as Record<string, PasswordRecord>;
  }
  saveInvites(orgId: string, records: Record<string, PasswordRecord>) {
    writeFileSync(this.invitePath(orgId), JSON.stringify(records));
  }
}

// scrypt helpers shared by passwords and invite codes
function hashSecret(value: string): PasswordRecord {
  const salt = randomBytes(16).toString('hex');
  return { salt, hash: scryptSync(value, salt, 64).toString('hex') };
}
function verifySecret(value: string, rec: PasswordRecord): boolean {
  const got = scryptSync(value, rec.salt, 64);
  const expect = Buffer.from(rec.hash, 'hex');
  return got.length === expect.length && timingSafeEqual(got, expect);
}

// ------------------------------------------------------------------ tokens

interface TokenPayload {
  kind: 'user' | 'grant';
  orgId: string;
  userId?: string;
  role?: string;
  grantId?: string;
  exp: number; // epoch ms
}

export function signToken(secret: string, payload: TokenPayload): string {
  const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
  const sig = createHmac('sha256', secret).update(body).digest('base64url');
  return `${body}.${sig}`;
}

export function verifyToken(secret: string, token: string): TokenPayload | null {
  const [body, sig] = token.split('.');
  if (!body || !sig) return null;
  const expect = createHmac('sha256', secret).update(body).digest();
  const got = Buffer.from(sig, 'base64url');
  if (expect.length !== got.length || !timingSafeEqual(expect, got)) return null;
  try {
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString()) as TokenPayload;
    if (payload.exp < Date.now()) return null;
    return payload;
  } catch {
    return null;
  }
}

// ------------------------------------------------------------------ server

const MAX_BODY = 64 * 1024 * 1024;

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    req.on('data', (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY) { reject(new Error('body too large')); req.destroy(); return; }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function send(res: ServerResponse, status: number, body: unknown, contentType = 'application/json'): void {
  const data = contentType === 'application/json' ? JSON.stringify(body) : (body as Buffer);
  res.writeHead(status, {
    'Content-Type': contentType,
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type, If-Match',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, OPTIONS',
    'Access-Control-Expose-Headers': 'ETag',
  });
  res.end(data);
}

export interface TraceServer {
  server: Server;
  port: number;
  close(): Promise<void>;
}

export function createTraceServer(store: ServerStore, secret: string, staticHtmlPath?: string): Server {
  return createServer(async (req, res) => {
    try {
      if (req.method === 'OPTIONS') { send(res, 204, ''); return; }
      const url = new URL(req.url ?? '/', 'http://localhost');
      const parts = url.pathname.split('/').filter(Boolean);

      // Single-service deployments (e.g. Render) serve the built app from the
      // same origin: any GET outside the API surface returns the one-file app.
      if (staticHtmlPath && req.method === 'GET'
        && parts[0] !== 'orgs' && parts[0] !== 'auth' && existsSync(staticHtmlPath)) {
        send(res, 200, readFileSync(staticHtmlPath), 'text/html; charset=utf-8');
        return;
      }

      // ---- auth: password sign-in (scrypt; first sign-in sets the password) ----
      // An IdP for SSO replaces only this handler. Once the org database has
      // been pushed, it is the authority on who exists and what role they hold.
      if (req.method === 'POST' && url.pathname === '/auth/login') {
        const body = JSON.parse((await readBody(req)).toString() || '{}');
        const { orgId, userId, password } = body;
        let role = body.role as string | undefined;
        if (!orgId || !userId || typeof password !== 'string' || !password) {
          send(res, 400, { error: 'orgId, userId, password required' }); return;
        }
        const orgData = store.loadOrg(orgId);
        if (orgData) {
          const u = orgData.db.users.find((x) => x.id === userId);
          if (!u) { send(res, 401, { error: 'unknown user for this organization' }); return; }
          role = u.role;
        }
        if (!role) { send(res, 400, { error: 'role required until the organization database is first pushed' }); return; }
        const records = store.loadAuth(orgId) ?? {};
        const rec = records[userId];
        if (!rec) {
          if (password.length < 8) {
            send(res, 400, { error: 'first sign-in sets your password — use at least 8 characters' }); return;
          }
          // Bootstrap trust ends the moment the org database is on the server:
          // from then on, a new account's first sign-in needs a one-time invite
          // code minted by a team admin.
          if (orgData) {
            const invites = store.loadInvites(orgId) ?? {};
            const invite = invites[userId];
            const code = typeof body.inviteCode === 'string' ? body.inviteCode.trim() : '';
            if (!invite || !code || !verifySecret(code, invite)) {
              send(res, 403, { error: 'first sign-in for this account needs a one-time invite code from a team admin' }); return;
            }
            delete invites[userId];
            store.saveInvites(orgId, invites);
          }
          records[userId] = hashSecret(password);
          store.saveAuth(orgId, records);
        } else if (!verifySecret(password, rec)) {
          send(res, 401, { error: 'wrong password' }); return;
        }
        const token = signToken(secret, { kind: 'user', orgId, userId, role, exp: Date.now() + 12 * 3600 * 1000 });
        send(res, 200, { token, firstLogin: !rec });
        return;
      }

      // ---- auth: self-service password change (authenticated by the old password) ----
      if (req.method === 'POST' && url.pathname === '/auth/change-password') {
        const body = JSON.parse((await readBody(req)).toString() || '{}');
        const { orgId, userId, oldPassword, newPassword } = body;
        if (!orgId || !userId || typeof oldPassword !== 'string' || typeof newPassword !== 'string') {
          send(res, 400, { error: 'orgId, userId, oldPassword, newPassword required' }); return;
        }
        if (newPassword.length < 8) { send(res, 400, { error: 'new password needs at least 8 characters' }); return; }
        const records = store.loadAuth(orgId) ?? {};
        const rec = records[userId];
        if (!rec || !verifySecret(oldPassword, rec)) { send(res, 401, { error: 'wrong password' }); return; }
        records[userId] = hashSecret(newPassword);
        store.saveAuth(orgId, records);
        send(res, 200, { ok: true });
        return;
      }

      // ---- auth: mint a scoped token for a remote-access grant ----
      // Requires a signed-in user who could manage the test program — the
      // same roles that resolve sync conflicts (tuner, crew chief, manager).
      if (req.method === 'POST' && url.pathname === '/auth/grant-token') {
        const minter = verifyToken(secret, (req.headers.authorization ?? '').replace(/^Bearer /, ''));
        const mayMint = minter?.kind === 'user' && (['user.manage', 'map.approveForTest', 'abtest.conclude'] as const)
          .some((a) => can(minter.role as Role, a));
        if (!mayMint) { send(res, 403, { error: 'minting a grant token requires a signed-in tuner, crew chief, or manager' }); return; }
        const body = JSON.parse((await readBody(req)).toString() || '{}');
        const { orgId, grantId } = body;
        if (minter.orgId !== orgId) { send(res, 403, { error: 'token is for a different organization' }); return; }
        const stored = orgId ? store.loadOrg(orgId) : null;
        const grant = stored?.db.grants.find((g) => g.id === grantId);
        if (!grant || !grantIsActive(grant)) { send(res, 404, { error: 'no active grant with that id — sync first so the server has it' }); return; }
        const token = signToken(secret, {
          kind: 'grant', orgId, grantId,
          exp: Math.min(Date.now() + 12 * 3600 * 1000, new Date(grant.expiresAt).getTime()),
        });
        send(res, 200, { token, scope: { bikeIds: grant.bikeIds, readMaps: grant.readMaps, exportAllowed: grant.exportAllowed } });
        return;
      }

      // ---- everything below requires a token ----
      const auth = (req.headers.authorization ?? '').replace(/^Bearer /, '');
      const who = verifyToken(secret, auth);
      if (!who) { send(res, 401, { error: 'invalid or expired token' }); return; }

      // /orgs/:orgId/...
      if (parts[0] !== 'orgs' || !parts[1]) { send(res, 404, { error: 'not found' }); return; }
      const orgId = parts[1];
      if (who.orgId !== orgId) { send(res, 403, { error: 'token is for a different organization' }); return; }
      const stored = store.loadOrg(orgId);

      const activeGrant = (): RemoteAccessGrant | null => {
        if (who.kind !== 'grant') return null;
        const g = stored?.db.grants.find((x) => x.id === who.grantId);
        return g && grantIsActive(g) ? g : null;
      };

      // GET /orgs/:id/rev — lightweight revision probe for live polling;
      // displays poll this and only pull the db when the number moves
      if (req.method === 'GET' && parts[2] === 'rev' && parts.length === 3) {
        send(res, 200, { rev: stored?.rev ?? 0 });
        return;
      }

      // GET /orgs/:id/db — full db for users; redacted + scoped for grants
      if (req.method === 'GET' && parts[2] === 'db' && parts.length === 3) {
        if (!stored) { send(res, 404, { error: 'organization has no data yet' }); return; }
        if (who.kind === 'grant') {
          const grant = activeGrant();
          if (!grant) { send(res, 403, { error: 'grant expired or revoked' }); return; }
          send(res, 200, { rev: stored.rev, db: redactDbForGrant(stored.db, grant), redacted: true });
          return;
        }
        res.setHeader('ETag', String(stored.rev));
        send(res, 200, { rev: stored.rev, db: stored.db });
        return;
      }

      // PUT /orgs/:id/db — optimistic concurrency; grants can never write
      if (req.method === 'PUT' && parts[2] === 'db' && parts.length === 3) {
        if (who.kind === 'grant') { send(res, 403, { error: 'read-only grant token' }); return; }
        const body = JSON.parse((await readBody(req)).toString());
        const baseRev = Number(req.headers['if-match'] ?? body.baseRev ?? -1);
        const currentRev = stored?.rev ?? 0;
        if (stored && baseRev !== currentRev) {
          // stale: hand the client the server copy — the CLIENT merges with the
          // conflict-preserving domain policy; the server never merges silently
          send(res, 409, { error: 'stale revision', rev: currentRev, db: stored.db });
          return;
        }
        const nextRev = currentRev + 1;
        store.saveOrg(orgId, nextRev, body.db as Db);
        send(res, 200, { rev: nextRev });
        return;
      }

      // POST /orgs/:id/invites — one-time sign-in codes, admin-minted.
      // The code crosses the wire exactly once, here; only its hash is stored.
      if (req.method === 'POST' && parts[2] === 'invites' && parts.length === 3) {
        if (who.kind !== 'user' || !can(who.role as Role, 'user.manage')) {
          send(res, 403, { error: 'minting invites requires a team admin or manager' }); return;
        }
        const body = JSON.parse((await readBody(req)).toString() || '{}');
        const target = stored?.db.users.find((u) => u.id === body.userId);
        if (!target) { send(res, 404, { error: 'no such user in the team database — sync first' }); return; }
        const code = randomBytes(9).toString('base64url');
        const invites = store.loadInvites(orgId) ?? {};
        invites[target.id] = hashSecret(code);
        store.saveInvites(orgId, invites);
        send(res, 200, { userId: target.id, code });
        return;
      }

      // telemetry chunks: binary, outside the metadata store
      if (parts[2] === 'telemetry' && parts[3]) {
        const sessionId = parts[3];
        if (req.method === 'POST') {
          if (who.kind === 'grant') { send(res, 403, { error: 'read-only grant token' }); return; }
          const data = await readBody(req);
          if (!data.length) { send(res, 400, { error: 'empty chunk' }); return; }
          store.saveChunk(orgId, sessionId, data);
          send(res, 200, { ok: true, bytes: data.length });
          return;
        }
        if (req.method === 'GET') {
          const grant = who.kind === 'grant' ? activeGrant() : null;
          if (who.kind === 'grant') {
            if (!grant) { send(res, 403, { error: 'grant expired or revoked' }); return; }
            if (!grant.exportAllowed) { send(res, 403, { error: 'grant does not allow telemetry export' }); return; }
            const session = stored?.db.sessions.find((s) => s.id === sessionId);
            if (!session || !grant.bikeIds.includes(session.bikeId)) { send(res, 403, { error: 'session outside grant scope' }); return; }
          }
          const chunk = store.loadChunk(orgId, sessionId);
          if (!chunk) { send(res, 404, { error: 'no telemetry archived for this session' }); return; }
          send(res, 200, chunk, 'application/octet-stream');
          return;
        }
      }

      send(res, 404, { error: 'not found' });
    } catch (e) {
      send(res, 500, { error: (e as Error).message });
    }
  });
}

export async function startTraceServer(dataDir: string, port = 0, staticHtmlPath?: string): Promise<TraceServer> {
  mkdirSync(dataDir, { recursive: true });
  const secretPath = join(dataDir, 'secret');
  if (!existsSync(secretPath)) writeFileSync(secretPath, randomBytes(32).toString('hex'));
  const secret = readFileSync(secretPath, 'utf8');
  const server = createTraceServer(new FileStore(dataDir), secret, staticHtmlPath);
  await new Promise<void>((resolve) => server.listen(port, resolve));
  const addr = server.address();
  const boundPort = typeof addr === 'object' && addr ? addr.port : port;
  return {
    server,
    port: boundPort,
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}
