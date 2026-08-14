import { fullMerge, type Db, type SyncConflict } from '@mxlab/domain';

/**
 * Client sync engine for the self-hosted TRACE sync server.
 * Cycle: pull → merge locally with the conflict-preserving policy → push with
 * optimistic concurrency → retry once on a race. Conflicts are queued for
 * human resolution; approvals and decisions are never silently overwritten.
 */

export interface SyncConfig {
  serverUrl: string;
  token: string;
  userLabel: string;
  lastRev: number;
  lastSyncedAt?: string;
  auto: boolean;
}

const CFG_KEY = 'mx-lab-sync-cfg';
const CONFLICTS_KEY = 'mx-lab-sync-conflicts';

/**
 * When the app is served by the sync server itself (Render, a pit laptop),
 * the team server IS this origin — prefill it. Local dev keeps :8787.
 */
export function defaultServerUrl(): string {
  const { protocol, hostname, origin } = window.location;
  if (protocol.startsWith('http') && hostname !== 'localhost' && hostname !== '127.0.0.1') return origin;
  return 'http://localhost:8787';
}

export function loadSyncConfig(): SyncConfig | null {
  try { return JSON.parse(localStorage.getItem(CFG_KEY) ?? 'null'); } catch { return null; }
}
export function saveSyncConfig(cfg: SyncConfig | null): void {
  if (cfg) localStorage.setItem(CFG_KEY, JSON.stringify(cfg));
  else localStorage.removeItem(CFG_KEY);
}
export function loadConflicts(): SyncConflict[] {
  try { return JSON.parse(localStorage.getItem(CONFLICTS_KEY) ?? '[]'); } catch { return []; }
}
export function saveConflicts(cs: SyncConflict[]): void {
  localStorage.setItem(CONFLICTS_KEY, JSON.stringify(cs));
}

export async function serverLogin(
  serverUrl: string, orgId: string, userId: string, role: string, password: string, inviteCode?: string,
): Promise<{ token: string; firstLogin: boolean }> {
  const res = await fetch(`${serverUrl.replace(/\/$/, '')}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ orgId, userId, role, password, inviteCode }),
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(out.error ?? `login failed (${res.status})`);
  return { token: out.token as string, firstLogin: !!out.firstLogin };
}

export async function changePassword(
  serverUrl: string, orgId: string, userId: string, oldPassword: string, newPassword: string,
): Promise<void> {
  const res = await fetch(`${serverUrl.replace(/\/$/, '')}/auth/change-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ orgId, userId, oldPassword, newPassword }),
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((out as { error?: string }).error ?? `change failed (${res.status})`);
}

/** Admin-minted one-time sign-in code; the server stores only its hash. */
export async function mintInvite(cfg: SyncConfig, orgId: string, userId: string): Promise<string> {
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, '')}/orgs/${orgId}/invites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${cfg.token}` },
    body: JSON.stringify({ userId }),
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((out as { error?: string }).error ?? `invite failed (${res.status})`);
  return (out as { code: string }).code;
}

// ---- remote-tuner grant flow: mint on the team side, consume read-only ----

export interface GrantScope { bikeIds: string[]; readMaps: boolean; exportAllowed: boolean }

export async function mintGrantToken(cfg: SyncConfig, orgId: string, grantId: string): Promise<{ token: string; scope: GrantScope }> {
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, '')}/auth/grant-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${cfg.token}` },
    body: JSON.stringify({ orgId, grantId }),
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(out.error ?? `mint failed (${res.status})`);
  return out as { token: string; scope: GrantScope };
}

