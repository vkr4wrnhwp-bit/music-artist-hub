import React, { useMemo, useState } from 'react';
import { appendAudit, predictSetup, setupPerformance } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { EmptyState, Help, Panel, Pill } from '../ui';

/** Setup Intelligence + TRACE Predict — history with sample sizes, never one-session truths. */
export function IntelligenceScreen() {
  const { db, user, update, allowed } = useApp();
  const [riderId, setRiderId] = useState(db.riders[0]?.id ?? '');
  const [bikeId, setBikeId] = useState(db.bikes[0]?.id ?? '');
  const [surface, setSurface] = useState('');

  const rows = useMemo(() => setupPerformance(db, {
    riderId: riderId || undefined, bikeId: bikeId || undefined, surface: surface || undefined,
  }), [db, riderId, bikeId, surface]);

  const prediction = useMemo(() => predictSetup(db, {
    bikeId, riderId, surface: surface || undefined,
  }), [db, bikeId, riderId, surface]);

  const canConfirm = allowed('map.approveForTest') || allowed('setup.edit');

  return (
    <div>
      <div className="page-title">
        <h1>Setup Intelligence</h1>
        <span className="sub">what has actually worked, with sample sizes</span>
        <Pill tone="warning">DEVELOPMENT</Pill>
      </div>
      <Help id="intel">
        Rankings are computed from session snapshots and outcomes. A setup seen once is a data point,
        not a baseline — TRACE always shows how many sessions stand behind a row.
      </Help>
      <div className="btn-row" style={{ marginBottom: 18 }}>
        <select value={riderId} onChange={(e) => setRiderId(e.target.value)}>
          {db.riders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <select value={bikeId} onChange={(e) => setBikeId(e.target.value)}>
          {db.bikes.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
        </select>
        <select value={surface} onChange={(e) => setSurface(e.target.value)}>
          <option value="">Any surface</option>
          <option value="hard pack">Hard pack</option>
          <option value="loam">Loam</option>
        </select>
      </div>

      {prediction && (
        <section className="insight" aria-label="TRACE Predict">
          <p className="eyebrow">TRACE Predict — recommended starting point</p>
          <h4 className="mono">Map {prediction.mapRev} · {prediction.gearing} · rear {prediction.tirePressureRear} bar · sag {prediction.sagMm} mm</h4>
          <p>{prediction.reason}</p>
          <p className="hint">
            Confidence {prediction.confidence.pct}% ({prediction.confidence.label}) · {prediction.comparableSessions} comparable
            session{prediction.comparableSessions === 1 ? '' : 's'} — starting point only, requires confirmation.
          </p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            {prediction.citations.map((c, i) => <a key={i} href={c.href} className="btn small ghost">{c.label}</a>)}
          </div>
          {canConfirm && (
            <div className="btn-row" style={{ marginTop: 10 }}>
              <button className="btn small primary" onClick={() => {
                if (!confirm('Accept this as today\'s baseline? Recorded as a team decision under your name.')) return;
                update((d) => {
                  d.decisions.unshift({
                    id: `dec-${Date.now()}`, orgId: d.org.id, at: new Date().toISOString(),
                    authorUserId: user!.id, bikeId, riderId,
                    sessionIds: prediction.citations.filter((c) => c.kind === 'session').map((c) => c.id),
                    decision: `Baseline accepted from TRACE Predict: map ${prediction.mapRev}, ${prediction.gearing}, rear ${prediction.tirePressureRear} bar.`,
                    rationale: prediction.reason,
                  });
                  appendAudit(d, user!.id, 'predict.accept_baseline', 'Bike', bikeId,
                    `Predicted baseline accepted (${prediction.confidence.pct}% confidence, ${prediction.comparableSessions} sessions).`);
                });
              }}>Accept as baseline</button>
              <button className="btn small ghost" onClick={() => nav('planner')}>Plan a test instead</button>
            </div>
          )}
        </section>
      )}

      <Panel title={`Setup history (${rows.length} distinct setups)`}>
        {rows.length === 0 ? (
          <EmptyState title="No sessions match these filters">Loosen the surface filter or pick another rider.</EmptyState>
        ) : (
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr><th>Setup</th><th>Surface</th><th>Sessions</th><th>Best lap</th><th>Mean lap</th><th>Consistency σ</th><th>Peak slip p95</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key}>
                    <td className="mono" style={{ fontWeight: 650 }}>{r.key}</td>
                    <td>{r.surface}</td>
                    <td className="num">{r.sessions.length} {r.sessions.length === 1 && <Pill tone="warning">n=1</Pill>}</td>
                    <td className="num">{r.bestLap.toFixed(2)}s</td>
                    <td className="num">{r.meanLap.toFixed(2)}s</td>
                    <td className="num">{r.lapSigma.toFixed(2)}</td>
                    <td className="num">{r.peakSlipP95}%</td>
                    <td>{r.sessions.map((id) => <a key={id} href={`#/session/${id}`} style={{ marginRight: 6 }}>↗</a>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="hint">All metrics computed from SIMULATED session traces.</p>
      </Panel>
    </div>
  );
}
