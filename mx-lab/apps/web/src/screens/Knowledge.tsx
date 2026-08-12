import React, { useState } from 'react';
import { askTrace, searchAll, type KnowledgeAnswer } from '@mxlab/domain';
import { useApp } from '../state';
import { Help, Panel, Pill } from '../ui';

const EXAMPLES = [
  'What did we learn from the R07 test?',
  'Which gearing has produced the best starts?',
  'Show every session where coolant temperature exceeded 170°F',
  'What changed after engine build B03?',
  'What did we run at Pine Grove?',
];

/** TRACE Knowledge — team memory with citations. Ask TRACE is the power feature. */
export function KnowledgeScreen() {
  const { db } = useApp();
  const [q, setQ] = useState('');
  const [asked, setAsked] = useState('');
  const [answer, setAnswer] = useState<KnowledgeAnswer | null>(null);
  const hits = q.trim().length >= 2 ? searchAll(db, q) : [];

  const ask = (question: string) => {
    setAsked(question);
    setAnswer(askTrace(db, question));
  };

  return (
    <div>
      <div className="page-title">
        <h1>TRACE Knowledge</h1>
        <span className="sub">team memory — every answer cites real records</span>
        <Pill tone="warning">DEVELOPMENT</Pill>
      </div>
      <Help id="knowledge">
        Knowledge is retrieval over the team's structured records — sessions, decisions, tests,
        debriefs, components. TRACE composes answers <b>only</b> from what's on file and links every
        claim; when it doesn't know, it says so.
      </Help>

      <Panel title="Search everything">
        <div className="field" style={{ maxWidth: 480 }}>
          <label>Bikes, riders, sessions, maps, components, decisions, faults, events…</label>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. R07 · S04 · 13/49 · overheating · Pine Grove" />
        </div>
        {hits.length > 0 && (
          <div className="tbl-scroll">
            <table className="data">
              <tbody>
                {hits.map((h) => (
                  <tr key={`${h.kind}-${h.id}`} className="click" onClick={() => { window.location.hash = h.href.slice(1); }}>
                    <td style={{ width: 110 }}><Pill tone="neutral">{h.kind}</Pill></td>
                    <td style={{ fontWeight: 600 }}>{h.title}</td>
                    <td className="hint">{h.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {q.trim().length >= 2 && hits.length === 0 && <p className="hint">No records match “{q}”.</p>}
      </Panel>

      <Panel title="Ask TRACE" actions={<Pill tone="warning">DEVELOPMENT — structured intents only</Pill>}>
        <div className="btn-row" style={{ marginBottom: 12 }}>
          {EXAMPLES.map((e) => (
            <button key={e} className="btn small ghost" onClick={() => ask(e)}>{e}</button>
          ))}
        </div>
        <div className="btn-row">
          <input style={{ flex: 1, minWidth: 240, background: 'var(--raised)', border: 0, borderRadius: 7, padding: '10px 12px' }}
            placeholder="Ask about tests, revisions, starts, builds, events…"
            value={asked} onChange={(e) => setAsked(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && asked.trim()) ask(asked.trim()); }} />
          <button className="btn primary" disabled={!asked.trim()} onClick={() => ask(asked.trim())}>Ask</button>
        </div>
        {answer && (
          <div style={{ marginTop: 16 }}>
            {answer.answer.map((p, i) => <p key={i} style={{ fontSize: 14.5, margin: '0 0 8px' }}>{p}</p>)}
            {answer.citations.length > 0 && (
              <>
                <p className="eyebrow" style={{ marginTop: 12 }}>Sources</p>
                <div className="btn-row">
                  {answer.citations.map((c, i) => (
                    <a key={i} href={c.href} className="btn small ghost">{c.kind}: {c.label}</a>
                  ))}
                </div>
              </>
            )}
            {answer.missing.length > 0 && (
              <p className="hint" style={{ marginTop: 10 }}>Missing / caveats: {answer.missing.join(' · ')}</p>
            )}
            <p className="hint" style={{ marginTop: 6 }}>
              Confidence {answer.confidence.pct}% ({answer.confidence.label}) — {answer.confidence.basis}.
              Composed from team records only; nothing here is generated without a source.
            </p>
          </div>
        )}
      </Panel>

      <Panel title="Decision log">
        {db.decisions.map((d) => (
          <div key={d.id} style={{ background: 'var(--raised)', borderRadius: 10, padding: '12px 16px', marginBottom: 10 }}>
            <p style={{ margin: 0, fontWeight: 700 }}>{d.decision}</p>
            <p style={{ margin: '4px 0', fontSize: 13.5, color: 'var(--ink-2)' }}>{d.rationale}</p>
            <p className="hint" style={{ margin: 0 }}>
              {db.users.find((u) => u.id === d.authorUserId)?.name} · {new Date(d.at).toLocaleString()}
              {d.outcome && ` · outcome: ${d.outcome}`}
              {' · '}{d.sessionIds.map((id) => <a key={id} href={`#/session/${id}`} style={{ marginRight: 6 }}>{id}</a>)}
            </p>
            {d.followUp && <p className="hint" style={{ margin: '4px 0 0' }}>Follow-up: {d.followUp}</p>}
          </div>
        ))}
        {db.decisions.length === 0 && <p className="hint">No decisions recorded yet.</p>}
      </Panel>

      <Panel title="Stored debriefs">
        {db.debriefs.map((d) => (
          <div key={d.id} style={{ marginBottom: 12 }}>
            <p className="eyebrow">{d.date}{d.approvedByUserId ? ` · approved by ${db.users.find((u) => u.id === d.approvedByUserId)?.name}` : ' · draft'}</p>
            <ul style={{ margin: '4px 0', paddingLeft: 18, fontSize: 13.5 }}>
              {d.learned.map((l, i) => <li key={i}>{l}</li>)}
            </ul>
          </div>
        ))}
      </Panel>
    </div>
  );
}