/** The server redacts to the grant's scope before anything leaves it. */
export async function fetchGrantView(serverUrl: string, orgId: string, token: string): Promise<{ rev: number; db: Db }> {
  const res = await fetch(`${serverUrl.replace(/\/$/, '')}/orgs/${orgId}/db`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(out.error ?? `fetch failed (${res.status})`);
  return out as { rev: number; db: Db };
}

export async function downloadGrantTelemetry(serverUrl: string, orgId: string, token: string, sessionId: string): Promise<ArrayBuffer> {
  const res = await fetch(`${serverUrl.replace(/\/$/, '')}/orgs/${orgId}/telemetry/${sessionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const out = await res.json().catch(() => ({}));
    throw new Error((out as { error?: string }).error ?? `download failed (${res.status})`);
  }
  return res.arrayBuffer();
}

export interface SyncOutcome {
  status: 'synced' | 'conflicts' | 'offline' | 'error';
  rev?: number;
  newConflicts: number;
  detail: string;
}

/** Runs one sync cycle. Mutates `db` in place with the merged result. */
export async function syncNow(db: Db, cfg: SyncConfig): Promise<SyncOutcome> {
  const base = cfg.serverUrl.replace(/\/$/, '');
  const auth = { Authorization: `Bearer ${cfg.token}` };
  const orgPath = `${base}/orgs/${db.org.id}/db`;
  let newConflicts: SyncConflict[] = [];

  try {
    // 1. pull + merge
    let serverRev = 0;
    const pull = await fetch(orgPath, { headers: auth });
    if (pull.status === 200) {
      const remote = await pull.json() as { rev: number; db: Db };
      serverRev = remote.rev;
      if (remote.rev !== cfg.lastRev) {
        const { merged, conflicts } = fullMerge(db, remote.db);
        Object.assign(db, merged);
        newConflicts = conflicts;
      }
    } else if (pull.status !== 404) {
      const err = await pull.json().catch(() => ({ error: `HTTP ${pull.status}` }));
      return { status: 'error', newConflicts: 0, detail: err.error ?? `pull failed (${pull.status})` };
    }

    // 2. push with optimistic concurrency; retry once on a race
    for (let attempt = 0; attempt < 2; attempt++) {
      const push = await fetch(orgPath, {
        method: 'PUT',
        headers: { ...auth, 'Content-Type': 'application/json', 'If-Match': String(serverRev) },
        body: JSON.stringify({ db }),
      });
      if (push.status === 200) {
        const { rev } = await push.json();
        if (newConflicts.length) saveConflicts([...loadConflicts(), ...newConflicts]);
        cfg.lastRev = rev;
        cfg.lastSyncedAt = new Date().toISOString();
        saveSyncConfig(cfg);
        return {
          status: newConflicts.length ? 'conflicts' : 'synced',
          rev,
          newConflicts: newConflicts.length,
          detail: newConflicts.length
            ? `Synced at rev ${rev} — ${newConflicts.length} conflict${newConflicts.length > 1 ? 's' : ''} need review (both versions preserved).`
            : `Synced at rev ${rev}.`,
        };
      }
      if (push.status === 409) {
        const remote = await push.json() as { rev: number; db: Db };
        serverRev = remote.rev;
        const { merged, conflicts } = fullMerge(db, remote.db);
        Object.assign(db, merged);
        newConflicts = [...newConflicts, ...conflicts];
        continue;
      }
      const err = await push.json().catch(() => ({ error: `HTTP ${push.status}` }));
      return { status: 'error', newConflicts: 0, detail: err.error ?? `push failed (${push.status})` };
    }
    return { status: 'error', newConflicts: 0, detail: 'Sync raced twice — try again.' };
  } catch (e) {
    return { status: 'offline', newConflicts: 0, detail: `Server unreachable (${(e as Error).message}) — working offline, changes stay local.` };
  }
}

/** Archive a session's simulated telemetry trace as a binary chunk. */
export async function uploadTelemetry(cfg: SyncConfig, orgId: string, sessionId: string, samples: Float32Array): Promise<string> {
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, '')}/orgs/${orgId}/telemetry/${sessionId}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${cfg.token}`, 'Content-Type': 'application/octet-stream' },
    body: samples.buffer as ArrayBuffer,
  });
  if (!res.ok) throw new Error(`upload failed (${res.status})`);
  const { bytes } = await res.json();
  return `${(bytes / 1024).toFixed(1)} KB archived`;
}

// ---- live polling: displays pull when the server revision moves ----

export async function fetchServerRev(cfg: SyncConfig, orgId: string): Promise<number> {
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, '')}/orgs/${orgId}/rev`, {
    headers: { Authorization: `Bearer ${cfg.token}` },
  });
  if (!res.ok) throw new Error(`rev probe failed (${res.status})`);
  return ((await res.json()) as { rev: number }).rev;
}

/**
 * One poll tick: probe the server revision and run a full sync cycle only if
 * it moved. Returns true when new data landed (caller re-renders). Protected
 * records still conflict instead of changing silently — live mode never
 * bypasses the merge policy.
 */
export async function pollForChanges(db: Db): Promise<boolean> {
  const cfg = loadSyncConfig();
  if (!cfg?.token) return false;
  try {
    const rev = await fetchServerRev(cfg, db.org.id);
    if (rev === cfg.lastRev) return false;
    const outcome = await syncNow(db, cfg);
    return outcome.status === 'synced' || outcome.status === 'conflicts';
  } catch {
    return false; // unreachable server never disturbs the display
  }
}

// debounced auto-sync hook, registered by the app shell
let timer: ReturnType<typeof setTimeout> | null = null;
export function maybeAutoSync(db: Db, onDone?: (o: SyncOutcome) => void): void {
  const cfg = loadSyncConfig();
  if (!cfg?.auto || !cfg.token) return;
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    void syncNow(db, cfg).then((o) => onDone?.(o));
  }, 1500);
}
