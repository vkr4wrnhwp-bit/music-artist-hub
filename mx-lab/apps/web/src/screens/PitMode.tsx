import React, { useState } from 'react';
import { computeReadiness, simulateSession } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Pill } from '../ui';

/**
 * PIT MODE — tablet-first, glove-friendly, offline (the whole app is local).
 * Two states: before riding (readiness checklist + one action) and when the
 * bike returns (session received + one action). Minimal chrome.
 */
export function PitMode() {
  const { db, user } = useApp();
  const [bikeId, setBikeId] = useState(db.focus?.bikeId ?? db.bikes[0]?.id ?? '');
  const bike = db.bikes.find((b) => b.id === bikeId);
  if (!bike || !user) return null;

  const readiness = computeReadiness(db, bike);
  const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);
  const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
  const lastSession = [...db.sessions]
    .filter((s) => s.bikeId === bike.id && s.status === 'complete')
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
  const lastSim = lastSession ? simulateSession(db, lastSession) : null;
  const markers = lastSession ? db.markers.filter((m) => m.sessionId === lastSession.id) : [];
  const feedback = lastSession ? db.feedback.find((f) => f.sessionId === lastSession.id) : null;
  const sensorIssues = device
    ? Object.values(device.channelHealth).filter((q) => q === 'Missing' || q === 'Intermittent' || q === 'Out of range').length
    : 1;

  const gate = (id: string) => readiness.gates.find((g) => g.id === id);
  const checks: Array<[string, boolean, string]> = [
    [`Map ${rev?.rev ?? '—'}`, !!gate('transfer')?.pass && !!gate('mapApproved')?.pass, 'map'],
    ['Fuel', !!gate('fuel')?.pass, 'fuel'],
    ['Maintenance', !!gate('maintenance')?.pass, 'mnt'],
    ['Logger', !!gate('hardware')?.pass, 'log'],
    ['Sensors', sensorIssues === 0, 'sns'],
  ];
  const allOk = readiness.readyForInstrumentedTest;

  // one hour = "fresh" — the bike just came back and feedback is pending
  const sessionFresh = lastSession
    && !feedback
    && (Date.now() - new Date(lastSession.startedAt).getTime()) < 6 * 3600 * 1000;

  return (
    <div className="pit">
      <div className="btn-row" style={{ justifyContent: 'center' }}>
        {db.bikes.filter((b) => !b.retired).map((b) => (
          <button key={b.id} className={`btn ${b.id === bikeId ? 'primary' : ''}`} onClick={() => setBikeId(b.id)}>
            {b.label}
          </button>
        ))}
      </div>

      {sessionFresh && lastSession ? (
        <>
          <p className="eyebrow" style={{ marginTop: 36 }}>Session received</p>
          <h1>{lastSession.objective}</h1>
          <div style={{ display: 'flex', gap: 48, justifyContent: 'center', margin: '28px 0 8px', flexWrap: 'wrap' }}>
            <div className="pit-stat">{lastSim?.laps.length ?? 0}<small>laps</small></div>
            <div className="pit-stat">{markers.length}<small>rider markers</small></div>
            <div className="pit-stat" style={{ color: 'var(--good)' }}>GOOD<small>data quality (SIM)</small></div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center', marginTop: 26 }}>
            <button className="btn primary big" onClick={() => nav(`session/${lastSession.id}/feedback`)}>Get Rider Feedback</button>
            <button className="btn big" onClick={() => nav(`session/${lastSession.id}`)}>Analyze</button>
          </div>
        </>
      ) : (
        <>
          <p className="eyebrow" style={{ marginTop: 36 }}>{allOk ? 'Bike ready' : 'Not ready'}</p>
          <h1 className="mono">{bike.label}</h1>
          <p className="pit-sub">
            {rev ? `Map ${rev.rev} · Slot ${bike.currentMapSlot}` : 'No map loaded'} · <Pill tone="sim">SIMULATED</Pill>
          </p>
          <div className="pit-checks">
            {checks.map(([label, ok, key]) => (
              <div key={key} className={`pit-check ${ok ? 'ok' : 'bad'}`}>
                <span>{label}</span>
                <span className="st" aria-label={ok ? 'ready' : 'blocked'}>{ok ? '✓' : '✕'}</span>
              </div>
            ))}
          </div>
          {allOk ? (
            <button className="btn primary big" onClick={() => nav('session/new')}>Start Session</button>
          ) : (
            <button className="btn big" onClick={() => nav(`bike/${bike.id}`)}>Resolve in Bike Profile →</button>
          )}
        </>
      )}
      <p className="hint" style={{ marginTop: 28 }}>Pit Mode works fully offline — everything is on this device.</p>
    </div>
  );
}
