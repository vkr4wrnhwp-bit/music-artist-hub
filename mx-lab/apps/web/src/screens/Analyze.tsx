import React from 'react';
import { compareSessions } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { EmptyState, Help, Panel, Pill } from '../ui';

/**
 * ANALYZE — findings before graphs. TRACE composes findings from concluded
 * A/B tests (focus outcomes), open insights, session anomalies, and data
 * quality. Evidence is one tap deeper.
 */
export function AnalyzeHub() {
  const { db } = useApp();

  interface Finding {
    id: string;
    title: string;
    delta?: { text: string; dir: 'up' | 'down' | 'flat' };
    body: string;
    confidence?: string;
    action: () => void;
    actionLabel: string;
  }
  const findings: Finding[] = [];

  // 1) focus outcome from concluded A/B tests
  for (const ab of db.abTests.filter((t) => t.outcome)) {
    const a = db.sessions.find((s) => s.id === ab.sessionAId);
    const b = db.sessions.find((s) => s.id === ab.sessionBId);
    const revB = db.mapRevisions.find((r) => r.id === ab.revisionBId);
    let deltaTxt = '';
    if (a && b) {
      const rows = compareSessions(db, a, b);
      const best = rows.find((r) => r.metric === 'Best lap');
      if (best) deltaTxt = `${(best.a - best.b) >= 0 ? '−' : '+'}${Math.abs(best.a - best.b).toFixed(2)}s best lap`;
    }
    findings.push({
      id: ab.id,
      title: ab.name,
      delta: deltaTxt ? { text: deltaTxt, dir: deltaTxt.startsWith('−') ? 'up' : 'down' } : undefined,
      body: `${ab.conclusion ?? ''} Rider preferred ${ab.riderPreferred}; telemetry ${ab.telemetrySupportsPreference ? 'agreed' : 'disagreed'}.`,
      confidence: 'Concluded A/B',
      action: () => nav(`session/${ab.sessionBId}/compare`),
      actionLabel: 'Open evidence',
    });
  }

  // 2) open TRACE insights
  for (const rec of db.recommendations.filter((r) => r.status === 'AWAITING_TUNER_REVIEW')) {
    findings.push({
      id: rec.id,
      title: rec.observedEvent,
      body: `${rec.likelyCause.category} — ${rec.likelyCause.rationale}`,
      confidence: `${rec.confidencePct}% confidence · data ${rec.dataQualityStatus}`,
      action: () => nav(`engineer/${rec.id}`),
      actionLabel: 'Review',
    });
  }

  // 3) sensor / data-quality findings
  for (const dev of db.devices) {
    const bad = Object.entries(dev.channelHealth).filter(([, q]) => q === 'Missing' || q === 'Intermittent' || q === 'Out of range');
    if (bad.length) {
      const bike = db.bikes.find((b) => b.id === dev.assignedBikeId);
      findings.push({
        id: `dq-${dev.id}`,
        title: `${bike?.label ?? dev.id}: ${bad.map(([c]) => c).join(', ')} channel ${bad.length > 1 ? 'faults' : 'fault'}`,
        body: 'Telemetry from this channel is excluded from analysis, and TRACE caps insight confidence until it is repaired.',
        confidence: 'Data quality',
        action: () => nav('hardware'),
        actionLabel: 'Open hardware',
      });
    }
  }

  const tracks = db.tracks;

  return (
    <div>
      <div className="page-title">
        <h1>Analyze</h1>
        <span className="sub">findings first — evidence one tap deeper</span>
      </div>
      <Help id="analyze">
        TRACE leads with what it found, not with charts. Every finding says what changed, why it
        matters, and how confident the data allows it to be. Raw telemetry lives inside each
        session's Data view.
      </Help>

      <p className="eyebrow">TRACE found {findings.length} {findings.length === 1 ? 'thing' : 'things'}</p>
      {findings.length === 0 && (
        <EmptyState title="Nothing to report yet">Run a session and TRACE will surface findings here.</EmptyState>
      )}
      {findings.map((f, i) => (
        <div key={f.id} className="finding">
          <span className="f-n">{i + 1}</span>
          <div style={{ flex: 1 }}>
            <h4>
              {f.title}{' '}
              {f.delta && <span className={`f-delta ${f.delta.dir === 'up' ? 'up' : 'down'}`}>{f.delta.text}</span>}
            </h4>
            <p>{f.body}</p>
            {f.confidence && <p className="hint">{f.confidence}</p>}
          </div>
          <button className="btn small" onClick={f.action}>{f.actionLabel}</button>
        </div>
      ))}

      <div className="cols" style={{ marginTop: 28 }}>
        <Panel title="Track view & data explorer">
          <p className="hint" style={{ marginTop: 0 }}>
            Track position is the navigation surface: open a session, tap a corner, compare passes.
          </p>
          {[...db.sessions].sort((a, b) => b.startedAt.localeCompare(a.startedAt)).slice(0, 4).map((s) => (
            <div key={s.id} className="btn-row" style={{ marginBottom: 8 }}>
              <button className="btn small" onClick={() => nav(`session/${s.id}/track`)}>
                {db.tracks.find((t) => t.id === s.trackId)?.name.split(' (')[0]} · {new Date(s.startedAt).toLocaleDateString()}
              </button>
              <span className="hint">{s.objective}</span>
            </div>
          ))}
        </Panel>
        <Panel title="Comparisons & exports">
          <div className="btn-row" style={{ marginBottom: 6 }}>
            <button className="btn small" onClick={() => nav('starts')}>Starts comparison</button>
            <button className="btn small" onClick={() => nav('reports')}>Reports / exports</button>
            <button className="btn small" onClick={() => nav('audit')}>Audit history</button>
          </div>
          <p className="hint">
            A/B session comparison lives inside each session (Compare tab), so the evidence stays next
            to the laps that produced it.
          </p>
        </Panel>
      </div>
      <p className="hint">Tracks on file: {tracks.map((t) => t.name).join(' · ')}</p>
    </div>
  );
}
