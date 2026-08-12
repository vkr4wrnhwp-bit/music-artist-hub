import React, { useState } from 'react';
import { buildChecklist, computeReadiness, simulateSession } from '@mxlab/domain';
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

  const checklist = buildChecklist(db, bike);
  const allOk = checklist.ready && readiness.readyForInstrumentedTest;

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
          <p className="eyebrow" style={{ marginTop: 36 }}>{allOk ? 'Ready to race' : 'Not ready'}</p>
          <h1 className="mono">{bike.label}</h1>
          <p className="pit-sub">
            {rev ? `Map ${rev.rev} · Slot ${bike.currentMapSlot}` : 'No map loaded'} · <Pill tone="sim">SIMULATED</Pill>
          </p>
          <div className="pit-checks">
            {checklist.items.filter((i) => i.status !== 'manual').map((i) => (
              <div key={i.id} className={`pit-check ${i.status === 'pass' ? 'ok' : 'bad'}`}>
                <span>{i.label}</span>
                <span className="st" aria-label={i.status === 'pass' ? 'ready' : 'blocked'}>{i.status === 'pass' ? '✓' : '✕'}</span>
              </div>
            ))}
            {checklist.items.filter((i) => i.status === 'manual').map((i) => (
              <ManualCheck key={i.id} id={`${bike.id}-${i.id}`} label={i.label} detail={i.detail} />
            ))}
          </div>
          {checklist.blockers.length > 0 && (
            <p style={{ color: 'var(--critical)', fontWeight: 650, fontSize: 15 }}>
              {checklist.blockers[0]}
            </p>
          )}
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

/** Glove-friendly manual checklist item — physical checks stay human. */
function ManualCheck({ id, label, detail }: { id: string; label: string; detail: string }) {
  const [done, setDone] = useState(() => sessionStorage.getItem(`pitcheck-${id}`) === '1');
  return (
    <button
      className={`pit-check ${done ? 'ok' : ''}`}
      style={{ width: '100%', textAlign: 'left', cursor: 'pointer', opacity: done ? 1 : 0.85 }}
      title={detail}
      onClick={() => {
        const next = !done;
        setDone(next);
        sessionStorage.setItem(`pitcheck-${id}`, next ? '1' : '0');
      }}
    >
      <span>{label}</span>
      <span className="st" style={{ color: done ? 'var(--good)' : 'var(--muted)' }}>{done ? '✓' : '○'}</span>
    </button>
  );
}
