import React, { useState } from 'react';
import { appendAudit, detectUncontrolled, type TestPlan, type TestVariant } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill } from '../ui';

/** TRACE Test Planner — structured experiments, uncontrolled variables flagged. */
export function Planner() {
  const { db, user, update, allowed } = useApp();
  const [creating, setCreating] = useState(false);
  const canPlan = allowed('session.create');

  return (
    <div>
      <div className="page-title">
        <h1>Test Planner</h1>
        <span className="sub">one variable at a time, or TRACE tells you why the result will be weaker</span>
      </div>
      <Help id="planner">
        A plan declares the intended variable and what must hold constant. Sessions link to variants;
        What Changed and Compare then know which differences were <b>intended</b> vs uncontrolled.
      </Help>
      {canPlan && !creating && (
        <div className="btn-row" style={{ marginBottom: 20 }}>
          <button className="btn primary" onClick={() => setCreating(true)}>New test plan</button>
        </div>
      )}
      {creating && <NewPlan onDone={() => setCreating(false)} />}

      {db.testPlans.map((p) => <PlanCard key={p.id} plan={p} />)}
    </div>
  );
}

function PlanCard({ plan }: { plan: TestPlan }) {
  const { db, user, update, allowed } = useApp();
  const bike = db.bikes.find((b) => b.id === plan.bikeId);
  const rider = db.riders.find((r) => r.id === plan.riderId);
  const warnings = detectUncontrolled(plan);
  const tone = plan.status === 'complete' ? 'good' : plan.status === 'planned' ? 'warning' : plan.status === 'running' ? 'neutral' : 'critical';

  return (
    <Panel title={plan.objective} actions={<Pill tone={tone}>{plan.status}</Pill>}>
      <p className="hint" style={{ marginTop: 0 }}>
        {bike?.label} · {rider?.name} · {plan.kind.replaceAll('_', ' ')} test
        {plan.trackId && ` · ${db.tracks.find((t) => t.id === plan.trackId)?.name}`}
      </p>
      {warnings.map((w, i) => <p key={i} style={{ color: 'var(--warning)', fontWeight: 650, fontSize: 13 }}>⚠ {w}</p>)}
      <div className="cols">
        {plan.variants.map((v) => {
          const rev = db.mapRevisions.find((r) => r.id === v.mapRevisionId);
          const session = db.sessions.find((s) => s.id === v.sessionId);
          return (
            <div key={v.id} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px' }}>
              <p className="eyebrow" style={{ margin: 0 }}>{v.label}</p>
              <dl className="kv" style={{ marginTop: 6 }}>
                <dt>Map</dt><dd className="mono">{rev?.rev ?? '—'}</dd>
                <dt>Gearing</dt><dd className="mono">{v.gearing ?? '—'}</dd>
                <dt>Rear pressure</dt><dd className="mono">{v.tirePressureRear ?? '—'} bar</dd>
                <dt>Session</dt>
                <dd>{session
                  ? <a href={`#/session/${session.id}`}>{new Date(session.startedAt).toLocaleDateString()}</a>
                  : <LinkSession planId={plan.id} variantId={v.id} />}
                </dd>
              </dl>
            </div>
          );
        })}
      </div>
      <p className="hint">Hold constant: {plan.holdConstant.join(', ') || '—'}</p>
      {plan.conclusion && <p style={{ fontSize: 13.5 }}><b>Conclusion:</b> {plan.conclusion}</p>}
      <div className="btn-row" style={{ marginTop: 8 }}>
        {plan.variants.length >= 2 && plan.variants[0].sessionId && plan.variants[1].sessionId && (
          <button className="btn small primary" onClick={() => nav(`compare/${plan.variants[0].sessionId}/${plan.variants[1].sessionId}`)}>
            Open in TRACE Compare
          </button>
        )}
        {plan.status !== 'complete' && allowed('abtest.conclude') && plan.variants.every((v) => v.sessionId) && (
          <button className="btn small" onClick={() => {
            const c = prompt('Conclusion (recorded as a team decision):');
            if (!c) return;
            update((d) => {
              const p = d.testPlans.find((x) => x.id === plan.id)!;
              p.status = 'complete';
              p.conclusion = c;
              const dec = {
                id: `dec-${Date.now()}`, orgId: d.org.id, at: new Date().toISOString(),
                authorUserId: user!.id, bikeId: p.bikeId, riderId: p.riderId,
                sessionIds: p.variants.map((v) => v.sessionId!).filter(Boolean),
                decision: `Test concluded: ${p.objective}`, rationale: c,
              };
              d.decisions.push(dec);
              p.decisionId = dec.id;
              appendAudit(d, user!.id, 'plan.conclude', 'TestPlan', p.id, `Concluded: ${c}`);
            });
          }}>Conclude…</button>
        )}
      </div>
    </Panel>
  );
}

