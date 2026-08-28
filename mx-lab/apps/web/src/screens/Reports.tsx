import React, { useState } from 'react';
import { appendAudit, compareSessions, exportDb, importDb, simulateSession } from '@mxlab/domain';
import { useApp } from '../state';
import { download, Help, Panel, Pill, Prov, TraceWordmark } from '../ui';
import { AuditList } from './BikeProfile';

export function Reports() {
  const { db, user, update, allowed } = useApp();
  const [kind, setKind] = useState('session');
  const [sessionId, setSessionId] = useState(db.sessions[db.sessions.length - 1]?.id ?? '');
  const session = db.sessions.find((s) => s.id === sessionId);
  const canExport = allowed('report.export');

  return (
    <div>
      {/* one-color black wordmark is a sanctioned print application */}
      <div className="print-only" style={{ marginBottom: 10 }}>
        <TraceWordmark height={18} color="#000" />
      </div>
      <div className="page-title">
        <h1>Reports</h1>
        <span className="sub">printable, exportable, and always labeled with provenance</span>
      </div>
      <Panel title="Report">
        <div className="btn-row">
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="session">Session summary</option>
            <option value="ab">A/B test result</option>
            <option value="setup">Bike setup sheet</option>
            <option value="baseline">Team baseline promotion</option>
          </select>
          {kind === 'session' || kind === 'setup' ? (
            <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
              {db.sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective}</option>)}
            </select>
          ) : null}
          <button className="btn" onClick={() => window.print()}>Print / PDF</button>
          {kind === 'session' && session && (
            <button className="btn" disabled={!canExport} onClick={() => {
              update((d) => appendAudit(d, user!.id, 'report.export', 'Session', session.id, 'Session summary JSON exported.'));
              const sim = simulateSession(db, session);
              download(`${session.id}-summary.json`, JSON.stringify({
                banner: 'SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE',
                session, laps: sim.laps,
              }, null, 2), 'application/json');
            }}>Export JSON</button>
          )}
        </div>
        {!canExport && <p className="hint">Your role can view reports but not export them.</p>}
      </Panel>

      {kind === 'session' && session && <SessionReport sessionId={session.id} />}
      {kind === 'ab' && <AbReport />}
      {kind === 'setup' && session && <SetupSheet sessionId={session.id} />}
      {kind === 'baseline' && <BaselineReport />}

      <Panel title="Team archive (offline backup)">
        <Help id="archive">
          The entire team database can be exported as one JSON archive and re-imported on another
          machine — the offline path when there's no connectivity at the track. Conflicting map
          approvals are never merged silently.
        </Help>
        <div className="btn-row">
          <button className="btn" disabled={!canExport} onClick={() => {
            update((d) => appendAudit(d, user!.id, 'report.export', 'Organization', db.org.id, 'Full archive exported.'));
            download('mx-lab-archive.json', exportDb(db), 'application/json');
          }}>Export full archive</button>
          <label className="btn" style={{ display: 'inline-block' }}>
            Import archive…
            <input type="file" accept=".json" hidden onChange={(e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              f.text().then((text) => {
                try {
                  const incoming = importDb(text);
                  update((d) => {
                    Object.assign(d, incoming);
                    appendAudit(d, user!.id, 'archive.import', 'Organization', d.org.id, 'Archive imported (full replace, local review).');
                  });
                } catch (err) { alert((err as Error).message); }
              });
            }} />
          </label>
        </div>
      </Panel>
    </div>
  );
}

