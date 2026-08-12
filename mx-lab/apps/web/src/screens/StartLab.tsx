import React, { useState } from 'react';
import { rankStarts, startInsight, type StartRankKey } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill, Prov } from '../ui';

const RANKS: Array<[StartRankKey, string]> = [
  ['fastest', 'Fastest'], ['most_consistent', 'Most consistent'], ['least_wheelspin', 'Least wheelspin'],
  ['best_rpm_control', 'Best RPM control'], ['best_confidence', 'Best rider confidence'],
  ['best_second_phase', 'Best second phase'],
];

export function StartLab() {
  const { db } = useApp();
  const sessionsWithStarts = db.sessions.filter((s) => db.startAttempts.some((a) => a.sessionId === s.id));
  const [sessionId, setSessionId] = useState(sessionsWithStarts[0]?.id ?? '');
  const [rank, setRank] = useState<StartRankKey>('fastest');
  const attempts = db.startAttempts.filter((a) => a.sessionId === sessionId);
  const session = db.sessions.find((s) => s.id === sessionId);
  const ranked = attempts.length ? rankStarts(attempts, rank) : [];
  const insight = attempts.length ? startInsight(attempts) : null;

  return (
    <div>
      <div className="page-title">
        <h1>Start Lab</h1>
        <span className="sub">launch capture, ranking, and honest cause attribution</span>
      </div>
      <Help id="startlab">
        A bad start is not automatically a map problem. The insight below checks whether RPM handling or
        wheelspin variance dominates — and recommends <b>clutch, gearing, tire, or gate prep first</b>
        when the evidence points there.
      </Help>
      <Panel title="Session">
        <div className="btn-row">
          <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
            {sessionsWithStarts.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective}</option>)}
          </select>
          {session && <span className="hint">{db.bikes.find((b) => b.id === session.bikeId)?.label} · {db.riders.find((r) => r.id === session.riderId)?.name} · {db.tracks.find((t) => t.id === session.trackId)?.name}</span>}
        </div>
      </Panel>

      {insight && (
        <div className="cols">
          <Panel title={`Attempts (${attempts.length}) — ranked by ${RANKS.find((r) => r[0] === rank)?.[1]}`}>
            <div className="btn-row" style={{ marginBottom: 10 }}>
              {RANKS.map(([k, label]) => (
                <button key={k} className={`btn small ${rank === k ? 'primary' : ''}`} onClick={() => setRank(k)}>{label}</button>
              ))}
            </div>
            <div className="tbl-scroll">
              <table className="data">
                <thead>
                  <tr><th>#</th><th>Gate</th><th>Surface</th><th>Init RPM</th><th>RPM drop</th><th>Spin</th><th>0–30 mph</th><th>2nd phase</th><th>Rider</th><th /></tr>
                </thead>
                <tbody>
                  {ranked.map((a) => (
                    <tr key={a.id}>
                      <td className="num">{a.n}</td>
                      <td>{a.gatePick}</td>
                      <td>{a.moisture}</td>
                      <td className="num">{a.initialRpm.toLocaleString()}</td>
                      <td className="num">{(a.initialRpm - a.minRpmAfterRelease).toLocaleString()} <span className="hint">({insight.rpmDropPctVsMean(a) > 0 ? '+' : ''}{insight.rpmDropPctVsMean(a)}% vs avg)</span></td>
                      <td className="num">{a.estWheelspinPct}%</td>
                      <td className="num">{a.timeTo30MphS.toFixed(2)}s</td>
                      <td className="num">{a.secondPhaseG.toFixed(2)}g</td>
                      <td className="num">{a.riderRating}/5</td>
                      <td><Prov p={a.provenance} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="Start Lab insight">
            <dl className="kv">
              <dt>Best 0–30</dt><dd className="mono">{insight.bestTimeTo30.toFixed(2)}s</dd>
              <dt>Mean 0–30</dt><dd className="mono">{insight.meanTimeTo30.toFixed(2)}s (σ {insight.stdTimeTo30.toFixed(3)})</dd>
              <dt>Mean wheelspin</dt><dd className="mono">{insight.meanWheelspin}%</dd>
              <dt>Map change advised</dt>
              <dd><Pill tone={insight.mapChangeAdvised ? 'warning' : 'good'}>{insight.mapChangeAdvised ? 'Review launch region (tuner)' : 'No — retain current map'}</Pill></dd>
            </dl>
            <h4 style={{ margin: '12px 0 6px', fontSize: 13 }}>Recommendation</h4>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13.5 }}>
              {insight.recommendation.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
            <p className="hint" style={{ marginTop: 10 }}>
              Computed from the recorded attempts (<Prov p="SIMULATION" />). Any launch-region map work
              still goes through the full tuner-review workflow.
            </p>
          </Panel>
        </div>
      )}
    </div>
  );
}
