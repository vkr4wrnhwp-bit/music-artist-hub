import React, { useState } from 'react';
import { rankStarts, startInsight, type StartRankKey } from '@mxlab/domain';
import { useApp } from '../state';
import { EmptyState, Help, Panel, Pill, Prov } from '../ui';

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
  const [compare, setCompare] = useState(false);
  const attempts = db.startAttempts.filter((a) => a.sessionId === sessionId);
  const session = db.sessions.find((s) => s.id === sessionId);
  const ranked = attempts.length ? rankStarts(attempts, rank) : [];
  const insight = attempts.length ? startInsight(attempts) : null;
  const best = attempts.length ? rankStarts(attempts, 'fastest')[0] : null;

  if (!sessionsWithStarts.length) {
    return (
      <div>
        <div className="page-title"><h1>Start Lab</h1></div>
        <EmptyState title="No start attempts recorded yet">Run a start-practice session and attempts will appear here.</EmptyState>
      </div>
    );
  }

  return (
    <div>
      <div className="page-title">
        <h1>Start Lab</h1>
        <span className="sub">launch outcomes with honest cause attribution</span>
      </div>
      <div className="btn-row" style={{ marginBottom: 20 }}>
        <select value={sessionId} onChange={(e) => setSessionId(e.target.value)} style={{ background: 'var(--raised)', borderRadius: 7, padding: '8px 12px', border: 0 }}>
          {sessionsWithStarts.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective}</option>)}
        </select>
        {session && <span className="hint">{db.bikes.find((b) => b.id === session.bikeId)?.label} · {db.riders.find((r) => r.id === session.riderId)?.name}</span>}
      </div>

      {insight && best && (
        <>
          <section className="hero" style={{ padding: '24px 28px' }}>
            <p className="eyebrow">Best start · #{best.n}</p>
            <div style={{ display: 'flex', gap: 44, flexWrap: 'wrap', margin: '10px 0 4px' }}>
              <span className="pit-stat" style={{ fontSize: 36 }}>{best.timeTo30MphS.toFixed(2)}s<small>0–30 mph</small></span>
              <span className="pit-stat" style={{ fontSize: 36 }}>{best.estWheelspinPct.toFixed(0)}%<small>wheelspin</small></span>
              <span className="pit-stat" style={{ fontSize: 36 }}>
                σ{insight.stdTimeTo30.toFixed(2)}<small>consistency across {insight.attempts}</small>
              </span>
            </div>
            <div className="btn-row" style={{ marginTop: 16 }}>
              <button className="btn primary" onClick={() => setCompare(!compare)}>{compare ? 'Hide comparison' : 'Compare Starts'}</button>
            </div>
          </section>

          <section className="insight">
            <p className="eyebrow">TRACE finding</p>
            <h4>{insight.mapChangeAdvised ? 'Launch delivery is the least consistent variable.' : 'Wheelspin variance tracks release technique and surface — not RPM handling.'}</h4>
            <p><b>Recommendation:</b> {insight.recommendation[0]} {insight.recommendation[1] ?? ''}</p>
            <p className="hint">
              Map change advised: <Pill tone={insight.mapChangeAdvised ? 'warning' : 'good'}>{insight.mapChangeAdvised ? 'Review launch region (tuner)' : 'No — retain current map'}</Pill>
              {' '}· computed from the recorded attempts <Prov p="SIMULATION" />
            </p>
          </section>
          <Help id="startlab">
            A bad start is not automatically a map problem. TRACE checks whether RPM handling or
            wheelspin variance dominates and recommends <b>clutch, gearing, tire, or gate prep first</b>
            when the evidence points there.
          </Help>

          {compare && (
            <Panel title={`All attempts — ranked by ${RANKS.find((r) => r[0] === rank)?.[1]}`}>
              <div className="btn-row" style={{ marginBottom: 12 }}>
                {RANKS.map(([k, label]) => (
                  <button key={k} className={`btn small ${rank === k ? 'primary' : 'ghost'}`} onClick={() => setRank(k)}>{label}</button>
                ))}
              </div>
              <div className="tbl-scroll">
                <table className="data">
                  <thead>
                    <tr><th>#</th><th>Gate</th><th>Surface</th><th>Init RPM</th><th>RPM drop</th><th>Spin</th><th>0–30 mph</th><th>2nd phase</th><th>Rider</th></tr>
                  </thead>
                  <tbody>
                    {ranked.map((a) => (
                      <tr key={a.id} style={a.id === best.id ? { background: 'var(--accent-soft)' } : undefined}>
                        <td className="num">{a.n}</td>
                        <td>{a.gatePick}</td>
                        <td>{a.moisture}</td>
                        <td className="num">{a.initialRpm.toLocaleString()}</td>
                        <td className="num">{(a.initialRpm - a.minRpmAfterRelease).toLocaleString()} <span className="hint">({insight.rpmDropPctVsMean(a) > 0 ? '+' : ''}{insight.rpmDropPctVsMean(a)}%)</span></td>
                        <td className="num">{a.estWheelspinPct}%</td>
                        <td className="num">{a.timeTo30MphS.toFixed(2)}s</td>
                        <td className="num">{a.secondPhaseG.toFixed(2)}g</td>
                        <td className="num">{a.riderRating}/5</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </>
      )}
    </div>
  );
}
