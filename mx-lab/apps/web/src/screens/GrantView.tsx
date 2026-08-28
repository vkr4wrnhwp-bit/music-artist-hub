import React, { useState } from 'react';
import type { Db } from '@mxlab/domain';
import { download, Panel, Pill, TraceLogo } from '../ui';
import { defaultServerUrl, downloadGrantTelemetry, fetchGrantView } from '../syncClient';

/**
 * Remote tuner view — consumes a scoped grant token, no team account needed.
 * Everything shown here was redacted DOWN TO THE GRANT on the server before it
 * left the machine; this screen never writes and never touches local team data.
 */
export function GrantView() {
  const [serverUrl, setServerUrl] = useState(defaultServerUrl());
  const [orgId, setOrgId] = useState('');
  const [token, setToken] = useState('');
  const [view, setView] = useState<{ rev: number; db: Db } | null>(null);
  const [status, setStatus] = useState('Paste the server URL, organization id, and access token your team sent you.');
  const [busy, setBusy] = useState(false);
  const [dlMsg, setDlMsg] = useState('');

  const connect = async () => {
    setBusy(true);
    setDlMsg('');
    try {
      const v = await fetchGrantView(serverUrl, orgId.trim(), token.trim());
      setView(v);
      setStatus(`Connected at server revision ${v.rev}.`);
    } catch (e) {
      setView(null);
      setStatus(`Could not connect: ${(e as Error).message}`);
    } finally { setBusy(false); }
  };

  const downloadTelemetry = async (sessionId: string) => {
    setDlMsg('');
    try {
      const buf = await downloadGrantTelemetry(serverUrl, orgId.trim(), token.trim(), sessionId);
      const f = new Float32Array(buf);
      const nSamples = Math.floor(f.length / 4);
      let csv = 't_s,rpm,tps_pct,speed_kph\n';
      for (let i = 0; i < nSamples; i++) {
        csv += `${f[i]},${f[nSamples + i]},${f[2 * nSamples + i]},${f[3 * nSamples + i]}\n`;
      }
      download(`trace-telemetry-${sessionId}.csv`, csv, 'text/csv');
      setDlMsg(`${sessionId}: ${nSamples} samples exported.`);
    } catch (e) { setDlMsg((e as Error).message); }
  };

  const db = view?.db;
  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, margin: '18px 0 4px' }}>
        <TraceLogo />
        <Pill tone="warning">REMOTE TUNER — READ-ONLY, SCOPED BY GRANT</Pill>
      </div>
      <div className="page-title">
        <h1>Grant view</h1>
        <span className="sub">the server redacts to your grant before anything leaves it</span>
      </div>

      <Panel title="Connect">
        <div className="field"><label>Server URL</label>
          <input value={serverUrl} onChange={(e) => setServerUrl(e.target.value)} placeholder="http://localhost:8787" />
        </div>
        <div className="field"><label>Organization id</label>
          <input value={orgId} onChange={(e) => setOrgId(e.target.value)} placeholder="org-…" />
        </div>
        <div className="field"><label>Access token</label>
          <input className="mono" value={token} onChange={(e) => setToken(e.target.value)} placeholder="paste the token you were sent" />
        </div>
        <div className="btn-row">
          <button className="btn primary" disabled={busy || !orgId.trim() || !token.trim()} onClick={connect}>Connect</button>
          {view && <a className="btn ghost" href="#/garage">Team sign-in</a>}
        </div>
        <p className="hint">{status}</p>
      </Panel>

      {db && (
        <>
          <p className="hint">
            In scope: {db.bikes.length} bike{db.bikes.length === 1 ? '' : 's'} · {db.mapRevisions.length} map
            revision{db.mapRevisions.length === 1 ? '' : 's'} · {db.sessions.length} session{db.sessions.length === 1 ? '' : 's'} —
            decisions, debriefs, test plans, crew, audit, and team identity never leave the server.
          </p>

          <Panel title="Bikes in scope">
            {db.bikes.length === 0 && <p className="hint" style={{ margin: 0 }}>No bikes in this grant's scope.</p>}
            <div className="tbl-scroll">
              <table className="data">
                <tbody>
                  {db.bikes.map((b) => (
                    <tr key={b.id}>
                      <td style={{ fontWeight: 600 }}>{b.label}</td>
                      <td className="mono" style={{ color: 'var(--muted)' }}>{b.bikeModelId}</td>
                      <td className="hint">{b.setup.gearing} · {b.setup.suspension}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <Panel title="Map revisions (read-only)">
            {db.mapRevisions.length === 0 && (
              <p className="hint" style={{ margin: 0 }}>None visible — this grant does not include map access, or no revisions exist for its bikes.</p>
            )}
            {db.mapRevisions.length > 0 && (
              <div className="tbl-scroll">
                <table className="data">
                  <thead><tr><th>Revision</th><th>Status</th><th>Provenance</th></tr></thead>
                  <tbody>
                    {db.mapRevisions.map((r) => (
                      <tr key={r.id}>
                        <td className="mono">{r.rev} · {r.id}</td>
                        <td><Pill tone="neutral">{r.state.replaceAll('_', ' ')}</Pill></td>
                        <td className="hint">{r.provenance}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title="Sessions (telemetry)">
            {db.sessions.length === 0 && (
              <p className="hint" style={{ margin: 0 }}>None visible — this grant does not include telemetry access.</p>
            )}
            {db.sessions.length > 0 && (
              <div className="tbl-scroll">
                <table className="data">
                  <thead><tr><th>Date</th><th>Objective</th><th /></tr></thead>
                  <tbody>
                    {db.sessions.map((s) => (
                      <tr key={s.id}>
                        <td className="mono">{new Date(s.startedAt).toLocaleDateString()}</td>
                        <td>{s.objective}</td>
                        <td>
                          <button className="btn small" onClick={() => downloadTelemetry(s.id)}>Download telemetry</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {dlMsg && <p className="hint">{dlMsg}</p>}
            <p className="hint">
              Downloads are archived binary chunks and require the grant's export permission — the
              server refuses them otherwise.
            </p>
          </Panel>
        </>
      )}
    </div>
  );
}
