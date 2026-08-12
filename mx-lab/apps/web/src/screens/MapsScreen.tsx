import React, { useMemo, useState } from 'react';
import {
  appendAudit, checkCompatibility, diffRevisions, diffTrims, exceedsEnvelope,
  transitionRevision, type MapRevision,
} from '@mxlab/domain';
import { nav, useApp } from '../state';
import { download, Drawer, fmtSigned, heatColor, Help, inkFor, Panel, Pill, Prov, themeHeat, useThemeVersion } from '../ui';
import { AuditList } from './BikeProfile';

const FLOW: MapRevision['state'][] = [
  'DRAFT', 'TUNER_REVIEW', 'APPROVED_FOR_TEST', 'EXPORTED', 'TRANSFER_CONFIRMED', 'TESTED', 'ACCEPTED', 'TEAM_BASELINE',
];

export function MapLibrary() {
  const { db } = useApp();
  return (
    <div>
      <div className="page-title">
        <h1>Tune</h1>
        <span className="sub">team IP — access is role-gated and every view/export is audited</span>
      </div>
      <Help id="maplib">
        A map revision is authored against an <b>exact compatibility key</b> (model year, ECU definition,
        firmware, engine build, fuel, exhaust). It is never automatically available to another bike.
      </Help>

      {/* current maps first — the thing a tuner reaches for */}
      <div className="cols" style={{ marginBottom: 4 }}>
        {db.bikes.filter((b) => !b.retired && b.currentMapRevisionId).map((b) => {
          const rev = db.mapRevisions.find((r) => r.id === b.currentMapRevisionId)!;
          const m = db.maps.find((x) => x.id === rev.mapId);
          return (
            <button key={b.id} className="finding" style={{ textAlign: 'left', cursor: 'pointer', width: '100%' }} onClick={() => nav(`maps/${rev.id}`)}>
              <div style={{ flex: 1 }}>
                <p className="eyebrow" style={{ margin: 0 }}>Current on {b.label}</p>
                <h4 className="mono" style={{ fontSize: 18 }}>{m?.name}-{rev.rev}</h4>
                <p>Slot {b.currentMapSlot} · {rev.state.replaceAll('_', ' ')} · trims {Object.entries(b.trims).map(([k, v]) => `${k}:${v}`).join(' ')}</p>
              </div>
              <span style={{ color: 'var(--muted)' }}>→</span>
            </button>
          );
        })}
      </div>

      {db.maps.map((m) => (
        <Panel key={m.id} title={`${m.name} — ${m.purpose}`}>
          <div className="tbl-scroll">
            <table className="data">
              <thead><tr><th>Rev</th><th>State</th><th>Author</th><th>Created</th><th>Parent</th><th>Notes</th><th>Tested in</th></tr></thead>
              <tbody>
                {db.mapRevisions.filter((r) => r.mapId === m.id).map((r) => (
                  <tr key={r.id} className="click" onClick={() => nav(`maps/${r.id}`)}>
                    <td className="mono">{r.rev}</td>
                    <td><StatePill state={r.state} /></td>
                    <td>{db.users.find((u) => u.id === r.authorUserId)?.name}</td>
                    <td>{new Date(r.createdAt).toLocaleDateString()}</td>
                    <td className="mono">{db.mapRevisions.find((p) => p.id === r.parentRevisionId)?.rev ?? '—'}</td>
                    <td>{r.notes}</td>
                    <td>{r.testedInSessionIds.map((s) => <a key={s} href={`#/session/${s}`} onClick={(e) => e.stopPropagation()}>{s} </a>)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ))}
      <Panel title="Map slots (per bike)">
        <Help id="slots">
          Slot systems are configurable per verified ECU definition. The 10-slot layout below is a
          <b> configurable example</b>, not a universal Vortex rule.
        </Help>
        <div className="cols">
          {db.bikes.map((b) => (
            <div key={b.id}>
              <h4 style={{ margin: '4px 0 8px' }} className="mono">{b.label}</h4>
              <div className="tbl-scroll">
                <table className="data">
                  <thead><tr><th>Slot</th><th>Revision</th><th>Purpose</th></tr></thead>
                  <tbody>
                    {(db.mapSlots[b.id] ?? []).map((s) => {
                      const r = db.mapRevisions.find((x) => x.id === s.mapRevisionId);
                      const m = db.maps.find((x) => x.id === r?.mapId);
                      return (
                        <tr key={s.slot}>
                          <td className="num">{s.slot}</td>
                          <td className="mono">{r ? <a href={`#/maps/${r.id}`}>{m?.name}-{r.rev}</a> : 'empty'}</td>
                          <td>{s.purpose ?? '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function StatePill({ state }: { state: MapRevision['state'] }) {
  const tone = state === 'TEAM_BASELINE' || state === 'ACCEPTED' ? 'good'
    : state === 'REJECTED' || state === 'RETIRED' ? 'critical'
      : state === 'DRAFT' || state === 'TUNER_REVIEW' ? 'neutral' : 'warning';
  return <Pill tone={tone}>{state.replaceAll('_', ' ')}</Pill>;
}

// ------------------------------------------------------------------ workspace

export function MapWorkspace({ revId }: { revId: string }) {
  const { db, user, update, allowed } = useApp();
  useThemeVersion();
  const revision = db.mapRevisions.find((r) => r.id === revId);
  const [tableId, setTableId] = useState('fuel');
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [anchor, setAnchor] = useState<[number, number] | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [advOpen, setAdvOpen] = useState(false);
  const [checkBikeId, setCheckBikeId] = useState(db.bikes[0]?.id ?? '');

  if (!revision || !user) return <p>Revision not found.</p>;
  const map = db.maps.find((m) => m.id === revision.mapId)!;
  const tableDef = map.tableDefs.find((td) => td.id === tableId) ?? map.tableDefs[0];
  const xAxis = map.axes.find((a) => a.id === tableDef.xAxisId)!;
  const yAxis = map.axes.find((a) => a.id === tableDef.yAxisId)!;
  const parent = db.mapRevisions.find((r) => r.id === revision.parentRevisionId);
  const grid = revision.tables[tableDef.id];
  const editable = revision.state === 'DRAFT' && allowed('map.editDraft');
  const th = themeHeat();

  const diff = parent ? diffRevisions(parent, revision) : [];
  const trimDiff = parent ? diffTrims(parent, revision) : [];
  const envelope = parent ? exceedsEnvelope(db, parent, revision) : { exceeded: false, details: [] };
  const relatedInsight = db.recommendations.find(
    (r) => r.status === 'AWAITING_TUNER_REVIEW'
      && db.sessions.find((s) => s.id === r.sessionId)?.setupSnapshot.mapRevisionId
      && db.mapRevisions.find((x) => x.id === db.sessions.find((s) => s.id === r.sessionId)!.setupSnapshot.mapRevisionId)?.mapId === map.id,
  );

  const key = (r: number, c: number) => `${r},${c}`;
  const clickCell = (r: number, c: number, shift: boolean) => {
    if (shift && anchor) {
      const [r0, r1] = [Math.min(anchor[0], r), Math.max(anchor[0], r)];
      const [c0, c1] = [Math.min(anchor[1], c), Math.max(anchor[1], c)];
      const next = new Set<string>();
      for (let ri = r0; ri <= r1; ri++) for (let ci = c0; ci <= c1; ci++) next.add(key(ri, ci));
      setSel(next);
    } else {
      setAnchor([r, c]);
      setSel(new Set([key(r, c)]));
    }
  };

  const applyToSel = (fn: (v: number) => number) => {
    update((d) => {
      const rev = d.mapRevisions.find((x) => x.id === revId)!;
      const g = rev.tables[tableDef.id];
      const targets = sel.size ? [...sel].map((k) => k.split(',').map(Number)) : [];
      for (const [r, c] of targets) {
        const nv = Math.min(tableDef.allowedMax, Math.max(tableDef.allowedMin, fn(g[r][c])));
        g[r][c] = +nv.toFixed(tableDef.precision);
      }
    });
  };

  const doTransition = (to: MapRevision['state'], note?: string) => {
    try {
      update((d) => {
        const rev = d.mapRevisions.find((x) => x.id === revId)!;
        transitionRevision(d, user, rev, to, note);
      });
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const compatBike = db.bikes.find((b) => b.id === checkBikeId);
  const compat = compatBike ? checkCompatibility(revision.compatibility, db, compatBike) : null;

  const nextActions: Array<{ to: MapRevision['state']; label: string; enabled: boolean; title?: string; confirm?: string }> = [];
  if (revision.state === 'DRAFT') nextActions.push({ to: 'TUNER_REVIEW', label: 'Submit for tuner review', enabled: allowed('map.submitForReview') });
  if (revision.state === 'TUNER_REVIEW') {
    nextActions.push({
      to: 'APPROVED_FOR_TEST', label: 'Approve for test',
      enabled: allowed('map.approveForTest') && !envelope.exceeded,
      title: envelope.exceeded ? 'Blocked: exceeds validated envelope' : undefined,
      confirm: `Approve ${map.name}-${revision.rev} for test? This is recorded in the audit log under your name.`,
    });
    nextActions.push({ to: 'REJECTED', label: 'Reject', enabled: allowed('map.reject') });
  }
  if (revision.state === 'APPROVED_FOR_TEST') nextActions.push({ to: 'EXPORTED', label: 'Generate companion change sheet →', enabled: allowed('map.export') });
  if (revision.state === 'TESTED') {
    nextActions.push({ to: 'ACCEPTED', label: 'Accept (post-test)', enabled: allowed('ai.decide') });
    nextActions.push({ to: 'REJECTED', label: 'Reject (post-test)', enabled: allowed('map.reject') });
  }
  if (revision.state === 'ACCEPTED') nextActions.push({ to: 'TEAM_BASELINE', label: 'Promote to team baseline', enabled: allowed('map.promoteBaseline'), confirm: `Promote ${revision.rev} to team baseline?` });

  return (
    <div>
      <div className="page-title">
        <h1 className="mono">{map.name}-{revision.rev}</h1>
        <span className="sub">{tableDef.label}</span>
        <StatePill state={revision.state} />
        <Prov p={revision.provenance} />
      </div>

      <div className="flow no-print" style={{ marginBottom: 18 }}>
        {FLOW.map((s) => (
          <span key={s} className={`step ${s === revision.state ? 'now' : FLOW.indexOf(s) < FLOW.indexOf(revision.state) ? 'done' : ''}`}>
            {s.replaceAll('_', ' ')}
          </span>
        ))}
        {(revision.state === 'REJECTED' || revision.state === 'RETIRED' || revision.state === 'REVISED') && (
          <span className="step now">{revision.state}</span>
        )}
      </div>

      {/* contextual controls: Compare · History · TRACE Insight · Advanced */}
      <div className="btn-row no-print" style={{ marginBottom: 16 }}>
        {parent && (
          <button className={`btn small ${showDiff ? 'primary' : ''}`} onClick={() => setShowDiff(!showDiff)}>
            Compare Δ vs {parent.rev}
          </button>
        )}
        {parent && <button className="btn small ghost" onClick={() => nav(`maps/${parent.id}`)}>History: {parent.rev} ←</button>}
        {relatedInsight && (
          <button className="btn small ghost" onClick={() => nav(`engineer/${relatedInsight.id}`)}>TRACE Insight ({relatedInsight.confidencePct}%)</button>
        )}
        <button className="btn small ghost" onClick={() => setAdvOpen(true)}>Advanced…</button>
      </div>

      <p className="mobile-note">Map editing works here, but a tablet or desktop display is recommended for serious table work.</p>
      <div className="cols wide-left">
        <div>
          <Panel title={`${tableDef.label} (${tableDef.unit}) — ${yAxis.label} × ${xAxis.label}`}>
            <Help id="grid">
              Grids are <b>data-driven</b> from the verified ECU definition — axes, ranges, and precision
              are never assumed. Warm adds ({tableDef.unit === '%' ? 'richer' : 'advance'}), cool removes.
            </Help>
            <div className="tbl-scroll">
              <table className="mapgrid">
                <thead>
                  <tr>
                    <th className="rowh">{yAxis.label} \ {xAxis.label}</th>
                    {xAxis.breakpoints.map((bp) => <th key={bp}>{bp}{xAxis.unit === '%' ? '%' : ''}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {grid.map((row, r) => (
                    <tr key={r}>
                      <th className="rowh mono">{yAxis.breakpoints[r].toLocaleString()}</th>
                      {row.map((v, c) => {
                        const pv = parent?.tables[tableDef.id]?.[r]?.[c] ?? 0;
                        const shown = showDiff ? +(v - pv).toFixed(tableDef.precision) : v;
                        const range = showDiff ? Math.max(1, (tableDef.allowedMax - tableDef.allowedMin) / 6) : tableDef.allowedMax;
                        const bg = heatColor(shown, range, th);
                        return (
                          <td key={c}>
                            <button
                              className={`mcell ${sel.has(key(r, c)) ? 'sel' : ''}`}
                              style={{ background: bg, color: inkFor(bg) }}
                              onClick={(e) => clickCell(r, c, e.shiftKey)}
                              title={`${yAxis.breakpoints[r]} ${yAxis.unit} · ${xAxis.breakpoints[c]}${xAxis.unit}`}
                            >
                              {shown === 0 ? '0' : fmtSigned(shown, tableDef.precision)}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="scalebar">
              <span className="lab mono">{tableDef.allowedMin}{tableDef.unit}</span>
              <div className="bar" style={{ background: `linear-gradient(90deg, ${[...Array(11)].map((_, i) => heatColor(tableDef.allowedMin + (i / 10) * (tableDef.allowedMax - tableDef.allowedMin), tableDef.allowedMax, th)).join(',')})` }} />
              <span className="lab mono">+{tableDef.allowedMax}{tableDef.unit}</span>
            </div>
            {editable ? (
              <div className="btn-row" style={{ marginTop: 14 }}>
                {[-1, -0.5, 0.5, 1].map((d) => (
                  <button key={d} className="btn small mono" disabled={!sel.size} onClick={() => applyToSel((v) => v + d)}>{fmtSigned(d, 1)}</button>
                ))}
                <button className="btn small" disabled={!sel.size} onClick={() => {
                  const raw = prompt(`Set selected cells to (${tableDef.unit}):`);
                  const n = raw === null ? NaN : parseFloat(raw);
                  if (Number.isFinite(n)) applyToSel(() => n);
                }}>Set…</button>
                <button className="btn small" disabled={!sel.size} onClick={() => {
                  const raw = prompt('Percentage change, e.g. 5 for +5%:');
                  const n = raw === null ? NaN : parseFloat(raw);
                  if (Number.isFinite(n)) applyToSel((v) => v * (1 + n / 100));
                }}>% change…</button>
                <button className="btn small" disabled={!sel.size} onClick={() => applyToSel(() => 0)}>Zero</button>
                <span className="hint">{sel.size ? `${sel.size} cells — shift-click extends the region` : 'Click a cell; shift-click to select a region'}</span>
              </div>
            ) : (
              <p className="hint" style={{ marginTop: 12 }}>
                {revision.state === 'DRAFT' ? 'Your role cannot edit drafts.' : `Read-only — cells are locked outside DRAFT (state: ${revision.state.replaceAll('_', ' ')}).`}
              </p>
            )}
          </Panel>

          {parent && (showDiff || diff.length > 0) && (
            <Panel title={`Change summary vs ${parent.rev}`}>
              <p className="hint" style={{ marginTop: 0 }}>{diff.length} cell change{diff.length === 1 ? '' : 's'}; {trimDiff.length} trim change{trimDiff.length === 1 ? '' : 's'}.</p>
              {envelope.exceeded && (
                <p style={{ color: 'var(--critical)', fontSize: 13, fontWeight: 650 }}>⚠ Envelope: {envelope.details[0]}</p>
              )}
              <div className="tbl-scroll" style={{ maxHeight: 220, overflowY: 'auto' }}>
                <table className="data">
                  <thead><tr><th>Table</th><th>{yAxis.label}</th><th>{xAxis.label}</th><th>{parent.rev}</th><th>{revision.rev}</th><th>Δ</th></tr></thead>
                  <tbody>
                    {diff.map((d, i) => {
                      const tdDef = map.tableDefs.find((x) => x.id === d.tableId)!;
                      const ax = map.axes.find((a) => a.id === tdDef.xAxisId)!;
                      const ay = map.axes.find((a) => a.id === tdDef.yAxisId)!;
                      return (
                        <tr key={i}>
                          <td>{tdDef.label}</td>
                          <td className="num">{ay.breakpoints[d.y].toLocaleString()}</td>
                          <td className="num">{ax.breakpoints[d.x]}{ax.unit}</td>
                          <td className="num">{d.a}</td>
                          <td className="num">{d.b}</td>
                          <td className="num">{fmtSigned(d.delta, 1)}</td>
                        </tr>
                      );
                    })}
                    {trimDiff.map((t) => (
                      <tr key={t.trim}><td>Global trim</td><td colSpan={2}>{t.trim}</td><td className="num">{t.a}</td><td className="num">{t.b}</td><td className="num">{fmtSigned(t.b - t.a, 0)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </div>

        <div>
          <Panel title="Workflow">
            <dl className="kv">
              <dt>Author</dt><dd>{db.users.find((u) => u.id === revision.authorUserId)?.name}</dd>
              <dt>Approved by</dt><dd>{revision.approvedByUserId ? `${db.users.find((u) => u.id === revision.approvedByUserId)?.name}` : '—'}</dd>
              <dt>Parent</dt><dd className="mono">{parent ? <a href={`#/maps/${parent.id}`}>{parent.rev}</a> : '—'}</dd>
              <dt>Children</dt>
              <dd className="mono">
                {db.mapRevisions.filter((r) => r.parentRevisionId === revision.id).map((r) => <a key={r.id} href={`#/maps/${r.id}`}>{r.rev} </a>)}
                {db.mapRevisions.filter((r) => r.parentRevisionId === revision.id).length === 0 && '—'}
              </dd>
              <dt>Notes</dt><dd>{revision.notes}</dd>
            </dl>
            <div className="btn-row" style={{ marginTop: 14 }}>
              {nextActions.map((a) => (
                <button key={a.to} className="btn small primary" disabled={!a.enabled} title={a.title}
                  onClick={() => {
                    if (a.confirm && !confirm(a.confirm)) return;
                    const note = a.to === 'REJECTED' ? prompt('Rejection note (required):') ?? undefined : undefined;
                    if (a.to === 'REJECTED' && !note) return;
                    if (a.to === 'EXPORTED') { doTransition('EXPORTED'); nav(`transfer/${revision.id}`); return; }
                    doTransition(a.to, note);
                  }}>
                  {a.label}
                </button>
              ))}
              {revision.state === 'EXPORTED' && (
                <button className="btn small primary" onClick={() => nav(`transfer/${revision.id}`)}>Open transfer worksheet →</button>
              )}
              {['TRANSFER_CONFIRMED', 'TESTED', 'ACCEPTED', 'TEAM_BASELINE'].includes(revision.state) && (
                <button className="btn small" onClick={() => nav(`transfer/${revision.id}`)}>Load onto a bike →</button>
              )}
              {allowed('map.createRevision') && (
                <button className="btn small ghost" onClick={() => {
                  update((d) => {
                    const src = d.mapRevisions.find((x) => x.id === revId)!;
                    const n = d.mapRevisions.filter((r) => r.mapId === src.mapId).length;
                    const child: MapRevision = JSON.parse(JSON.stringify(src));
                    child.id = `rev-${Date.now()}`;
                    child.rev = `R${String(n + 5).padStart(2, '0')}`;
                    child.state = 'DRAFT';
                    child.parentRevisionId = src.id;
                    child.authorUserId = user.id;
                    child.notes = `Draft from ${src.rev}`;
                    child.createdAt = new Date().toISOString();
                    child.testedInSessionIds = [];
                    delete child.approvedByUserId;
                    delete child.approvedAt;
                    d.mapRevisions.push(child);
                    appendAudit(d, user.id, 'map.create_draft', 'MapRevision', child.id, `${child.rev} drafted from ${src.rev}.`);
                    nav(`maps/${child.id}`);
                  });
                }}>Create draft from this</button>
              )}
            </div>
          </Panel>

          <Panel title="Audit">
            <AuditList entityIds={[revision.id]} />
          </Panel>
        </div>
      </div>

      {advOpen && (
        <Drawer title="Advanced" onClose={() => setAdvOpen(false)}>
          <p className="eyebrow">Tables</p>
          <div className="btn-row" style={{ marginBottom: 18 }}>
            {map.tableDefs.map((td) => (
              <button key={td.id} className={`btn small ${tableId === td.id ? 'primary' : ''}`}
                onClick={() => { setTableId(td.id); setSel(new Set()); }}>
                {td.label}
              </button>
            ))}
          </div>

          <p className="eyebrow">Global trims</p>
          <p className="mono" style={{ marginTop: 0 }}>
            {Object.entries(revision.globalTrims).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'none'}
          </p>

          <p className="eyebrow" style={{ marginTop: 18 }}>Compatibility</p>
          <div className="field">
            <label>Evaluate against bike</label>
            <select value={checkBikeId} onChange={(e) => setCheckBikeId(e.target.value)}>
              {db.bikes.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
            </select>
          </div>
          {compat && (
            <>
              <Pill tone={compat.blocking ? 'critical' : compat.verdict === 'Compatible' ? 'good' : 'warning'}>{compat.verdict}</Pill>
              <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 13 }}>
                {compat.details.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </>
          )}
          <dl className="kv" style={{ marginTop: 12 }}>
            <dt>Authored for</dt>
            <dd>{revision.compatibility.modelYear} {revision.compatibility.model} · {revision.compatibility.ecuFirmware}</dd>
            <dt>Engine build</dt><dd className="mono">{revision.compatibility.engineBuildId}</dd>
            <dt>Envelope</dt><dd className="mono">{revision.compatibility.envelopeVersion}</dd>
            <dt>Provenance</dt><dd><Prov p={revision.provenance} /> · created {new Date(revision.createdAt).toLocaleString()}</dd>
          </dl>

          <p className="eyebrow" style={{ marginTop: 18 }}>Exports</p>
          <div className="btn-row">
            <button className="btn small" disabled={!allowed('map.export')} onClick={() => {
              update((d) => appendAudit(d, user.id, 'map.export', 'MapRevision', revision.id, `CSV diff exported for ${revision.rev}.`));
              const rows = ['table,rpm,throttle,parent,revision,delta'];
              for (const d of diff) {
                const tdDef = map.tableDefs.find((x) => x.id === d.tableId)!;
                const ax = map.axes.find((a) => a.id === tdDef.xAxisId)!;
                const ay = map.axes.find((a) => a.id === tdDef.yAxisId)!;
                rows.push(`${d.tableId},${ay.breakpoints[d.y]},${ax.breakpoints[d.x]},${d.a},${d.b},${d.delta}`);
              }
              download(`${map.name}-${revision.rev}-diff.csv`, rows.join('\n'), 'text/csv');
            }}>CSV diff</button>
            <button className="btn small" disabled={!allowed('map.export')} onClick={() => {
              update((d) => appendAudit(d, user.id, 'map.export', 'MapRevision', revision.id, `JSON archive exported for ${revision.rev}.`));
              download(`${map.name}-${revision.rev}.json`, JSON.stringify({ banner: 'SIMULATED DEMONSTRATION DATA — NOT A VALID TUNE', map: map.name, revision }, null, 2), 'application/json');
            }}>JSON archive</button>
          </div>
          <p className="hint">
            No proprietary Vortex file formats are produced — that requires verified documentation and
            authorization (Phase 4). No 3D surface view yet: it ships only if it beats the table for
            real tasks, never as decoration.
          </p>
        </Drawer>
      )}
    </div>
  );
}
