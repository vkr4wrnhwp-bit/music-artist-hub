import React, { useMemo, useState } from 'react';
import {
  compareSessions, compareSetups, confidenceFrom, rankContributors,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { EmptyState, Help, Panel, Pill } from '../ui';

/**
 * TRACE Compare — flagship workspace.
 * WHAT CHANGED → WHAT HAPPENED → WHAT PROBABLY CAUSED IT → raw evidence.
 */
export function CompareWorkspace({ aId, bId }: { aId?: string; bId?: string }) {
  const { db } = useApp();
  const sessions = [...db.sessions].sort((a, b) => a.startedAt.localeCompare(b.startedAt));
  const [selA, setSelA] = useState(aId ?? 'sess-4');
  const [selB, setSelB] = useState(bId ?? 'sess-5');
  const a = db.sessions.find((s) => s.id === selA);
  const b = db.sessions.find((s) => s.id === selB);

  const plan = db.testPlans.find((p) =>
    p.variants.some((v) => v.sessionId === selA) && p.variants.some((v) => v.sessionId === selB));

  const vars = useMemo(() => (a && b
    ? compareSetups(db, a, b, plan?.holdConstant ?? [],
      plan ? ['map', 'gearing', 'pressureR', 'trims'] : [])
    : []), [db, a, b, plan]);
  const changed = vars.filter((v) => v.changed);
  const metrics = useMemo(() => (a && b ? compareSessions(db, a, b) : []), [db, a, b]);
  const contributors = useMemo(() => (a && b ? rankContributors(db, a, b, vars) : []), [db, a, b, vars]);
  const fbB = b ? db.feedback.find((f) => f.sessionId === b.id) : null;
  const fbA = a ? db.feedback.find((f) => f.sessionId === a.id) : null;
  const confDelta = fbA && fbB ? fbB.sliders.confidence - fbA.sliders.confidence : null;

  const uncontrolled = changed.filter((v) => !v.intended && !['weather', 'trackCond', 'hours', 'slot', 'hardware'].includes(v.field)).length;
  const conf = confidenceFrom({
    sampleSize: a && b ? 2 : 0, dataQualityOk: true,
    conditionSimilarity: a && b && a.trackId === b.trackId ? 0.9 : 0.4,
    variablesChanged: Math.max(0, uncontrolled - 1),
  });

  const sessionOpt = (s: typeof sessions[number]) =>
    `${new Date(s.startedAt).toLocaleDateString()} · ${db.bikes.find((x) => x.id === s.bikeId)?.label} · ${s.objective}`;

  return (
    <div>
      <div className="page-title">
        <h1>TRACE Compare</h1>
        <span className="sub">what changed → what happened → what probably caused it</span>
      </div>
      <Help id="compare">
        Compare is honest about attribution: intended variables are marked, uncontrolled changes lower
        the confidence, and every number links back to the session that produced it.
      </Help>
      <div className="cols" style={{ marginBottom: 4 }}>
        <div className="field"><label>Session A (baseline)</label>
          <select value={selA} onChange={(e) => setSelA(e.target.value)}>
            {sessions.map((s) => <option key={s.id} value={s.id}>{sessionOpt(s)}</option>)}
          </select>
        </div>
        <div className="field"><label>Session B (candidate)</label>
          <select value={selB} onChange={(e) => setSelB(e.target.value)}>
            {sessions.map((s) => <option key={s.id} value={s.id}>{sessionOpt(s)}</option>)}
          </select>
        </div>
      </div>
      {!a || !b || a.id === b.id ? (
        <EmptyState title="Pick two different sessions">Any two sessions can be compared — bikes, riders, maps, gearing, or conditions.</EmptyState>
      ) : (
        <>
          {plan && <p className="hint" style={{ marginBottom: 14 }}>Linked test plan: <b>{plan.objective}</b> — hold-constant rules applied.</p>}

          <p className="eyebrow">What changed?</p>
          <Panel>
            {changed.length === 0 && <p className="hint" style={{ margin: 0 }}>No configuration differences recorded.</p>}
            <div className="tbl-scroll">
              <table className="data">
                <tbody>
                  {changed.map((v) => (
                    <tr key={v.field}>
                      <td style={{ width: 180, color: 'var(--muted)', textTransform: 'uppercase', fontSize: 11, fontWeight: 750, letterSpacing: '0.08em' }}>{v.label}</td>
                      <td className="mono">{v.a} → <b>{v.b}</b></td>
                      <td>
                        {v.intended && <Pill tone="good">Intended</Pill>}
                        {v.shouldHoldConstant && <Pill tone="critical">Should have held constant</Pill>}
                        {!v.intended && !v.shouldHoldConstant && ['weather', 'trackCond', 'hours'].includes(v.field) && <Pill tone="neutral">Environment</Pill>}
                        {!v.intended && !v.shouldHoldConstant && !['weather', 'trackCond', 'hours'].includes(v.field) && <Pill tone="warning">Uncontrolled</Pill>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <p className="eyebrow">What happened?</p>
          <Panel>
            <div style={{ display: 'flex', gap: 40, flexWrap: 'wrap' }}>
              {metrics.map((m) => {
                const delta = +(m.b - m.a).toFixed(2);
                const better = m.betterIs === 'lower' ? delta < 0 : delta > 0;
                return (
                  <div key={m.metric} className="pit-stat" style={{ fontSize: 26 }}>
                    <span style={{ color: delta === 0 ? 'var(--ink)' : better ? 'var(--good)' : 'var(--critical)' }}>
                      {delta > 0 ? '+' : ''}{delta}{m.unit}
                    </span>
                    <small>{m.metric} ({m.a}{m.unit} → {m.b}{m.unit})</small>
                  </div>
                );
              })}
              {confDelta !== null && (
                <div className="pit-stat" style={{ fontSize: 26 }}>
                  <span style={{ color: confDelta >= 0 ? 'var(--good)' : 'var(--critical)' }}>{confDelta > 0 ? '+' : ''}{confDelta}</span>
                  <small>Rider confidence (0–10)</small>
                </div>
              )}
            </div>
          </Panel>

          <p className="eyebrow">What probably caused it?</p>
          <Panel>
            {contributors.length === 0 ? <p className="hint" style={{ margin: 0 }}>Nothing changed — differences are noise or environment.</p> : (
              <ol style={{ margin: 0, paddingLeft: 20 }}>
                {contributors.map((c, i) => (
                  <li key={i} style={{ marginBottom: 8 }}>
                    <b>{c.label}</b>
                    <span className="hint" style={{ display: 'block' }}>{c.rationale}</span>
                  </li>
                ))}
              </ol>
            )}
            <p className="hint" style={{ marginTop: 12 }}>
              Attribution confidence: <b>{conf.pct}%</b> ({conf.label}) — {conf.basis}.
            </p>
          </Panel>

          <div className="btn-row">
            <button className="btn" onClick={() => nav(`session/${b.id}/compare`)}>Open raw evidence (session B)</button>
            <button className="btn ghost" onClick={() => nav(`session/${a.id}`)}>Session A</button>
            <button className="btn ghost" onClick={() => nav(`session/${b.id}`)}>Session B</button>
          </div>
        </>
      )}
    </div>
  );
}
