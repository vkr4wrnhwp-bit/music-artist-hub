import React, { useMemo, useState } from 'react';
import { coachingInsights, computeRiderDNA, fatigueEstimate } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill, Prov } from '../ui';

/** Rider DNA + coaching + fatigue — measured, preferred, and inferred kept separate. */
export function RidersScreen() {
  const { db } = useApp();
  const [riderId, setRiderId] = useState(db.riders[0]?.id ?? '');
  const rider = db.riders.find((r) => r.id === riderId)!;
  const dna = useMemo(() => computeRiderDNA(db, rider), [db, rider]);
  const sessions = db.sessions.filter((s) => s.riderId === riderId).sort((a, b) => b.startedAt.localeCompare(a.startedAt));
  const [sessionId, setSessionId] = useState(sessions[0]?.id ?? '');
  const session = db.sessions.find((s) => s.id === sessionId) ?? sessions[0];
  const coaching = useMemo(() => (session ? coachingInsights(db, session) : []), [db, session]);
  const fatigue = useMemo(() => (session ? fatigueEstimate(db, session) : null), [db, session]);

  return (
    <div>
      <div className="page-title">
        <h1>Riders</h1>
        <span className="sub">DNA · coaching · fatigue — development analyses over simulated data</span>
        <Pill tone="warning">DEVELOPMENT</Pill>
      </div>
      <div className="btn-row" style={{ marginBottom: 18 }}>
        {db.riders.map((r) => (
          <button key={r.id} className={`btn ${riderId === r.id ? 'primary' : ''}`} onClick={() => { setRiderId(r.id); setSessionId(''); }}>{r.name}</button>
        ))}
      </div>

      <div className="cols-3">
        <Panel title="Measured behavior" actions={<Prov p="CALCULATED" />}>
          <dl className="kv">
            <dt>Typical RPM band</dt><dd className="mono">{dna.measured.typicalRpmBand[0].toLocaleString()}–{dna.measured.typicalRpmBand[1].toLocaleString()}</dd>
            <dt>Throttle aggressiveness</dt><dd className="mono">{dna.measured.throttleAggressiveness} <span className="hint">(mean |ΔTPS|, normalized)</span></dd>
            <dt>Clutch use</dt><dd className="mono">{dna.measured.clutchUsePctOfLap}% of lap</dd>
            <dt>Avg min corner speed</dt><dd className="mono">{dna.measured.avgMinCornerSpeed} kph</dd>
            <dt>Lap consistency</dt><dd className="mono">σ {dna.measured.lapConsistency}s</dd>
            <dt>Sample</dt><dd className="mono">{dna.measured.sessions} sessions (SIMULATED)</dd>
          </dl>
        </Panel>
        <Panel title="Rider preference" actions={<Prov p="RIDER REPORTED" />}>
          <dl className="kv">
            <dt>Delivery</dt><dd>{dna.preferences.delivery}</dd>
            <dt>Engine braking</dt><dd>{dna.preferences.engineBraking}</dd>
            <dt>Initial hit</dt><dd>{dna.preferences.initialHit}</dd>
          </dl>
          <p className="hint">Preference is not performance — TRACE keeps both and never swaps one for the other.</p>
        </Panel>
        <Panel title="Inference" actions={<Prov p="AI INFERENCE" />}>
          <dl className="kv">
            <dt>Setup sensitivity</dt><dd>{dna.inferred.setupSensitivity}</dd>
            <dt>Track types</dt><dd>{dna.inferred.trackTypeStrength}</dd>
          </dl>
          <p className="hint">{dna.inferred.basis}</p>
        </Panel>
      </div>

      <Panel title="Coaching" actions={<Pill tone="warning">DEVELOPMENT</Pill>}>
        <div className="field" style={{ maxWidth: 460 }}>
          <label>Session</label>
          <select value={session?.id ?? ''} onChange={(e) => setSessionId(e.target.value)}>
            {sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective}</option>)}
          </select>
        </div>
        {coaching.length === 0 && <p className="hint">No coaching signals stood out in this session.</p>}
        {coaching.map((c, i) => (
          <div key={i} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px', marginBottom: 10 }}>
            <p style={{ margin: 0, fontSize: 14 }}>{c.text}</p>
            <p className="hint" style={{ margin: '4px 0 0' }}>{c.evidence} · shareable with rider · <Prov p={c.provenance} /></p>
          </div>
        ))}
        <Help id="coaching">
          Coaching notes are written to be handed to the rider without exposing tuning detail —
          what to trust and where the time is, not fuel numbers.
        </Help>
      </Panel>

      {fatigue && (
        <Panel title="Fatigue pattern" actions={<Pill tone="warning">DEVELOPMENT ESTIMATE</Pill>}>
          <p style={{ margin: 0, fontWeight: 650 }}>
            {fatigue.detected ? `Pattern detected${fatigue.onsetLap ? ` — estimated onset lap ${fatigue.onsetLap}` : ''}` : 'No consistent fatigue signature'}
          </p>
          <ul style={{ margin: '6px 0', paddingLeft: 18, fontSize: 13.5 }}>
            {fatigue.evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
          <p style={{ fontSize: 12, fontWeight: 750, color: 'var(--warning)', letterSpacing: '0.04em' }}>{fatigue.disclaimer}</p>
        </Panel>
      )}
    </div>
  );
}
