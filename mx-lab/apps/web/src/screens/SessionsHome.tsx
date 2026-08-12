import React from 'react';
import { simulateSession } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { EmptyState, Panel, Pill } from '../ui';

/** Sessions overview: today first, then history. One primary action. */
export function SessionsHome() {
  const { db, allowed } = useApp();
  const sessions = [...db.sessions].sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  const today = new Date().toDateString();
  const todays = sessions.filter((s) => new Date(s.startedAt).toDateString() === today);
  const earlier = sessions.filter((s) => new Date(s.startedAt).toDateString() !== today);

  const row = (s: typeof sessions[number]) => {
    const bike = db.bikes.find((b) => b.id === s.bikeId);
    const rider = db.riders.find((r) => r.id === s.riderId);
    const fb = db.feedback.find((f) => f.sessionId === s.id);
    const markers = db.markers.filter((m) => m.sessionId === s.id).length;
    const sim = simulateSession(db, s);
    const best = Math.min(...sim.laps.map((l) => l.timeS));
    return (
      <tr key={s.id} className="click" onClick={() => nav(`session/${s.id}`)}>
        <td>{new Date(s.startedAt).toLocaleDateString()} <span className="hint">{new Date(s.startedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></td>
        <td style={{ fontWeight: 600 }}>{s.objective}</td>
        <td className="mono">{bike?.label}</td>
        <td>{rider?.name}</td>
        <td className="num">{sim.laps.length}</td>
        <td className="num">{best.toFixed(2)}s</td>
        <td>{fb ? <Pill tone="good">Feedback in</Pill> : markers ? <Pill tone="warning">{markers} markers</Pill> : <Pill tone="neutral">Complete</Pill>}</td>
      </tr>
    );
  };

  return (
    <div>
      <div className="page-title">
        <h1>Sessions</h1>
        <span className="sub">{db.focus ? `Focus: ${db.focus.text}` : ''}</span>
      </div>
      {allowed('session.create') && (
        <div className="btn-row" style={{ marginBottom: 22 }}>
          <button className="btn primary" onClick={() => nav('session/new')}>New session</button>
          <button className="btn ghost" onClick={() => nav('pit')}>Pit Mode</button>
          <button className="btn ghost" onClick={() => nav('starts')}>Start Lab</button>
        </div>
      )}

      {todays.length > 0 && (
        <Panel title="Today">
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>When</th><th>Objective</th><th>Bike</th><th>Rider</th><th>Laps</th><th>Best</th><th>State</th></tr></thead>
              <tbody>{todays.map(row)}</tbody>
            </table>
          </div>
        </Panel>
      )}

      <Panel title={todays.length ? 'Earlier' : 'History'}>
        {earlier.length === 0 && todays.length === 0 ? (
          <EmptyState title="No sessions yet">Start the first test session when the bike is ready.</EmptyState>
        ) : (
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>When</th><th>Objective</th><th>Bike</th><th>Rider</th><th>Laps</th><th>Best</th><th>State</th></tr></thead>
              <tbody>{earlier.map(row)}</tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
