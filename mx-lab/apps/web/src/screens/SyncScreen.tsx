import React, { useState } from 'react';
import { appendAudit, simulateSession, type SyncConflict } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill } from '../ui';
import {
  changePassword, defaultServerUrl, loadConflicts, loadSyncConfig, saveConflicts, saveSyncConfig,
  serverLogin, syncNow, uploadTelemetry, type SyncConfig,
} from '../syncClient';

/**
 * Team Sync — the production persistence backend, self-hosted.
 * Local-first stays true: the app never needs the server; the server makes
 * the team database durable, shared, and grant-enforceable.
 */
export function SyncScreen() {
  const { db, user, update, allowed } = useApp();
  const [cfg, setCfg] = useState<SyncConfig | null>(() => loadSyncConfig());
  const [serverUrl, setServerUrl] = useState(cfg?.serverUrl ?? defaultServerUrl());
  const [password, setPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [pwOld, setPwOld] = useState('');
  const [pwNew, setPwNew] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string>(cfg?.lastSyncedAt ? `Last synced ${new Date(cfg.lastSyncedAt).toLocaleString()} (rev ${cfg.lastRev})` : 'Not connected yet.');
  const [conflicts, setConflicts] = useState<SyncConflict[]>(() => loadConflicts());
  const [archiveMsg, setArchiveMsg] = useState('');
  if (!user) return null;

  const refresh = () => { setCfg(loadSyncConfig()); setConflicts(loadConflicts()); };

  const connect = async () => {
    setBusy(true);
    try {
      const { token, firstLogin } = await serverLogin(serverUrl, db.org.id, user.id, user.role, password, inviteCode.trim() || undefined);
      const next: SyncConfig = {
        serverUrl, token, userLabel: `${user.name} (${user.role})`,
        lastRev: cfg?.lastRev ?? 0, auto: cfg?.auto ?? false,
      };
      saveSyncConfig(next);
      setCfg(next);
      setPassword('');
      setInviteCode('');
      setStatus(firstLogin
        ? 'Password set and signed in. Run Sync now to push the team database.'
        : 'Signed in to the sync server. Run Sync now to push the team database.');
    } catch (e) {
      setStatus(`Could not sign in: ${(e as Error).message}`);
    } finally { setBusy(false); }
  };

  const runSync = async () => {
    const c = loadSyncConfig();
    if (!c) return;
    setBusy(true);
    const outcome = await syncNow(db, c);
    update((d) => {
      appendAudit(d, user.id, 'sync.run', 'Organization', d.org.id, outcome.detail);
    });
    setStatus(outcome.detail);
    refresh();
    setBusy(false);
  };

  const resolve = (i: number, take: 'local' | 'remote') => {
    const c = conflicts[i];
    update((d) => {
      if (take === 'remote') {
        if (c.entityType === 'TraceFocus') {
          d.focus = c.remote as typeof d.focus;
        } else {
          const list = (c.entityType === 'MapRevision' ? d.mapRevisions
            : c.entityType === 'DecisionRecord' ? d.decisions
              : d.debriefs) as Array<{ id: string }>;
          const idx = list.findIndex((x) => x.id === c.entityId);
          if (idx >= 0) list[idx] = c.remote as { id: string };
        }
      }
      appendAudit(d, user.id, 'sync.resolve', c.entityType, c.entityId,
        `Sync conflict resolved by keeping the ${take} version.`);
    });
    const rest = conflicts.filter((_, k) => k !== i);
    saveConflicts(rest);
    setConflicts(rest);
  };

  // tuner (map.approveForTest), crew chief / manager (abtest.conclude), admin (user.manage)
  const canManage = allowed('user.manage') || allowed('map.approveForTest') || allowed('abtest.conclude');

  return (
    <div>
      <div className="page-title">
        <h1>Team Sync</h1>
        <span className="sub">self-hosted persistence — local-first stays true</span>
      </div>
      <Help id="sync">
        The app never needs a connection; the sync server makes the team database <b>durable and
        shared</b>. Conflicting approvals and decisions are preserved on both sides and land here for a
        human to resolve — nothing is ever overwritten silently.
      </Help>

      <div className="cols">
        <Panel title="Server">
          <div className="field"><label>Sync server URL</label>
            <input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} placeholder="http://localhost:8787" />
          </div>
          <div className="field"><label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="min 8 characters" />
          </div>
          <div className="field"><label>Invite code (first sign-in on an established team)</label>
            <input className="mono" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} placeholder="one-time code from your team admin" />
          </div>
          <p className="hint" style={{ marginBottom: 12 }}>
            Run it with <code className="mono">npm run server</code> in mx-lab. Your <b>first sign-in
            sets your password</b> (scrypt-hashed on the server). Once the team database is on the
            server, new accounts need a one-time invite code from an admin, and the server takes roles
            from the database, never from this device. An IdP for SSO swaps in at /auth/login.
          </p>
          <div className="btn-row">
            <button className="btn primary" disabled={busy} onClick={connect}>
              {cfg?.token ? 'Re-sign in' : 'Sign in to server'}
            </button>
            <button className="btn" disabled={busy || !cfg?.token} onClick={runSync}>Sync now</button>
            {cfg?.token && (
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13.5 }}>
                <input type="checkbox" checked={cfg.auto}
                  onChange={(e) => { const n = { ...cfg, auto: e.target.checked }; saveSyncConfig(n); setCfg(n); }} />
                Auto-sync after changes
              </label>
            )}
            {cfg?.token && <button className="btn ghost small" onClick={() => { saveSyncConfig(null); setCfg(null); setStatus('Disconnected — fully local again.'); }}>Disconnect</button>}
          </div>
          <p style={{ marginTop: 12, fontSize: 13.5 }}>
            <Pill tone={cfg?.token ? 'good' : 'neutral'}>{cfg?.token ? `Connected as ${cfg.userLabel}` : 'Offline / local only'}</Pill>
          </p>
          <p className="hint">{status}</p>

          <details style={{ marginTop: 14 }}>
            <summary style={{ cursor: 'pointer', fontSize: 13.5, color: 'var(--ink-2)' }}>Change password</summary>
            <div className="field" style={{ marginTop: 10 }}><label>Current password</label>
              <input type="password" value={pwOld} onChange={(e) => setPwOld(e.target.value)} />
            </div>
            <div className="field"><label>New password (min 8 characters)</label>
              <input type="password" value={pwNew} onChange={(e) => setPwNew(e.target.value)} />
            </div>
            <div className="btn-row">
              <button className="btn small" disabled={busy || !pwOld || !pwNew} onClick={async () => {
                setBusy(true);
                try {
                  await changePassword(serverUrl, db.org.id, user.id, pwOld, pwNew);
                  setPwOld(''); setPwNew('');
                  setPwMsg('Password changed. Existing sign-ins stay valid until their tokens expire.');
                } catch (e) { setPwMsg((e as Error).message); } finally { setBusy(false); }
              }}>Change password</button>
              {pwMsg && <span className="hint">{pwMsg}</span>}
            </div>
          </details>
        </Panel>

        <Panel title={`Sync conflicts (${conflicts.length})`}>
          {conflicts.length === 0 && <p className="hint" style={{ margin: 0 }}>None — no divergent edits awaiting review.</p>}
          {conflicts.map((c, i) => (
            <div key={`${c.entityType}-${c.entityId}-${i}`} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px', marginBottom: 10 }}>
              <p style={{ margin: 0, fontWeight: 700 }}>{c.entityType} · <span className="mono">{c.entityId}</span></p>
              <p className="hint" style={{ margin: '4px 0 8px' }}>{c.reason}</p>
              <div className="tbl-scroll">
                <table className="data">
                  <tbody>
                    <tr><td style={{ width: 90, color: 'var(--muted)' }}>Local</td><td className="mono" style={{ fontSize: 11.5 }}>{JSON.stringify(c.local).slice(0, 180)}…</td></tr>
                    <tr><td style={{ color: 'var(--muted)' }}>Remote</td><td className="mono" style={{ fontSize: 11.5 }}>{JSON.stringify(c.remote).slice(0, 180)}…</td></tr>
                  </tbody>
                </table>
              </div>
              {canManage ? (
                <div className="btn-row" style={{ marginTop: 8 }}>
                  <button className="btn small" onClick={() => resolve(i, 'local')}>Keep local</button>
                  <button className="btn small" onClick={() => resolve(i, 'remote')}>Take remote</button>
                </div>
              ) : <p className="hint">A tuner, crew chief, or manager resolves conflicts.</p>}
            </div>
          ))}
        </Panel>
      </div>

      <Panel title="Telemetry archive (binary chunks, outside the metadata store)">
        <p className="hint" style={{ marginTop: 0 }}>
          Archives a session's full simulated trace to the server as a binary chunk — the storage path
          real MX Node data will use. Grant tokens can only download it when export is allowed.
        </p>
        <div className="btn-row">
          <select id="arch-session" style={{ background: 'var(--raised)', border: 0, borderRadius: 7, padding: '8px 12px' }}>
            {db.sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective.slice(0, 44)}</option>)}
          </select>
          <button className="btn" disabled={!cfg?.token || busy} onClick={async () => {
            const sel = (document.getElementById('arch-session') as HTMLSelectElement).value;
            const session = db.sessions.find((s) => s.id === sel)!;
            const sim = simulateSession(db, session);
            const flat = new Float32Array([...sim.t, ...sim.channels.rpm, ...sim.channels.tps, ...sim.channels.speed]);
            try {
              const msg = await uploadTelemetry(loadSyncConfig()!, db.org.id, session.id, flat);
              setArchiveMsg(`${session.id}: ${msg}`);
              update((d) => appendAudit(d, user.id, 'telemetry.archive', 'Session', session.id, `Telemetry chunk archived to sync server (${msg}).`));
            } catch (e) { setArchiveMsg((e as Error).message); }
          }}>Archive telemetry</button>
          {archiveMsg && <span className="hint">{archiveMsg}</span>}
        </div>
      </Panel>
    </div>
  );
}
