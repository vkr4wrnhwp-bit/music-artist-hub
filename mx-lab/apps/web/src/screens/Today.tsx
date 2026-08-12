import React from 'react';
import { appendAudit, computeReadiness, simulateSession } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Pill, readinessTone, TraceIcon } from '../ui';

/**
 * Garage / Today — the landing screen. Answers exactly four questions:
 * which bike, what are we doing, is anything blocking us, what's next.
 * One dominant primary action. Everything else is one layer deeper.
 */
export function Today() {
  const { db, user, update, allowed } = useApp();
  if (!user) return null;

  // active bike: the focus bike, else the signed-in rider's bike, else first ready
  const rider = db.riders.find((r) => r.userId === user.id);
  const bike =
    db.bikes.find((b) => b.id === db.focus?.bikeId && !b.retired)
    ?? db.bikes.find((b) => b.assignedRiderId === rider?.id && !b.retired)
    ?? db.bikes.find((b) => !b.retired);
  if (!bike) {
    return (
      <div className="empty">
        <h4>No bikes yet</h4>
        <p><a href="#/bike/new">Register the first bike</a> to open its Phase 0 inventory.</p>
      </div>
    );
  }

  const model = db.bikeModels.find((m) => m.id === bike.bikeModelId);
  const assignedRider = db.riders.find((r) => r.id === bike.assignedRiderId);
  const readiness = computeReadiness(db, bike);
  const rev = db.mapRevisions.find((r) => r.id === bike.currentMapRevisionId);
  const map = db.maps.find((m) => m.id === rev?.mapId);
  const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
  const blocking = readiness.gates.filter((g) => g.critical && !g.pass);

  const lastSession = [...db.sessions]
    .filter((s) => s.bikeId === bike.id && s.status === 'complete')
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];
  const lastSim = lastSession ? simulateSession(db, lastSession) : null;
  const lastBest = lastSim ? Math.min(...lastSim.laps.map((l) => l.timeS)) : null;

  const openInsight = db.recommendations.find((r) => r.status === 'AWAITING_TUNER_REVIEW');
  const sensorIssues = device
    ? Object.entries(device.channelHealth).filter(([, q]) => q === 'Missing' || q === 'Intermittent' || q === 'Out of range')
    : [];

  const canEditFocus = allowed('session.create');
  const focusText = db.focus?.bikeId === bike.id ? db.focus?.text : undefined;

  return (
    <div>
      {/* ---- active bike hero ---- */}
      <section className="hero" aria-label="Active bike">
        <span className="watermark"><TraceIcon size={260} /></span>
        <p className="eyebrow">Active bike</p>
        <h1 className="mono">{bike.label}</h1>
        <p className="hero-sub">
          {model ? `${model.modelYear} ${model.manufacturer} ${model.model}` : ''}
          {assignedRider ? ` · ${assignedRider.name}` : ''}
        </p>
        <div className="hero-row">
          <span className="hero-kv">Status<b><Pill tone={readinessTone(readiness.status)}>{readiness.status}</Pill></b></span>
          <span className="hero-kv">Map<b className="mono">{rev ? `${map?.name}-${rev.rev} · Slot ${bike.currentMapSlot}` : 'None'}</b></span>
          <span className="hero-kv">Engine<b className="mono">{bike.hoursSinceRebuild.toFixed(1)} h since rebuild</b></span>
          {device && <span className="hero-kv">Logger<b>{sensorIssues.length ? `${sensorIssues.length} sensor fault` : 'Healthy'} · SIM</b></span>}
        </div>
        <div className="btn-row" style={{ marginTop: 24 }}>
          {readiness.readyForInstrumentedTest ? (
            <button className="btn primary big" onClick={() => nav('session/new')}>Start Session</button>
          ) : (
            <button className="btn big" onClick={() => nav(`bike/${bike.id}`)}>Resolve readiness →</button>
          )}
          <button className="btn ghost" onClick={() => nav(`bike/${bike.id}`)}>Bike profile</button>
          <button className="btn ghost" onClick={() => nav('fleet')}>All bikes</button>
        </div>
      </section>

      {/* ---- TRACE Focus ---- */}
      <section className="focus" aria-label="TRACE Focus">
        <p className="eyebrow" style={{ color: 'var(--accent)' }}>Today's focus</p>
        <p className="focus-text">{focusText ?? 'No test objective set for this bike yet.'}</p>
        {canEditFocus && (
          <div className="btn-row" style={{ marginTop: 10 }}>
            <button className="btn small ghost" onClick={() => {
              const t = prompt('TRACE Focus — one objective for today:', focusText ?? '');
              if (t === null) return;
              update((d) => {
                d.focus = { bikeId: bike.id, text: t.trim() || 'No test objective set.', setByUserId: user.id };
                appendAudit(d, user.id, 'focus.set', 'Bike', bike.id, `TRACE Focus: ${t.trim()}`);
              });
            }}>{focusText ? 'Edit focus' : 'Set focus'}</button>
          </div>
        )}
      </section>
      <Help id="focus">
        One session, one objective. TRACE biases session setup and post-session analysis toward
        answering the focus — that's what turns random testing into a disciplined experiment loop.
      </Help>

      {/* ---- exactly a few secondary items ---- */}
      <div className="cols-3">
        {lastSession && (
          <section className="panel" aria-label="Last session">
            <h3>Last session</h3>
            <div className="panel-b">
              <p style={{ margin: 0, fontWeight: 650 }}>{lastSession.objective}</p>
              <p className="hint" style={{ marginTop: 2 }}>
                {new Date(lastSession.startedAt).toLocaleDateString()} · {lastSession.lapCount} laps
                {lastBest ? ` · best ${lastBest.toFixed(2)}s` : ''}
              </p>
              <div className="btn-row" style={{ marginTop: 12 }}>
                <button className="btn small" onClick={() => nav(`session/${lastSession.id}`)}>Open</button>
              </div>
            </div>
          </section>
        )}

        {openInsight && (
          <section className="insight" aria-label="TRACE insight" style={{ marginBottom: 20 }}>
            <p className="eyebrow">TRACE found something</p>
            <h4>{openInsight.observedEvent}</h4>
            <p>{openInsight.likelyCause.category} — {openInsight.confidencePct}% confidence</p>
            <div className="btn-row" style={{ marginTop: 10 }}>
              <button className="btn small primary" onClick={() => nav(`engineer/${openInsight.id}`)}>Review</button>
            </div>
          </section>
        )}

        {(blocking.length > 0 || bike.maintenanceStatus !== 'Current') && (
          <section className="panel" aria-label="Attention">
            <h3>Needs attention</h3>
            <div className="panel-b">
              {blocking.slice(0, 2).map((g) => (
                <p key={g.id} style={{ margin: '0 0 6px' }}>
                  <Pill tone="critical">{g.label}</Pill>
                  <span className="hint" style={{ display: 'block', marginTop: 3 }}>{g.detail}</span>
                </p>
              ))}
              {bike.maintenanceStatus !== 'Current' && (
                <p style={{ margin: 0 }}>
                  <Pill tone={bike.maintenanceStatus === 'Due Soon' ? 'warning' : 'critical'}>Maintenance {bike.maintenanceStatus}</Pill>
                </p>
              )}
              <div className="btn-row" style={{ marginTop: 12 }}>
                <button className="btn small" onClick={() => nav(`bike/${bike.id}`)}>Open readiness</button>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
