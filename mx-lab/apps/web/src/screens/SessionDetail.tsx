import React, { useMemo, useState } from 'react';
import {
  appendAudit, buildImportedTrace, buildRecommendation, compareSessions,
  parseTelemetryCsv, pathPoint, simulateSession,
  telemetrySupportsPreference, transitionRevision, whatChanged, type EventMarker,
  type MarkerCategory, type RiderFeedback, type Session,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { fmtSigned, Help, LineChart, Panel, Pill, Prov, themeHeat, useThemeVersion } from '../ui';

const MARKER_CATEGORIES: MarkerCategory[] = [
  'Bog', 'Abrupt hit', 'Too soft', 'Wheelspin', 'Loss of drive', 'Flat top-end',
  'Excessive engine braking', 'Insufficient engine braking', 'Hard starting',
  'Inconsistent launch', 'Overheating', 'Popping on deceleration', 'Throttle-response delay',
  'Harsh landing response', 'Missed shift', 'Clutch issue', 'Suspension issue', 'Other',
];

type SessionTab = 'summary' | 'telemetry' | 'track' | 'markers' | 'feedback' | 'compare';

export function SessionDetail({ sessionId, initialTab }: { sessionId: string; initialTab?: string }) {
  const { db, user } = useApp();
  const valid: SessionTab[] = ['summary', 'telemetry', 'track', 'markers', 'feedback', 'compare'];
  const [tab, setTab] = useState<SessionTab>(
    valid.includes(initialTab as SessionTab) ? (initialTab as SessionTab) : 'summary',
  );
  const session = db.sessions.find((s) => s.id === sessionId);
  if (!session || !user) return <p>Session not found.</p>;

  const bike = db.bikes.find((b) => b.id === session.bikeId)!;
  const rider = db.riders.find((r) => r.id === session.riderId)!;
  const track = db.tracks.find((t) => t.id === session.trackId)!;
  const rev = db.mapRevisions.find((r) => r.id === session.setupSnapshot.mapRevisionId);
  const map = db.maps.find((m) => m.id === rev?.mapId);
  const markers = db.markers.filter((m) => m.sessionId === session.id);

  return (
    <div>
      <div className="page-title">
        <h1>{session.objective}</h1>
        <span className="sub mono">{bike.label} · {rider.name} · {new Date(session.startedAt).toLocaleDateString()}</span>
        <Pill tone="sim">SIMULATED</Pill>
      </div>
      <p className="hint" style={{ marginTop: -12, marginBottom: 16 }}>
        {track.name} · map <a href={`#/maps/${rev?.id}`}>{map?.name}-{rev?.rev}</a> slot {session.setupSnapshot.mapSlot} ·
        {' '}{session.weather.ambientC}°C · {session.trackCondition.surfaceType}, {session.trackCondition.moisture}
      </p>
      <div className="btn-row no-print" style={{ marginBottom: 18 }}>
        {([['summary', 'Summary'], ['feedback', 'Rider feedback'], ['markers', `Markers (${markers.length})`], ['track', 'Track view'], ['telemetry', 'Data'], ['compare', 'A/B compare']] as const).map(([id, label]) => (
          <button key={id} className={`btn small ${tab === id ? 'primary' : ''}`} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'summary' && <SummaryTab session={session} goTo={setTab} />}
      {tab === 'telemetry' && <TelemetryTab session={session} />}
      {tab === 'track' && <TrackTab session={session} />}
      {tab === 'markers' && <MarkersTab session={session} />}
      {tab === 'feedback' && <FeedbackTab session={session} />}
      {tab === 'compare' && <CompareTab session={session} />}
    </div>
  );
}

/** Summary — what came back, what to do next. One primary action. */
function SummaryTab({ session, goTo }: { session: Session; goTo: (t: SessionTab) => void }) {
  const { db } = useApp();
  const sim = simulateSession(db, session);
  const markers = db.markers.filter((m) => m.sessionId === session.id);
  const feedback = db.feedback.find((f) => f.sessionId === session.id);
  const rec = db.recommendations.find((r) => r.sessionId === session.id);
  const ab = db.abTests.find((t) => (t.sessionAId === session.id || t.sessionBId === session.id) && t.outcome);
  const best = Math.min(...sim.laps.map((l) => l.timeS));
  const anomalies = markers.filter((m) => m.category !== 'Unreviewed').length;

  const next = !feedback
    ? { label: 'Get Rider Feedback', go: () => goTo('feedback') }
    : { label: 'Analyze', go: () => goTo('compare') };

  return (
    <div>
      <section className="hero" style={{ padding: '24px 28px' }}>
        <p className="eyebrow">Session received</p>
        <div style={{ display: 'flex', gap: 44, flexWrap: 'wrap', margin: '10px 0 4px' }}>
          <span className="pit-stat" style={{ fontSize: 34 }}>{sim.laps.length}<small>laps</small></span>
          <span className="pit-stat" style={{ fontSize: 34 }}>{best.toFixed(2)}s<small>best lap</small></span>
          <span className="pit-stat" style={{ fontSize: 34 }}>{markers.length}<small>rider markers</small></span>
          <span className="pit-stat" style={{ fontSize: 34, color: anomalies ? 'var(--warning)' : 'var(--good)' }}>
            {anomalies}<small>{anomalies === 1 ? 'anomaly' : 'anomalies'}</small>
          </span>
        </div>
        <div className="btn-row" style={{ marginTop: 18 }}>
          <button className="btn primary big" onClick={next.go}>{next.label}</button>
          {feedback && <button className="btn ghost" onClick={() => goTo('track')}>Track view</button>}
        </div>
      </section>

      {ab && (
        <section className="focus">
          <p className="eyebrow" style={{ color: 'var(--accent)' }}>Result</p>
          <p className="focus-text" style={{ fontSize: 16.5 }}>{ab.conclusion}</p>
        </section>
      )}
      {rec && (
        <section className="insight">
          <p className="eyebrow">TRACE found something</p>
          <h4>{rec.observedEvent}</h4>
          <p>{rec.likelyCause.category} — {rec.confidencePct}% confidence · {rec.status.replaceAll('_', ' ').toLowerCase()}</p>
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn small primary" onClick={() => nav(`engineer/${rec.id}`)}>Review</button>
          </div>
        </section>
      )}
      {feedback && (
        <p className="hint">
          Rider verdict: {feedback.answers.betterOrWorse}
          {feedback.preferredOverPrevious ? ' — preferred over previous setup' : ''} · full detail in Rider feedback.
        </p>
      )}

      <WhatChangedPanel session={session} />
    </div>
  );
}

/** WHAT CHANGED? — automatic diff vs the previous session on this bike. */
function WhatChangedPanel({ session }: { session: Session }) {
  const { db } = useApp();
  const res = whatChanged(db, session);
  if (!res.baseline) return null;
  const changed = res.vars.filter((v) => v.changed);
  return (
    <Panel title={`What changed? — vs ${new Date(res.baseline.startedAt).toLocaleDateString()} (${res.baseline.objective.slice(0, 40)})`}>
      {res.warnings.map((w, i) => (
        <p key={i} style={{ color: 'var(--warning)', fontWeight: 650, fontSize: 13, marginTop: 0 }}>⚠ {w}</p>
      ))}
      {changed.length === 0 ? (
        <p className="hint" style={{ margin: 0 }}>No configuration changes vs the previous session — a clean back-to-back.</p>
      ) : (
        <div className="tbl-scroll">
          <table className="data">
            <tbody>
              {changed.map((v) => (
                <tr key={v.field}>
                  <td style={{ width: 170, color: 'var(--muted)', fontSize: 11, fontWeight: 750, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{v.label}</td>
                  <td className="mono">{v.a} → <b>{v.b}</b></td>
                  <td>
                    {v.intended && <Pill tone="good">Intended</Pill>}
                    {v.shouldHoldConstant && <Pill tone="critical">Should have held constant</Pill>}
                    {!v.intended && !v.shouldHoldConstant && (['weather', 'trackCond', 'hours'].includes(v.field)
                      ? <Pill tone="neutral">Environment</Pill> : <Pill tone="warning">Unconfirmed</Pill>)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="btn-row" style={{ marginTop: 10 }}>
        <button className="btn small" onClick={() => nav(`compare/${res.baseline!.id}/${session.id}`)}>Open in TRACE Compare</button>
      </div>
    </Panel>
  );
}

// ------------------------------------------------------------- telemetry

function TelemetryTab({ session }: { session: Session }) {
  const { db, user, update, allowed } = useApp();
  useThemeVersion();
  const [importMsg, setImportMsg] = useState('');
  const imported = db.importedTraces?.[session.id];
  const canImport = allowed('telemetry.configure');
  const sim = simulateSession(db, session);
  const markers = db.markers.filter((m) => m.sessionId === session.id);
  const [chans, setChans] = useState<string[]>(['rpm', 'tps', 'slip']);
  const all = [
    ['rpm', 'RPM', 'rpm'], ['tps', 'Throttle', '%'], ['speed', 'Speed', 'kph'],
    ['slip', 'Rear slip est.', '%'], ['accel', 'Long. accel', 'g'], ['coolant', 'Coolant', '°C'],
    ['iat', 'IAT', '°C'], ['battv', 'Battery', 'V'], ['clutch', 'Clutch', '%'],
    ['fork', 'Fork travel', 'mm'], ['shock', 'Shock travel', 'mm'],
  ] as const;
  const device = db.devices.find((d) => d.id === session.hardwareCheck.deviceId);

  return (
    <div>
      <Panel
        title="Data source"
        actions={imported
          ? <Pill tone="good">IMPORTED — MEASURED DATA</Pill>
          : <Pill tone="sim">SIMULATION</Pill>}
      >
        {imported ? (
          <>
            <p style={{ margin: 0, fontSize: 13.5 }}>
              <span className="mono">{imported.sourceName}</span> · {imported.samples.toLocaleString()} samples
              at {imported.hz} Hz · channels: {imported.channelNames.join(', ')} · {imported.laps.length} lap
              {imported.laps.length === 1 ? ' span' : 's'}
            </p>
            <p className="hint" style={{ margin: '4px 0 8px' }}>
              Imported {new Date(imported.importedAt).toLocaleString()} by{' '}
              {db.users.find((u) => u.id === imported.byUserId)?.name ?? imported.byUserId}. Channels the
              file did not carry stay flat at zero — nothing is invented. All analysis on this session
              runs on the measured trace.
            </p>
            {canImport && (
              <button className="btn small danger" onClick={() => update((d) => {
                delete d.importedTraces[session.id];
                appendAudit(d, user!.id, 'telemetry.importRemove', 'Session', session.id,
                  'Imported telemetry removed — session reverts to the labeled simulation.');
              })}>Remove imported data (revert to simulation)</button>
            )}
          </>
        ) : (
          <>
            <p className="hint" style={{ marginTop: 0 }}>
              This session's trace is the labeled simulation. Import a logger CSV to replace it with
              measured data — accepted columns include time, rpm, throttle/tps, speed (kph or mph),
              gear, coolant, iat, voltage, clutch, and an optional lap column.
            </p>
            {canImport ? (
              <label className="btn small" style={{ display: 'inline-block', cursor: 'pointer' }}>
                Import telemetry CSV
                <input
                  type="file" accept=".csv,text/csv" style={{ display: 'none' }}
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    e.target.value = '';
                    if (!file) return;
                    try {
                      const parsed = parseTelemetryCsv(await file.text());
                      update((d) => {
                        d.importedTraces[session.id] = buildImportedTrace(
                          parsed, file.name, user!.id, new Date().toISOString(),
                        );
                        appendAudit(d, user!.id, 'telemetry.import', 'Session', session.id,
                          `Measured telemetry imported from ${file.name}: ${parsed.samples} samples, `
                          + `channels ${parsed.channelNames.join('/')}.`);
                      });
                      setImportMsg(parsed.warnings.length ? `Imported. ${parsed.warnings.join(' ')}` : 'Imported.');
                    } catch (err) {
                      setImportMsg(`Import failed: ${(err as Error).message}`);
                    }
                  }}
                />
              </label>
            ) : <p className="hint">A data engineer or org admin imports measured telemetry.</p>}
            {importMsg && <p className="hint" style={{ marginTop: 8 }}>{importMsg}</p>}
          </>
        )}
      </Panel>
      <Panel title="Channels">
        <div className="btn-row">
          {all.map(([id, label]) => {
            const q = device?.channelHealth[id];
            const dead = q === 'Missing';
            return (
              <button key={id} className={`btn small ${chans.includes(id) ? 'primary' : ''}`} disabled={dead}
                title={dead ? `${label}: channel Missing this session` : undefined}
                onClick={() => setChans(chans.includes(id) ? chans.filter((c) => c !== id) : [...chans, id])}>
                {label}{dead ? ' ✕' : ''}
              </button>
            );
          })}
        </div>
        <Help id="signal">
          Channel quality is tracked per session: a Missing or Uncalibrated channel is excluded here and
          <b> caps AI confidence</b> — bad telemetry never silently shapes a conclusion.
        </Help>
      </Panel>
      <Panel title={`Trace — ${Math.round(sim.t[sim.t.length - 1] ?? session.durationS)}s at ${sim.hz} Hz · ${imported ? 'measured (imported)' : 'simulated'} — downsampled for display`}>
        <LineChart
          t={sim.t}
          series={chans.map((c) => {
            const meta = all.find((a) => a[0] === c)!;
            return { id: c, label: meta[1], unit: meta[2], values: sim.channels[c] };
          })}
          markers={markers.map((m, i) => ({ tS: m.tS, label: `${i + 1}` }))}
          height={220}
        />
        <p className="hint">Series are auto-scaled per channel to share one plot; hover for exact values. ▲ marks rider events.</p>
      </Panel>
      <Panel title="Laps">
        <div className="tbl-scroll">
          <table className="data">
            <thead><tr><th>Lap</th><th>Time</th><th>vs best</th></tr></thead>
            <tbody>
              {sim.laps.map((l) => {
                const best = Math.min(...sim.laps.map((x) => x.timeS));
                return (
                  <tr key={l.n}>
                    <td className="num">{l.n}</td>
                    <td className="num">{l.timeS.toFixed(2)}s</td>
                    <td className="num">{l.timeS === best ? 'best' : `+${(l.timeS - best).toFixed(2)}`}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------- track view

function TrackTab({ session }: { session: Session }) {
  const { db } = useApp();
  useThemeVersion();
  const th = themeHeat();
  const track = db.tracks.find((t) => t.id === session.trackId)!;
  const sim = simulateSession(db, session);
  const markers = db.markers.filter((m) => m.sessionId === session.id);
  const [segId, setSegId] = useState(track.segments[0]?.id ?? '');
  const [otherId, setOtherId] = useState('');
  const seg = track.segments.find((s) => s.id === segId);
  const others = db.sessions.filter((s) => s.trackId === track.id && s.id !== session.id);
  const other = db.sessions.find((s) => s.id === otherId);

  const sectionStats = (s: Session, f0: number, f1: number) => {
    const d = simulateSession(db, s);
    const speeds: number[] = [];
    const slips: number[] = [];
    let reopenTps = 0;
    let n = 0;
    for (let i = 0; i < d.t.length; i++) {
      const f = d.channels.frac[i];
      if (f >= f0 && f < f1) {
        speeds.push(d.channels.speed[i]);
        slips.push(d.channels.slip[i]);
        if (i > 0 && d.channels.tps[i - 1] < 20 && d.channels.tps[i] >= 20) { reopenTps += d.channels.rpm[i]; n++; }
      }
    }
    const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(1, xs.length);
    return {
      avgSpeed: +mean(speeds).toFixed(1),
      minSpeed: speeds.length ? +Math.min(...speeds).toFixed(1) : 0,
      peakSlip: slips.length ? +Math.max(...slips).toFixed(1) : 0,
      reopenRpm: n ? Math.round(reopenTps / n) : 0,
    };
  };

  const W = 560;
  const H = 400;
  const px = (p: [number, number]) => [40 + p[0] * (W - 80), 30 + p[1] * (H - 60)] as [number, number];
  const d = `M ${track.path.map((p) => px(p).map((v) => v.toFixed(1)).join(' ')).join(' L ')}`;
  const mine = seg ? sectionStats(session, seg.startFrac, seg.endFrac) : null;
  const theirs = seg && other ? sectionStats(other, seg.startFrac, seg.endFrac) : null;
  const myRev = db.mapRevisions.find((r) => r.id === session.setupSnapshot.mapRevisionId);
  const otherRev = other ? db.mapRevisions.find((r) => r.id === other.setupSnapshot.mapRevisionId) : null;

  return (
    <div className="cols">
      <Panel title={`${track.name} — ${track.direction}, ${track.surface}`}>
        <div className="chart-box">
          <svg viewBox={`0 0 ${W} ${H}`} className="track-svg" role="img" aria-label="Track layout with event markers">
            <path className="line" d={d} />
            <path className="mid" d={d} />
            {seg && (() => {
              const pts: string[] = [];
              for (let f = seg.startFrac; f <= seg.endFrac; f += 0.005) pts.push(px(pathPoint(track, f)).map((v) => v.toFixed(1)).join(' '));
              return <path d={`M ${pts.join(' L ')}`} fill="none" stroke={th.accent} strokeWidth={14} strokeOpacity={0.55} strokeLinecap="round" />;
            })()}
            {markers.map((m, i) => {
              const [x, y] = px(pathPoint(track, m.trackFrac));
              return (
                <g key={m.id}>
                  <circle cx={x} cy={y} r={9} fill={th.neg} />
                  <text x={x} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={800} fill="#fff">{i + 1}</text>
                </g>
              );
            })}
            {(() => { const [x, y] = px(pathPoint(track, 0)); return <text x={x} y={y - 12} fontSize={10} fill={th.muted} textAnchor="middle">START</text>; })()}
          </svg>
        </div>
        <div className="btn-row" style={{ marginTop: 8 }}>
          {track.segments.map((s) => (
            <button key={s.id} className={`btn small ${segId === s.id ? 'primary' : ''}`} onClick={() => setSegId(s.id)}>{s.name}</button>
          ))}
        </div>
      </Panel>
      <Panel title={`Section analysis — ${seg?.name ?? ''}`}>
        <div className="field">
          <label>Compare against session</label>
          <select value={otherId} onChange={(e) => setOtherId(e.target.value)}>
            <option value="">— none —</option>
            {others.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective}</option>)}
          </select>
        </div>
        {mine && (
          <div className="tbl-scroll">
            <table className="data">
              <thead>
                <tr><th>Metric</th><th>This ({myRev?.rev})</th>{theirs && <th>Other ({otherRev?.rev})</th>}</tr>
              </thead>
              <tbody>
                <tr><td>Average speed</td><td className="num">{mine.avgSpeed} kph</td>{theirs && <td className="num">{theirs.avgSpeed} kph</td>}</tr>
                <tr><td>Minimum speed</td><td className="num">{mine.minSpeed} kph</td>{theirs && <td className="num">{theirs.minSpeed} kph</td>}</tr>
                <tr><td>Peak slip estimate</td><td className="num">{mine.peakSlip}%</td>{theirs && <td className="num">{theirs.peakSlip}%</td>}</tr>
                <tr><td>RPM at reopen</td><td className="num">{mine.reopenRpm || '—'}</td>{theirs && <td className="num">{theirs.reopenRpm || '—'}</td>}</tr>
              </tbody>
            </table>
          </div>
        )}
        <Help id="trackview">
          Pick a section, then compare repeated passes across two sessions — this is how a map change is
          judged <b>where the rider felt it</b>, not on averages that wash it out.
        </Help>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------- markers

function MarkersTab({ session }: { session: Session }) {
  const { db, user, update, allowed } = useApp();
  const markers = db.markers.filter((m) => m.sessionId === session.id);
  const track = db.tracks.find((t) => t.id === session.trackId)!;
  const sim = simulateSession(db, session);
  const [newLap, setNewLap] = useState(2);
  const [newSeg, setNewSeg] = useState(track.segments[0]?.id ?? '');
  const isRider = user?.role === 'rider';

  return (
    <div>
      <Panel title="Rider event markers">
        <Help id="markers">
          On the bike this is the physical <b>MARK button</b> — one press, one timestamped event with the
          full telemetry window around it. Review happens back in the pits: “What happened at Marker 3?”
        </Help>
        {markers.length === 0 && <p className="hint">No markers in this session.</p>}
        {markers.map((m, i) => <MarkerCard key={m.id} m={m} i={i} session={session} />)}
        {allowed('feedback.submit') && (
          <div className="btn-row" style={{ marginTop: 10 }}>
            <span style={{ fontSize: 13 }}>Add marker (simulated MARK press):</span>
            <select value={newLap} onChange={(e) => setNewLap(parseInt(e.target.value, 10))}>
              {sim.laps.map((l) => <option key={l.n} value={l.n}>Lap {l.n}</option>)}
            </select>
            <select value={newSeg} onChange={(e) => setNewSeg(e.target.value)}>
              {track.segments.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <button className="btn small" onClick={() => {
              update((d) => {
                const lap = sim.laps.find((l) => l.n === newLap)!;
                const seg = track.segments.find((s) => s.id === newSeg)!;
                const frac = (seg.startFrac + seg.endFrac) / 2;
                d.markers.push({
                  id: `mark-${Date.now()}`, sessionId: session.id,
                  tS: +(lap.startS + frac * (lap.endS - lap.startS)).toFixed(1),
                  lap: newLap, trackFrac: frac, segmentId: seg.id,
                  category: 'Unreviewed', provenance: 'RIDER REPORTED',
                });
                appendAudit(d, user!.id, 'marker.create', 'Session', session.id, `Marker added at ${seg.name}, lap ${newLap}.`);
              });
            }}>+ MARK</button>
          </div>
        )}
      </Panel>
    </div>
  );
}

function MarkerCard({ m, i, session }: { m: EventMarker; i: number; session: Session }) {
  const { db, user, update, allowed } = useApp();
  const track = db.tracks.find((t) => t.id === session.trackId)!;
  const seg = track.segments.find((s) => s.id === m.segmentId);
  const sim = simulateSession(db, session);
  const idx = Math.min(Math.floor(m.tS * sim.hz), sim.t.length - 1);
  const [editing, setEditing] = useState(m.category === 'Unreviewed');
  const [cat, setCat] = useState<MarkerCategory>(m.category === 'Unreviewed' ? 'Abrupt hit' : m.category);
  const [note, setNote] = useState(m.note ?? '');
  const [conf, setConf] = useState(m.confidence ?? 3);
  const [sev, setSev] = useState(m.severity ?? 3);
  const [rep, setRep] = useState(m.repeatability ?? 3);
  const canReview = allowed('marker.review') || allowed('feedback.submit');
  const existingRec = db.recommendations.find((r) => r.markerId === m.id);

  return (
    <div style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px', marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <b>Marker {i + 1}</b>
        <span className="mono hint">lap {m.lap} · t={m.tS}s · {seg?.name ?? `${(m.trackFrac * 100).toFixed(0)}%`}</span>
        <Pill tone={m.category === 'Unreviewed' ? 'warning' : 'neutral'}>{m.category}</Pill>
        <Prov p={m.provenance} />
      </div>
      <p className="hint mono" style={{ margin: '6px 0' }}>
        At marker: {sim.channels.rpm[idx]} rpm · {sim.channels.tps[idx]}% throttle · {sim.channels.speed[idx]} kph ·
        gear {sim.channels.gear[idx]} · slip {sim.channels.slip[idx]}% · {sim.channels.coolant[idx]}°C
      </p>
      {m.note && !editing && <p style={{ margin: '4px 0', fontSize: 13.5 }}>“{m.note}” <span className="hint">confidence {m.confidence}/5 · severity {m.severity}/5 · repeatability {m.repeatability}/5</span></p>}
      {editing && canReview ? (
        <div>
          <p style={{ fontWeight: 600, fontSize: 13.5, margin: '8px 0 6px' }}>What happened at Marker {i + 1}?</p>
          <div className="btn-row" style={{ marginBottom: 8 }}>
            {MARKER_CATEGORIES.map((c) => (
              <button key={c} className={`btn small ${cat === c ? 'primary' : ''}`} onClick={() => setCat(c)}>{c}</button>
            ))}
          </div>
          <div className="field"><label>Notes (voice notes arrive here in Phase 2)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. hits hard after the rut, spins, then hooks up" />
          </div>
          <div className="grid3">
            {([['Confidence', conf, setConf], ['Severity', sev, setSev], ['Repeatability', rep, setRep]] as const).map(([label, v, set]) => (
              <div className="field" key={label}>
                <label>{label}: {v}/5</label>
                <input type="range" min={1} max={5} value={v} onChange={(e) => (set as (n: number) => void)(parseInt(e.target.value, 10))} />
              </div>
            ))}
          </div>
          <button className="btn small primary" onClick={() => {
            update((d) => {
              const mk = d.markers.find((x) => x.id === m.id)!;
              mk.category = cat;
              mk.note = note;
              mk.confidence = conf;
              mk.severity = sev;
              mk.repeatability = rep;
            });
            setEditing(false);
          }}>Save review</button>
        </div>
      ) : (
        <div className="btn-row" style={{ marginTop: 4 }}>
          {canReview && <button className="btn small" onClick={() => setEditing(true)}>Review…</button>}
          {existingRec ? (
            <a href="#/engineer" style={{ fontSize: 13 }}>AI analysis exists → Race Engineer</a>
          ) : (
            allowed('ai.review') && m.category !== 'Unreviewed' && (
              <button className="btn small" onClick={() => {
                let recId = '';
                update((d) => {
                  const rec = buildRecommendation(d, session, m, m.note || m.category);
                  d.recommendations.push(rec);
                  recId = rec.id;
                  appendAudit(d, user!.id, 'ai.analyze', 'AIRecommendation', rec.id, `AI analysis requested for marker at ${seg?.name}.`);
                });
                nav(`engineer/${recId}`);
              }}>Ask AI Race Engineer</button>
            )
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------- feedback

function FeedbackTab({ session }: { session: Session }) {
  const { db, user, update, allowed } = useApp();
  const existing = db.feedback.find((f) => f.sessionId === session.id);
  const rider = db.riders.find((r) => r.id === session.riderId)!;
  const isThisRider = user && rider.userId === user.id;
  const canSubmit = allowed('feedback.submit') && !existing;

  const [answers, setAnswers] = useState({
    whatHappened: '', where: '', howOften: 'Occasional',
    betterOrWorse: 'same' as RiderFeedback['answers']['betterOrWorse'],
    confidenceEffect: '', fatigueEffect: '', startsEffect: '', compensated: '', changedOverSession: '',
  });
  const [sliders, setSliders] = useState({
    initialHit: 5, midrange: 5, topEnd: 5, throttleResponse: 5, engineBraking: 5,
    traction: 5, predictability: 5, starting: 5, fatigue: 5, confidence: 5,
  });
  const [preferred, setPreferred] = useState(false);

  if (existing) {
    return (
      <Panel title={`Rider feedback — ${rider.name}`}>
        <dl className="kv">
          {Object.entries(existing.answers).map(([k, v]) => (
            <React.Fragment key={k}><dt>{LABELS[k] ?? k}</dt><dd>{v || '—'}</dd></React.Fragment>
          ))}
        </dl>
        <div className="grid2" style={{ marginTop: 10 }}>
          {Object.entries(existing.sliders).map(([k, v]) => (
            <div key={k} style={{ fontSize: 13 }}>
              <span style={{ display: 'inline-block', width: 130 }}>{SLIDER_LABELS[k] ?? k}</span>
              <meter min={0} max={10} value={v} style={{ width: 120, verticalAlign: 'middle' }} /> <b className="mono">{v}/10</b>
            </div>
          ))}
        </div>
        {existing.preferredOverPrevious !== undefined && (
          <p style={{ marginTop: 10 }}><Pill tone={existing.preferredOverPrevious ? 'good' : 'neutral'}>
            {existing.preferredOverPrevious ? 'Rider preferred this setup over the previous one' : 'Rider did not prefer this setup'}
          </Pill></p>
        )}
        <p style={{ marginTop: 8 }}><Prov p={existing.provenance} /></p>
      </Panel>
    );
  }

  if (!canSubmit) return <Panel title="Rider feedback"><p className="hint">No feedback yet. The assigned rider ({rider.name}) submits it after the moto — sign in as a rider to try it.</p></Panel>;

  // rider-mode: four big sliders first, everything else optional
  const HERO_SLIDERS: Array<[keyof typeof sliders, string, string, string]> = [
    ['initialHit', 'Power', 'Smooth', 'Aggressive'],
    ['traction', 'Traction', 'Loose', 'Hooked up'],
    ['engineBraking', 'Engine braking', 'Low', 'High'],
    ['confidence', 'Confidence', 'Low', 'High'],
  ];

  return (
    <div style={{ maxWidth: 640 }}>
      <h2 style={{ fontSize: 26, margin: '4px 0 20px', letterSpacing: '-0.01em' }}>How did it feel?</h2>
      <Help id="feedback">
        Under two minutes, in gloves. The <b>fastest setup and the preferred setup may differ</b> —
        both answers are preserved, neither overwrites the other.
      </Help>
      {HERO_SLIDERS.map(([k, name, lo, hi]) => (
        <div className="rider-slider" key={k}>
          <div className="rs-name">{name}</div>
          <input type="range" min={0} max={10} value={sliders[k]} aria-label={name}
            onChange={(e) => setSliders({ ...sliders, [k]: parseInt(e.target.value, 10) })} />
          <div className="rs-labels"><span>{lo}</span><span>{hi}</span></div>
        </div>
      ))}

      <div className="field">
        <label>Tell TRACE where the bike felt wrong or especially good</label>
        <textarea rows={2} value={answers.whatHappened}
          placeholder="e.g. hits too hard out of the Corner 6 rut"
          onChange={(e) => setAnswers({ ...answers, whatHappened: e.target.value })} />
      </div>
      <div className="btn-row" style={{ marginBottom: 16 }}>
        <button className="btn" onClick={() => {
          const t = prompt('Voice capture arrives with MX Node hardware (Phase 2). For now, dictate with your device keyboard or type the note:');
          if (t) setAnswers({ ...answers, whatHappened: answers.whatHappened ? `${answers.whatHappened} — ${t}` : t });
        }}>🎙 Record Voice Note</button>
        <span className="hint">Stored as text in Phase 1 — labeled honestly, never faked as audio.</span>
      </div>

      <details style={{ marginBottom: 16 }}>
        <summary style={{ cursor: 'pointer', color: 'var(--ink-2)', fontWeight: 650, fontSize: 13.5 }}>
          More detail (optional)
        </summary>
        <div className="grid2" style={{ marginTop: 12 }}>
          {([['where', 'Where did it happen?'],
            ['confidenceEffect', 'Did it affect confidence?'], ['fatigueEffect', 'Did it affect fatigue?'],
            ['startsEffect', 'Did it affect starts?'], ['compensated', 'Did you compensate for it?'],
            ['changedOverSession', 'Did it change as the session went on?']] as const).map(([k, label]) => (
            <div className="field" key={k}><label>{label}</label>
              <input value={answers[k]} onChange={(e) => setAnswers({ ...answers, [k]: e.target.value })} />
            </div>
          ))}
          <div className="field"><label>How often?</label>
            <select value={answers.howOften} onChange={(e) => setAnswers({ ...answers, howOften: e.target.value })}>
              {['Once', 'Occasional', 'Most laps', 'Every lap'].map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div className="field"><label>Better or worse than previous setup?</label>
            <select value={answers.betterOrWorse} onChange={(e) => setAnswers({ ...answers, betterOrWorse: e.target.value as never })}>
              {['better', 'worse', 'same', 'n/a'].map((o) => <option key={o}>{o}</option>)}
            </select>
          </div>
          {Object.entries(sliders).filter(([k]) => !HERO_SLIDERS.some(([hk]) => hk === k)).map(([k, v]) => (
            <div className="field" key={k}>
              <label>{SLIDER_LABELS[k] ?? k}: <b className="mono">{v}/10</b></label>
              <input type="range" min={0} max={10} value={v} onChange={(e) => setSliders({ ...sliders, [k]: parseInt(e.target.value, 10) })} />
            </div>
          ))}
        </div>
      </details>

      <label style={{ display: 'flex', gap: 10, alignItems: 'center', fontSize: 14.5, margin: '4px 0 16px' }}>
        <input type="checkbox" checked={preferred} onChange={(e) => setPreferred(e.target.checked)} />
        I preferred this setup over the previous one
      </label>
      <button className="btn primary big" style={{ width: '100%' }} onClick={() => {
        update((d) => {
          d.feedback.push({
            id: `fb-${Date.now()}`, sessionId: session.id, riderId: rider.id,
            answers, sliders, preferredOverPrevious: preferred, provenance: 'RIDER REPORTED',
          });
          appendAudit(d, user!.id, 'feedback.submit', 'Session', session.id, `Rider feedback submitted for ${session.objective}.`);
        });
      }}>Submit feedback</button>
      {!isThisRider && <p className="hint" style={{ marginTop: 8 }}>Entering on the rider's behalf.</p>}
    </div>
  );
}

const LABELS: Record<string, string> = {
  whatHappened: 'What did the bike do?', where: 'Where?', howOften: 'How often?',
  betterOrWorse: 'Better or worse?', confidenceEffect: 'Confidence effect',
  fatigueEffect: 'Fatigue effect', startsEffect: 'Starts effect',
  compensated: 'Compensation', changedOverSession: 'Changed over session',
};
const SLIDER_LABELS: Record<string, string> = {
  initialHit: 'Initial hit', midrange: 'Midrange', topEnd: 'Top-end',
  throttleResponse: 'Throttle response', engineBraking: 'Engine braking',
  traction: 'Traction feel', predictability: 'Predictability', starting: 'Starting',
  fatigue: 'Fatigue (10 = fresh)', confidence: 'Confidence',
};

// ------------------------------------------------------------- A/B compare

function CompareTab({ session }: { session: Session }) {
  const { db, user, update, allowed } = useApp();
  const ab = db.abTests.find((t) => t.sessionAId === session.id || t.sessionBId === session.id);
  const [otherId, setOtherId] = useState(ab ? (ab.sessionAId === session.id ? ab.sessionBId : ab.sessionAId) ?? '' : '');
  const other = db.sessions.find((s) => s.id === otherId);
  const candidates = db.sessions.filter((s) => s.id !== session.id && s.bikeId === session.bikeId && s.trackId === session.trackId);

  const rows = useMemo(() => (other ? compareSessions(db, other, session) : []), [db, other, session]);
  const fb = db.feedback.find((f) => f.sessionId === session.id);
  const revA = other ? db.mapRevisions.find((r) => r.id === other.setupSnapshot.mapRevisionId) : null;
  const revB = db.mapRevisions.find((r) => r.id === session.setupSnapshot.mapRevisionId);
  const supports = rows.length && fb?.preferredOverPrevious !== undefined
    ? telemetrySupportsPreference(rows, fb.preferredOverPrevious ? 'B' : 'A') : null;

  // engine-condition comparability
  const hoursGap = other ? Math.abs(session.setupSnapshot.hoursAtSession - other.setupSnapshot.hoursAtSession) : 0;
  const buildChanged = other && other.setupSnapshot.engineBuildId !== session.setupSnapshot.engineBuildId;

  return (
    <div>
      <Panel title="A/B comparison">
        <div className="field" style={{ maxWidth: 460 }}>
          <label>Compare this session (B) against (A)</label>
          <select value={otherId} onChange={(e) => setOtherId(e.target.value)}>
            <option value="">— select session A —</option>
            {candidates.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleString()} · {s.objective}</option>)}
          </select>
        </div>
        {other && (
          <>
            {buildChanged && <p style={{ color: 'var(--critical-text)', fontWeight: 600, fontSize: 13 }}>⚠ Engine build changed between sessions — results are NOT comparable as an A/B.</p>}
            {!buildChanged && hoursGap > 5 && <p style={{ color: 'var(--serious-text)', fontWeight: 600, fontSize: 13 }}>⚠ {hoursGap.toFixed(1)} engine hours between sessions — treat differences with caution.</p>}
            <div className="tbl-scroll">
              <table className="data">
                <thead><tr><th>Metric</th><th>A — {revA?.rev}</th><th>B — {revB?.rev}</th><th>Better</th></tr></thead>
                <tbody>
                  {rows.map((r) => {
                    const bBetter = r.betterIs === 'lower' ? r.b < r.a : r.b > r.a;
                    return (
                      <tr key={r.metric}>
                        <td>{r.metric}</td>
                        <td className="num">{r.a}{r.unit}</td>
                        <td className="num"><b>{r.b}{r.unit}</b></td>
                        <td>{r.a === r.b ? '—' : bBetter ? 'B' : 'A'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 10, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {fb?.preferredOverPrevious !== undefined && (
                <Pill tone="neutral">Rider preferred: {fb.preferredOverPrevious ? `B (${revB?.rev})` : `A (${revA?.rev})`}</Pill>
              )}
              {supports !== null && (
                <Pill tone={supports ? 'good' : 'serious'}>
                  Telemetry {supports ? 'supports' : 'challenges'} the rider preference
                </Pill>
              )}
            </div>
            <Help id="ab">
              The rider's preference and the stopwatch are separate answers. When they disagree, that's
              information — the tuner decides which matters for this program, and the decision is audited.
            </Help>
            {ab && (
              <p className="hint" style={{ marginTop: 8 }}>
                Linked A/B test: <b>{ab.name}</b> — outcome {ab.outcome ?? 'pending'} · {ab.conclusion ?? 'no conclusion yet'}
              </p>
            )}
            {allowed('abtest.conclude') && revB && revB.state === 'TESTED' && (
              <div className="btn-row" style={{ marginTop: 10 }}>
                <button className="btn small primary" onClick={() => {
                  update((d) => {
                    const rev = d.mapRevisions.find((r) => r.id === revB.id)!;
                    transitionRevision(d, user!, rev, 'ACCEPTED', 'Accepted after A/B comparison.');
                  });
                }}>Accept {revB.rev}</button>
                <button className="btn small danger" onClick={() => {
                  update((d) => {
                    const rev = d.mapRevisions.find((r) => r.id === revB.id)!;
                    transitionRevision(d, user!, rev, 'REJECTED', 'Rejected after A/B comparison.');
                  });
                }}>Reject {revB.rev}</button>
              </div>
            )}
          </>
        )}
      </Panel>
    </div>
  );
}