function SessionReport({ sessionId }: { sessionId: string }) {
  const { db } = useApp();
  const s = db.sessions.find((x) => x.id === sessionId)!;
  const sim = simulateSession(db, s);
  const bike = db.bikes.find((b) => b.id === s.bikeId)!;
  const rider = db.riders.find((r) => r.id === s.riderId)!;
  const track = db.tracks.find((t) => t.id === s.trackId)!;
  const rev = db.mapRevisions.find((r) => r.id === s.setupSnapshot.mapRevisionId);
  const fb = db.feedback.find((f) => f.sessionId === s.id);
  const markers = db.markers.filter((m) => m.sessionId === s.id);
  const best = Math.min(...sim.laps.map((l) => l.timeS));
  return (
    <Panel title={`Session summary — ${s.objective}`} actions={<Pill tone="sim">SIMULATED</Pill>}>
      <dl className="kv">
        <dt>Date</dt><dd>{new Date(s.startedAt).toLocaleString()}</dd>
        <dt>Bike / rider</dt><dd className="mono">{bike.label} · {rider.name}</dd>
        <dt>Track</dt><dd>{track.name} ({s.trackCondition.surfaceType}, {s.trackCondition.moisture})</dd>
        <dt>Weather</dt><dd>{s.weather.ambientC}°C · {s.weather.humidityPct}% RH · {s.weather.baroHpa} hPa <Prov p={s.weather.provenance} /></dd>
        <dt>Map</dt><dd className="mono">{rev?.rev} / slot {s.setupSnapshot.mapSlot} / trims {Object.entries(s.setupSnapshot.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</dd>
        <dt>Laps</dt><dd className="mono">{sim.laps.length} · best {best.toFixed(2)}s · mean {(sim.laps.reduce((a, l) => a + l.timeS, 0) / sim.laps.length).toFixed(2)}s</dd>
        <dt>Markers</dt><dd>{markers.length ? markers.map((m, i) => `#${i + 1} ${m.category} (lap ${m.lap})`).join('; ') : 'none'}</dd>
        <dt>Rider verdict</dt><dd>{fb ? `${fb.answers.betterOrWorse}${fb.preferredOverPrevious ? ' — preferred over previous' : ''}` : 'no feedback yet'}</dd>
      </dl>
    </Panel>
  );
}

function AbReport() {
  const { db } = useApp();
  return (
    <>
      {db.abTests.map((ab) => {
        const a = db.sessions.find((s) => s.id === ab.sessionAId);
        const b = db.sessions.find((s) => s.id === ab.sessionBId);
        const revA = db.mapRevisions.find((r) => r.id === ab.revisionAId);
        const revB = db.mapRevisions.find((r) => r.id === ab.revisionBId);
        const rows = a && b ? compareSessions(db, a, b) : [];
        return (
          <Panel key={ab.id} title={ab.name} actions={<Pill tone="sim">SIMULATED</Pill>}>
            <dl className="kv">
              <dt>Revisions</dt><dd className="mono">A = {revA?.rev} · B = {revB?.rev}</dd>
              <dt>Held constant</dt><dd>{ab.holdConstant.join(', ')}</dd>
              <dt>Outcome</dt><dd><Pill tone="good">{ab.outcome ?? 'pending'}</Pill> rider preferred {ab.riderPreferred} · telemetry {ab.telemetrySupportsPreference ? 'agrees' : 'disagrees'}</dd>
              <dt>Conclusion</dt><dd>{ab.conclusion}</dd>
              <dt>Decided by</dt><dd>{db.users.find((u) => u.id === ab.decidedByUserId)?.name}</dd>
            </dl>
            {rows.length > 0 && (
              <table className="data" style={{ marginTop: 8 }}>
                <thead><tr><th>Metric</th><th>A</th><th>B</th></tr></thead>
                <tbody>
                  {rows.map((r) => <tr key={r.metric}><td>{r.metric}</td><td className="num">{r.a}{r.unit}</td><td className="num">{r.b}{r.unit}</td></tr>)}
                </tbody>
              </table>
            )}
          </Panel>
        );
      })}
    </>
  );
}

function SetupSheet({ sessionId }: { sessionId: string }) {
  const { db } = useApp();
  const s = db.sessions.find((x) => x.id === sessionId)!;
  const bike = db.bikes.find((b) => b.id === s.bikeId)!;
  const setup = s.setupSnapshot.setup;
  const build = db.engineBuilds.find((x) => x.id === s.setupSnapshot.engineBuildId);
  return (
    <Panel title={`Bike setup sheet — ${bike.label} @ ${new Date(s.startedAt).toLocaleDateString()}`}>
      <dl className="kv">
        <dt>Engine build</dt><dd className="mono">{build?.code} (rev limit {build?.revLimit.toLocaleString()})</dd>
        <dt>Fuel</dt><dd>{db.fuels.find((f) => f.id === setup.fuelId)?.name}</dd>
        <dt>Exhaust</dt><dd>{db.exhausts.find((e) => e.id === setup.exhaustId)?.name}</dd>
        <dt>Gearing</dt><dd className="mono">{setup.gearing}</dd>
        <dt>Tires</dt><dd>{setup.tireModel} {setup.tireSizeRear} · F {setup.tirePressureFront} / R {setup.tirePressureRear} bar</dd>
        <dt>Suspension</dt><dd>{setup.suspension} · fork {setup.forkHeightMm} mm · sag {setup.sagMm} mm</dd>
        <dt>Clutch</dt><dd>{setup.clutch}</dd>
        <dt>Map / slot / trims</dt><dd className="mono">{db.mapRevisions.find((r) => r.id === s.setupSnapshot.mapRevisionId)?.rev} / {s.setupSnapshot.mapSlot} / {Object.entries(s.setupSnapshot.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</dd>
        <dt>Hours at session</dt><dd className="mono">{s.setupSnapshot.hoursAtSession.toFixed(1)}</dd>
      </dl>
    </Panel>
  );
}

function BaselineReport() {
  const { db } = useApp();
  const baselines = db.mapRevisions.filter((r) => r.state === 'TEAM_BASELINE');
  return (
    <>
      {baselines.map((r) => {
        const map = db.maps.find((m) => m.id === r.mapId)!;
        return (
          <Panel key={r.id} title={`Team baseline — ${map.name}-${r.rev}`}>
            <dl className="kv">
              <dt>Promoted from</dt><dd className="mono">{db.mapRevisions.find((p) => p.id === r.parentRevisionId)?.rev ?? '—'}</dd>
              <dt>Approved by</dt><dd>{db.users.find((u) => u.id === r.approvedByUserId)?.name} · {r.approvedAt && new Date(r.approvedAt).toLocaleString()}</dd>
              <dt>Tested in</dt><dd>{r.testedInSessionIds.join(', ') || '—'}</dd>
              <dt>Compatibility</dt><dd>{r.compatibility.modelYear} {r.compatibility.model} · fw {r.compatibility.ecuFirmware} · build {r.compatibility.engineBuildId}</dd>
              <dt>Notes</dt><dd>{r.notes}</dd>
            </dl>
          </Panel>
        );
      })}
      {baselines.length === 0 && <Panel title="Team baselines"><p className="hint">No team baselines yet.</p></Panel>}
    </>
  );
}

export function AuditScreen() {
  const { db } = useApp();
  const [filter, setFilter] = useState('');
  const events = [...db.audit].sort((a, b) => b.at.localeCompare(a.at))
    .filter((e) => !filter || e.action.includes(filter) || e.summary.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div>
      <div className="page-title">
        <h1>Audit history</h1>
        <span className="sub">append-only — there is no delete API, by design</span>
      </div>
      <Panel title={`${events.length} events`}>
        <div className="field" style={{ maxWidth: 320 }}>
          <label>Filter</label>
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="e.g. transfer, map., approval" />
        </div>
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Entity</th><th>Summary</th></tr></thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{new Date(e.at).toLocaleString()}</td>
                  <td>{db.users.find((u) => u.id === e.actorUserId)?.name ?? e.actorUserId}</td>
                  <td className="mono">{e.action}</td>
                  <td className="mono">{e.entityType}</td>
                  <td>{e.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
