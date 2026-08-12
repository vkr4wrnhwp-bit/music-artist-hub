import React, { useState } from 'react';
import { appendAudit, decideRecommendation, type AIRecommendation, type MapRevision } from '@mxlab/domain';
import { nav, useApp } from '../state';
import { Help, Panel, Pill, Prov } from '../ui';

export function Engineer({ initialId }: { initialId?: string }) {
  const { db } = useApp();
  const [openId, setOpenId] = useState<string | null>(
    initialId
    ?? db.recommendations.find((r) => r.status === 'AWAITING_TUNER_REVIEW')?.id
    ?? db.recommendations[0]?.id ?? null,
  );
  const recs = [...db.recommendations].sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  return (
    <div>
      <div className="page-title">
        <h1>AI Race Engineer</h1>
        <span className="sub">structured analysis — recommends, never controls</span>
      </div>
      <Help id="engineer">
        Every card follows the same pipeline: data-quality check → telemetry correlation → cause ranking
        → non-map checks → proposed controlled test → <b>tuner review</b>. The AI cannot approve a map,
        cannot flash anything, and its confidence is capped whenever data quality is degraded.
      </Help>
      <div className="cols" style={{ gridTemplateColumns: '320px 1fr' }}>
        <Panel title="Recommendations">
          {recs.map((r) => {
            const session = db.sessions.find((s) => s.id === r.sessionId);
            return (
              <div key={r.id}
                onClick={() => setOpenId(r.id)}
                style={{
                  padding: '8px 10px', borderRadius: 8, cursor: 'pointer', marginBottom: 6,
                  border: `1px solid ${openId === r.id ? 'var(--accent)' : 'var(--hairline)'}`,
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6, alignItems: 'baseline' }}>
                  <b style={{ fontSize: 13 }}>{r.observedEvent.slice(0, 44)}…</b>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                  <StatusPill status={r.status} />
                  <Pill tone={r.dataQualityStatus === 'OK' ? 'neutral' : r.dataQualityStatus === 'DEGRADED' ? 'serious' : 'critical'}>data {r.dataQualityStatus}</Pill>
                </div>
                <p className="hint" style={{ margin: '4px 0 0' }}>{session?.objective} · {new Date(r.createdAt).toLocaleDateString()}</p>
              </div>
            );
          })}
          {recs.length === 0 && <p className="hint">No recommendations yet. Create one from a reviewed event marker in a session.</p>}
        </Panel>
        <div>
          {openId && <RecDetail recId={openId} />}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: AIRecommendation['status'] }) {
  const tone = status === 'AWAITING_TUNER_REVIEW' ? 'warning'
    : status === 'ACCEPTED_FOR_TEST' ? 'good'
      : status === 'REJECTED' ? 'critical' : 'neutral';
  return <Pill tone={tone}>{status.replaceAll('_', ' ')}</Pill>;
}

function Sect({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 10.5, fontWeight: 800, letterSpacing: '0.09em', color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13.5 }}>{children}</div>
    </div>
  );
}