function LinkSession({ planId, variantId }: { planId: string; variantId: string }) {
  const { db, user, update, allowed } = useApp();
  if (!allowed('session.create')) return <span className="hint">not run yet</span>;
  return (
    <select defaultValue="" onChange={(e) => {
      const sid = e.target.value;
      if (!sid) return;
      update((d) => {
        const p = d.testPlans.find((x) => x.id === planId)!;
        p.variants.find((v) => v.id === variantId)!.sessionId = sid;
        if (p.status === 'planned') p.status = 'running';
        appendAudit(d, user!.id, 'plan.link_session', 'TestPlan', p.id, `Variant ${variantId} linked to ${sid}.`);
      });
    }}>
      <option value="">link session…</option>
      {db.sessions.map((s) => <option key={s.id} value={s.id}>{new Date(s.startedAt).toLocaleDateString()} · {s.objective.slice(0, 40)}</option>)}
    </select>
  );
}

function NewPlan({ onDone }: { onDone: () => void }) {
  const { db, user, update } = useApp();
  const [objective, setObjective] = useState(db.focus?.text ?? '');
  const [kind, setKind] = useState<TestPlan['kind']>('ab');
  const [bikeId, setBikeId] = useState(db.bikes[0]?.id ?? '');
  const [riderId, setRiderId] = useState(db.riders[0]?.id ?? '');
  const mkVariant = (id: string): TestVariant => ({
    id, label: id,
    mapRevisionId: db.bikes.find((b) => b.id === bikeId)?.currentMapRevisionId,
    gearing: db.bikes.find((b) => b.id === bikeId)?.setup.gearing,
    tirePressureRear: db.bikes.find((b) => b.id === bikeId)?.setup.tirePressureRear,
  });
  const [variants, setVariants] = useState<TestVariant[]>([mkVariant('A'), mkVariant('B')]);
  const [hold, setHold] = useState<string[]>(['suspension', 'fuel', 'tire', 'clutch']);
  const warnings = detectUncontrolled({ variants });

  const setV = (i: number, patch: Partial<TestVariant>) =>
    setVariants(variants.map((v, k) => (k === i ? { ...v, ...patch } : v)));

  return (
    <Panel title="New test plan">
      <div className="grid2">
        <div className="field"><label>Objective</label>
          <input value={objective} onChange={(e) => setObjective(e.target.value)} />
        </div>
        <div className="field"><label>Kind</label>
          <select value={kind} onChange={(e) => setKind(e.target.value as TestPlan['kind'])}>
            {(['ab', 'abc', 'blind', 'rider_preference', 'start', 'section', 'durability'] as const).map((k) => <option key={k} value={k}>{k.replaceAll('_', ' ')}</option>)}
          </select>
        </div>
        <div className="field"><label>Bike</label>
          <select value={bikeId} onChange={(e) => setBikeId(e.target.value)}>
            {db.bikes.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
          </select>
        </div>
        <div className="field"><label>Rider</label>
          <select value={riderId} onChange={(e) => setRiderId(e.target.value)}>
            {db.riders.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </div>
      </div>
      <div className="cols">
        {variants.map((v, i) => (
          <div key={v.id} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px' }}>
            <p className="eyebrow">Test {v.id}</p>
            <div className="field"><label>Map revision</label>
              <select value={v.mapRevisionId ?? ''} onChange={(e) => setV(i, { mapRevisionId: e.target.value })}>
                {db.mapRevisions.map((r) => <option key={r.id} value={r.id}>{db.maps.find((m) => m.id === r.mapId)?.name}-{r.rev}</option>)}
              </select>
            </div>
            <div className="field"><label>Gearing</label>
              <input value={v.gearing ?? ''} onChange={(e) => setV(i, { gearing: e.target.value })} />
            </div>
            <div className="field"><label>Rear pressure (bar)</label>
              <input type="number" step="0.01" value={v.tirePressureRear ?? 0.85} onChange={(e) => setV(i, { tirePressureRear: parseFloat(e.target.value) || 0.85 })} />
            </div>
          </div>
        ))}
      </div>
      {kind === 'abc' && variants.length < 3 && (
        <button className="btn small ghost" onClick={() => setVariants([...variants, mkVariant('C')])}>+ Variant C</button>
      )}
      <div className="field" style={{ marginTop: 10 }}>
        <label>Hold constant</label>
        <div className="btn-row">
          {['suspension', 'fuel', 'tire', 'clutch', 'gearing', 'pressureR', 'map', 'sag'].map((f) => (
            <button key={f} className={`btn small ${hold.includes(f) ? 'primary' : 'ghost'}`}
              onClick={() => setHold(hold.includes(f) ? hold.filter((x) => x !== f) : [...hold, f])}>{f}</button>
          ))}
        </div>
      </div>
      {warnings.map((w, i) => <p key={i} style={{ color: 'var(--warning)', fontWeight: 650, fontSize: 13 }}>⚠ {w}</p>)}
      <div className="btn-row" style={{ marginTop: 10 }}>
        <button className="btn primary" disabled={!objective.trim()} onClick={() => {
          update((d) => {
            d.testPlans.unshift({
              id: `plan-${Date.now()}`, orgId: d.org.id, objective: objective.trim(), kind,
              bikeId, riderId, variants, holdConstant: hold, status: 'planned',
              createdByUserId: user!.id, createdAt: new Date().toISOString(),
            });
            appendAudit(d, user!.id, 'plan.create', 'TestPlan', 'new', `Test plan created: ${objective.trim()}`);
          });
          onDone();
        }}>Create plan</button>
        <button className="btn ghost" onClick={onDone}>Cancel</button>
      </div>
    </Panel>
  );
}