function RecDetail({ recId }: { recId: string }) {
  const { db, user, update, allowed } = useApp();
  const rec = db.recommendations.find((r) => r.id === recId);
  if (!rec || !user) return null;
  const session = db.sessions.find((s) => s.id === rec.sessionId)!;
  const rev = db.mapRevisions.find((r) => r.id === session.setupSnapshot.mapRevisionId);
  const map = db.maps.find((m) => m.id === rev?.mapId);
  const canDecide = allowed('ai.decide') && rec.status === 'AWAITING_TUNER_REVIEW';

  return (
    <Panel
      title={`Recommendation — ${rec.id}`}
      actions={<span className="btn-row"><Prov p="AI INFERENCE" /><StatusPill status={rec.status} /></span>}
    >
      <Sect label="Rider statement">“{rec.riderStatement}” <Prov p="RIDER REPORTED" /></Sect>
      <Sect label="Observed event">{rec.observedEvent} — <a href={`#/session/${session.id}`}>open session</a></Sect>
      <Sect label="Measured evidence">
        <ul style={{ margin: 0, paddingLeft: 18 }}>{rec.measuredEvidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
      </Sect>
      <Sect label="Data-quality status">
        <Pill tone={rec.dataQualityStatus === 'OK' ? 'good' : rec.dataQualityStatus === 'DEGRADED' ? 'serious' : 'critical'}>{rec.dataQualityStatus}</Pill>
        {rec.dataQuality.length > 0 && (
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {rec.dataQuality.map((f, i) => <li key={i}>{f.note}</li>)}
          </ul>
        )}
      </Sect>
      <Sect label="Likely cause">
        <b>{rec.likelyCause.category}</b> — {rec.likelyCause.rationale}
      </Sect>
      <Sect label="Alternative causes">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {rec.alternativeCauses.map((c, i) => <li key={i}><b>{c.category}</b> — {c.rationale}</li>)}
        </ul>
      </Sect>
      <Sect label="Non-map items to check first">
        <ul style={{ margin: 0, paddingLeft: 18 }}>{rec.nonMapChecks.map((c, i) => <li key={i}>{c}</li>)}</ul>
      </Sect>
      {rec.affectedRegion && (
        <Sect label="Affected map region (for tuner review)">
          {rec.affectedRegion.description} — table <b>{rec.affectedRegion.tableId}</b>
          {map && rev && <> of <a href={`#/maps/${rev.id}`}>{map.name}-{rev.rev}</a></>}
        </Sect>
      )}
      <Sect label="Proposed A/B test">{rec.proposedTest}</Sect>
      <Sect label="Expected observable result">{rec.expectedObservable}</Sect>
      <Sect label="Risk flags">
        <ul style={{ margin: 0, paddingLeft: 18 }}>{rec.riskFlags.map((f, i) => <li key={i}>{f}</li>)}</ul>
      </Sect>
      {rec.missingData.length > 0 && (
        <Sect label="Missing data">
          <ul style={{ margin: 0, paddingLeft: 18 }}>{rec.missingData.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </Sect>
      )}
      <Sect label="Confidence">
        <b className="mono">{rec.confidencePct}%</b>
        {rec.dataQualityStatus !== 'OK' && <span className="hint"> (capped — degraded data quality)</span>}
        <span className="hint"> — never presented as certainty; requires tuner decision.</span>
      </Sect>
      {rec.tunerDecisionNote && (
        <Sect label="Tuner decision">
          {rec.tunerDecisionNote} — {db.users.find((u) => u.id === rec.decidedByUserId)?.name} <Prov p="TUNER ENTERED" />
        </Sect>
      )}
      {rec.resultNote && <Sect label="Final result">{rec.resultNote}</Sect>}

      {canDecide && (
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button className="btn primary" onClick={() => {
            const note = prompt('Decision note (what will be tested, within which envelope):');
            if (!note) return;
            update((d) => {
              const r = d.recommendations.find((x) => x.id === recId)!;
              decideRecommendation(d, user, r, 'ACCEPTED_FOR_TEST', note);
            });
          }}>Accept for test</button>
          <button className="btn danger" onClick={() => {
            const note = prompt('Rejection note (required):');
            if (!note) return;
            update((d) => {
              const r = d.recommendations.find((x) => x.id === recId)!;
              decideRecommendation(d, user, r, 'REJECTED', note);
            });
          }}>Reject</button>
        </div>
      )}
      {(rec.status === 'AWAITING_TUNER_REVIEW' || rec.status === 'ACCEPTED_FOR_TEST') && (
        <div className="btn-row" style={{ marginTop: 10 }}>
          {allowed('map.createRevision') && rev && (
            <button className="btn" onClick={() => {
              update((d) => {
                const src = d.mapRevisions.find((x) => x.id === rev.id)!;
                const n = d.mapRevisions.filter((r2) => r2.mapId === src.mapId).length;
                const child: MapRevision = JSON.parse(JSON.stringify(src));
                child.id = `rev-${Date.now()}`;
                child.rev = `R${String(n + 5).padStart(2, '0')}`;
                child.state = 'DRAFT';
                child.parentRevisionId = src.id;
                child.authorUserId = user.id;
                child.notes = `Draft for recommendation ${rec.id}: ${rec.likelyCause.category}`;
                child.createdAt = new Date().toISOString();
                child.testedInSessionIds = [];
                delete child.approvedByUserId;
                delete child.approvedAt;
                d.mapRevisions.push(child);
                appendAudit(d, user.id, 'map.create_draft', 'MapRevision', child.id, `${child.rev} drafted from ${src.rev} for ${rec.id}.`);
                nav(`maps/${child.id}`);
              });
            }}>Create draft revision →</button>
          )}
        </div>
      )}
      {!canDecide && rec.status === 'AWAITING_TUNER_REVIEW' && (
        <p className="hint">Awaiting tuner review — your role cannot decide recommendations.</p>
      )}
    </Panel>
  );
}
